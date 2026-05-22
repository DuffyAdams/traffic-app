# routes.py
"""
Flask API routes for the traffic app.
Import this module to register all routes on the shared `app` instance.
"""

import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from threading import Lock

import requests
from dateutil.relativedelta import relativedelta
from flask import abort, jsonify, request, send_from_directory

from config import (
    app, DB_FILE, TARGET_DIR, COOKIE_NAME, COOKIE_MAX_AGE, db_lock,
    API_READ_RATE_LIMIT, API_WRITE_RATE_LIMIT, TRUST_PROXY_HEADERS,
    now_pst, pst_timestamp_str,
)
from db import read_incidents, with_user_like_state
from logger import safe_print


MAX_INCIDENT_LIMIT = 150
MAX_FILTER_VALUES = 25
MAX_FILTER_LENGTH = 80
MAX_COMMENT_LENGTH = 500
MAX_USERNAME_LENGTH = 40
READ_CACHE_TTL = 20
STATS_CACHE_TTL = 45
ALLOWED_DATE_FILTERS = {None, "day", "daily", "week", "month", "year"}
ALLOWED_SOURCES = {"CHP", "SDPD", "SDSO", "SDFD"}

_response_cache = {}
_cache_lock = Lock()
_rate_limit_hits = {}
_rate_limit_lock = Lock()


# ---------------------------------------------------------------------------
# Cookie helper
# ---------------------------------------------------------------------------

def _get_or_create_uuid(req):
    device_uuid = req.cookies.get(COOKIE_NAME)
    if not device_uuid:
        device_uuid = str(uuid.uuid4())
        safe_print(f"New UUID: {device_uuid}")
    else:
        safe_print(f"Reusing UUID: {device_uuid}")
    return device_uuid


def _set_uuid_cookie(response, device_uuid):
    """Attach UUID cookie to a response if not already present."""
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=False,
            httponly=True,
            samesite="Lax",
        )
    return response


def _parse_limit(default=20, max_value=MAX_INCIDENT_LIMIT):
    raw_limit = request.args.get("limit", str(default))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        abort(400, description="Invalid limit")

    return max(1, min(limit, max_value))


def _clean_filter_values(name, allowed_values=None):
    values = []
    for raw_value in request.args.getlist(name)[:MAX_FILTER_VALUES]:
        value = raw_value.strip()
        if not value:
            continue
        if len(value) > MAX_FILTER_LENGTH:
            abort(400, description=f"{name} value is too long")
        if allowed_values and value not in allowed_values:
            abort(400, description=f"Invalid {name} value")
        values.append(value)
    return values


def _get_date_filter():
    date_filter = request.args.get("date_filter")
    if date_filter not in ALLOWED_DATE_FILTERS:
        abort(400, description="Invalid date_filter")
    return date_filter


def _cache_key(prefix, *extra_parts):
    args = tuple(
        sorted(
            (key, tuple(sorted(value.strip() for value in values)))
            for key, values in request.args.lists()
        )
    )
    return (prefix, args, extra_parts)


def _get_cached_response(key):
    now = time.time()
    with _cache_lock:
        cached = _response_cache.get(key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            _response_cache.pop(key, None)
            return None
        return payload


def _set_cached_response(key, payload, ttl):
    with _cache_lock:
        _response_cache[key] = (time.time() + ttl, payload)


def _clear_response_cache():
    with _cache_lock:
        _response_cache.clear()


def _validate_incident_id(incident_id):
    if not incident_id or len(incident_id) > 80:
        abort(400, description="Invalid incident id")
    return incident_id


def _parse_rate_limit(limit_spec):
    count_part, _, period_part = limit_spec.partition(" per ")
    try:
        max_requests = int(count_part.strip())
    except ValueError:
        max_requests = 60

    period = period_part.strip().lower()
    if period.startswith("hour"):
        window_seconds = 3600
    elif period.startswith("second"):
        window_seconds = 1
    else:
        window_seconds = 60

    return max_requests, window_seconds


def _client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if TRUST_PROXY_HEADERS and forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def _enforce_rate_limit(bucket, limit_spec):
    max_requests, window_seconds = _parse_rate_limit(limit_spec)
    now = time.time()
    key = (_client_ip(), bucket)

    with _rate_limit_lock:
        window = [
            hit_at
            for hit_at in _rate_limit_hits.get(key, [])
            if now - hit_at < window_seconds
        ]
        if len(window) >= max_requests:
            abort(429, description="Too many requests")
        window.append(now)
        _rate_limit_hits[key] = window


# ---------------------------------------------------------------------------
# Incident list & stats
# ---------------------------------------------------------------------------

@app.route("/api/incidents")
def get_incidents():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid    = _get_or_create_uuid(request)
    limit         = _parse_limit()
    cursor        = request.args.get("cursor")
    if cursor and len(cursor) > 120:
        abort(400, description="Invalid cursor")
    incident_types = _clean_filter_values("type")
    locations     = _clean_filter_values("location")
    sources       = _clean_filter_values("source", ALLOWED_SOURCES)
    active_only   = request.args.get("active_only", "false").lower() == "true"
    date_filter   = _get_date_filter()

    cache_key = _cache_key("incidents")
    incidents = _get_cached_response(cache_key)
    if incidents is None:
        incidents = read_incidents(
            limit=limit, cursor=cursor, incident_types=incident_types,
            locations=locations, sources=sources, active_only=active_only,
            date_filter=date_filter, device_uuid=None,
        )
        _set_cached_response(cache_key, incidents, READ_CACHE_TTL)

    incidents = with_user_like_state(incidents, device_uuid)

    response = jsonify(incidents)
    return _set_uuid_cookie(response, device_uuid)


@app.route("/api/incident_stats")
def get_incident_stats():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    date_filter = _get_date_filter()
    sources     = _clean_filter_values("source", ALLOWED_SOURCES)
    now         = now_pst()

    cache_key = _cache_key("incident_stats")
    cached_payload = _get_cached_response(cache_key)
    if cached_payload is not None:
        return jsonify(cached_payload)

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()

        where_clauses, query_params = [], []

        if sources:
            ph = ",".join("?" for _ in sources)
            where_clauses.append(f"source IN ({ph})")
            query_params.extend(sources)

        if date_filter == "day":
            where_clauses.append("date = ?")
            query_params.append(now.strftime("%Y-%m-%d"))
        elif date_filter == "week":
            where_clauses.append("timestamp >= ?")
            query_params.append((now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"))
        elif date_filter == "month":
            where_clauses.append("timestamp >= ?")
            query_params.append((now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"))
        elif date_filter == "year":
            where_clauses.append("timestamp >= ?")
            query_params.append(
                (now - relativedelta(months=12)).strftime("%Y-%m-%d %H:%M:%S")
            )

        def make_query(select_part, extra=None):
            clauses = where_clauses[:]
            params  = query_params[:]
            if extra:
                clauses.append(extra)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            return f"{select_part}{where}", params

        # ── Stat counters ──────────────────────────────────────────────────
        today = now.strftime("%Y-%m-%d")
        events_today      = _count_with_source(cur, sources, "date = ?",          [today])
        events_last_hour  = _count_with_source(
            cur, sources, "timestamp >= ?",
            [(now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")],
        )
        q, p = make_query("SELECT COUNT(*) FROM incidents", "active = 1")
        cur.execute(q, p); events_active = cur.fetchone()[0]

        q, p = make_query("SELECT COUNT(*) FROM incidents")
        cur.execute(q, p); total_incidents = cur.fetchone()[0]

        q, p = make_query("SELECT type, COUNT(*) as count FROM incidents")
        cur.execute(q + " GROUP BY type ORDER BY count DESC", p)
        incidents_by_type = {row[0]: row[1] for row in cur.fetchall()}

        q, p = make_query("SELECT location, COUNT(*) as count FROM incidents",
                          "location IS NOT NULL AND location != ''")
        cur.execute(q + " GROUP BY location ORDER BY count DESC LIMIT 10", p)
        top_locations = {row[0]: row[1] for row in cur.fetchall()}

        # ── Chart data ─────────────────────────────────────────────────────
        chart_data = _build_chart_data(cur, sources, date_filter, now)

        # ── Historical hourly average ──────────────────────────────────────
        historical_avg = _historical_hour_average(cur, sources, now)

    payload = {
        "eventsToday":                 events_today,
        "eventsLastHour":              events_last_hour,
        "eventsActive":                events_active,
        "totalIncidents":              total_incidents,
        "incidentsByType":             incidents_by_type,
        "topLocations":                top_locations,
        "hourlyData":                  chart_data,
        "historicalCurrentHourAverage": historical_avg,
        "generatedAt":                 now.isoformat(),
    }
    _set_cached_response(cache_key, payload, STATS_CACHE_TTL)
    return jsonify(payload)


def _count_with_source(cur, sources, extra_cond, extra_params):
    clauses = ([f"source IN ({','.join('?' for _ in sources)})"] if sources else []) + [extra_cond]
    params  = (list(sources) if sources else []) + extra_params
    cur.execute(f"SELECT COUNT(*) FROM incidents WHERE {' AND '.join(clauses)}", params)
    return cur.fetchone()[0]


def _source_clause(sources):
    if not sources:
        return [], []
    return [f"source IN ({','.join('?' for _ in sources)})"], list(sources)


def _bucket_counts(cur, sources, start_dt, end_dt, bucket_format):
    clauses, params = _source_clause(sources)
    clauses += ["timestamp >= ?", "timestamp < ?"]
    params += [
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    ]

    cur.execute(
        f"""
        SELECT strftime(?, timestamp) AS bucket, COUNT(*) AS count
        FROM incidents
        WHERE {' AND '.join(clauses)}
        GROUP BY bucket
        """,
        [bucket_format, *params],
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def _hour_offset_counts(cur, sources, start_dt, end_dt):
    clauses, params = _source_clause(sources)
    clauses += ["timestamp >= ?", "timestamp < ?"]
    params += [
        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    ]

    cur.execute(
        f"""
        SELECT CAST((strftime('%s', timestamp) - strftime('%s', ?)) / 3600 AS INTEGER) AS bucket,
               COUNT(*) AS count
        FROM incidents
        WHERE {' AND '.join(clauses)}
        GROUP BY bucket
        """,
        [start_dt.strftime("%Y-%m-%d %H:%M:%S"), *params],
    )
    return {row[0]: row[1] for row in cur.fetchall() if row[0] is not None}


def _build_chart_data(cur, sources, date_filter, now):
    if date_filter == "year":
        base = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        starts = [base - relativedelta(months=11 - i) for i in range(12)]
        counts = _bucket_counts(cur, sources, starts[0], base + relativedelta(months=1), "%Y-%m")
        return [counts.get(start.strftime("%Y-%m"), 0) for start in starts]
    elif date_filter == "month":
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [base - timedelta(days=29 - i) for i in range(30)]
        counts = _bucket_counts(cur, sources, starts[0], base + timedelta(days=1), "%Y-%m-%d")
        return [counts.get(start.strftime("%Y-%m-%d"), 0) for start in starts]
    elif date_filter == "week":
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [base - timedelta(days=6 - i) for i in range(7)]
        counts = _bucket_counts(cur, sources, starts[0], base + timedelta(days=1), "%Y-%m-%d")
        return [counts.get(start.strftime("%Y-%m-%d"), 0) for start in starts]
    else:  # default: last 24h by hour
        start24 = now - timedelta(hours=24)
        counts = _hour_offset_counts(cur, sources, start24, now)
        return [counts.get(i, 0) for i in range(24)]


def _historical_hour_average(cur, sources, now):
    hour_str     = now.strftime("%H")
    dow_str      = now.strftime("%w")

    clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
    params  = list(sources) if sources else []
    clauses += ["strftime('%w', timestamp) = ?", "strftime('%H', timestamp) = ?"]
    params  += [dow_str, hour_str]

    cur.execute(f"SELECT COUNT(*) FROM incidents WHERE {' AND '.join(clauses)}", params)
    total = cur.fetchone()[0] or 0

    day_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
    day_params  = (list(sources) if sources else []) + [dow_str]
    day_clauses.append("strftime('%w', timestamp) = ?")

    cur.execute(
        f"SELECT COUNT(DISTINCT date(timestamp)) FROM incidents WHERE {' AND '.join(day_clauses)}",
        day_params,
    )
    unique_days = cur.fetchone()[0] or 1
    return total / unique_days


# ---------------------------------------------------------------------------
# Map files
# ---------------------------------------------------------------------------

@app.route("/maps/<filename>")
def get_map(filename):
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    return send_from_directory(TARGET_DIR, filename)


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

@app.route("/api/incidents/<incident_id>/like", methods=["POST", "DELETE"])
def like_incident(incident_id):
    _enforce_rate_limit("write", API_WRITE_RATE_LIMIT)
    incident_id = _validate_incident_id(incident_id)
    device_uuid = _get_or_create_uuid(request)

    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cur = conn.cursor()
            if request.method == "DELETE":
                cur.execute("DELETE FROM likes WHERE incident_no = ? AND device_uuid = ?",
                            (incident_id, device_uuid))
                cur.execute("UPDATE incidents SET likes = MAX(likes - 1, 0) WHERE incident_no = ?",
                            (incident_id,))
            else:
                cur.execute("SELECT 1 FROM likes WHERE incident_no = ? AND device_uuid = ?",
                            (incident_id, device_uuid))
                if cur.fetchone():
                    return jsonify({"error": "You already liked this post."}), 400
                timestamp = pst_timestamp_str()
                cur.execute("INSERT INTO likes (incident_no, device_uuid, timestamp) VALUES (?, ?, ?)",
                            (incident_id, device_uuid, timestamp))
                cur.execute("UPDATE incidents SET likes = likes + 1 WHERE incident_no = ?",
                            (incident_id,))
            conn.commit()
            _clear_response_cache()

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()
        cur.execute("SELECT likes FROM incidents WHERE incident_no = ?", (incident_id,))
        result = cur.fetchone()
        likes_count = result[0] if result else 0

    response = jsonify(
        {
            "likes": likes_count,
            "liked_by_user": request.method != "DELETE",
        }
    )
    return _set_uuid_cookie(response, device_uuid)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@app.route("/api/incidents/<incident_id>/comment", methods=["POST"])
def comment_incident(incident_id):
    _enforce_rate_limit("write", API_WRITE_RATE_LIMIT)
    incident_id = _validate_incident_id(incident_id)
    device_uuid  = _get_or_create_uuid(request)
    payload      = request.get_json(silent=True) or {}
    new_comment  = str(payload.get("comment", "")).strip()
    username     = str(payload.get("username", "Anonymous")).strip() or "Anonymous"
    timestamp    = pst_timestamp_str()

    if not new_comment:
        return jsonify({"error": "Empty comment"}), 400
    if len(new_comment) > MAX_COMMENT_LENGTH:
        return jsonify({"error": "Comment is too long"}), 400
    if len(username) > MAX_USERNAME_LENGTH:
        username = username[:MAX_USERNAME_LENGTH]

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT COUNT(*) FROM comments WHERE incident_no = ? AND username = ?",
                (incident_id, username),
            )
            if cur.fetchone()[0] >= 2:
                return jsonify({"error": "You can only leave 2 comments per post."}), 400

            cur.execute(
                "INSERT INTO comments (incident_no, device_uuid, username, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
                (incident_id, device_uuid, username, new_comment, timestamp),
            )
            conn.commit()
            _clear_response_cache()
            cur.execute(
                "SELECT username, comment, timestamp FROM comments WHERE incident_no = ? ORDER BY timestamp ASC",
                (incident_id,),
            )
            comments = [{"username": r[0] or "Anonymous", "comment": r[1], "timestamp": r[2]}
                        for r in cur.fetchall()]
        except sqlite3.IntegrityError:
            conn.rollback()
            return jsonify({"error": "Could not process comment."}), 400

    response = jsonify({"comments": comments})
    return _set_uuid_cookie(response, device_uuid)


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------

@app.route("/api/user/check", methods=["GET"])
def check_user():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    response    = jsonify({"uuid": device_uuid})
    return _set_uuid_cookie(response, device_uuid)


# ---------------------------------------------------------------------------
# SPA catch-all
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_app(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


# Needed for the catch-all route above
import os  # noqa: E402 (placed after function def to avoid top-level circular risk)
