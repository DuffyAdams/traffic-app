# routes.py
"""
Flask API routes for the traffic app.
Import this module to register all routes on the shared `app` instance.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta

import requests
from dateutil.relativedelta import relativedelta
from flask import jsonify, request, send_from_directory

from config import (
    app, DB_FILE, TARGET_DIR, COOKIE_NAME, COOKIE_MAX_AGE, db_lock
)
from db import read_incidents
from logger import safe_print


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


# ---------------------------------------------------------------------------
# Incident list & stats
# ---------------------------------------------------------------------------

@app.route("/api/incidents")
def get_incidents():
    device_uuid    = _get_or_create_uuid(request)
    limit         = int(request.args.get("limit", 20))
    cursor        = request.args.get("cursor")
    incident_types = request.args.getlist("type")
    locations     = request.args.getlist("location")
    sources       = request.args.getlist("source")
    active_only   = request.args.get("active_only", "false").lower() == "true"
    date_filter   = request.args.get("date_filter")

    incidents = read_incidents(
        limit=limit, cursor=cursor, incident_types=incident_types,
        locations=locations, sources=sources, active_only=active_only,
        date_filter=date_filter, device_uuid=device_uuid,
    )

    response = jsonify(incidents)
    return _set_uuid_cookie(response, device_uuid)


@app.route("/api/incident_stats")
def get_incident_stats():
    date_filter = request.args.get("date_filter")
    sources     = request.args.getlist("source")

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()

        where_clauses, query_params = [], []

        if sources:
            ph = ",".join("?" for _ in sources)
            where_clauses.append(f"source IN ({ph})")
            query_params.extend(sources)

        if date_filter == "day":
            where_clauses.append("date = ?")
            query_params.append(datetime.now().strftime("%Y-%m-%d"))
        elif date_filter == "week":
            where_clauses.append("timestamp >= ?")
            query_params.append((datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"))
        elif date_filter == "month":
            where_clauses.append("timestamp >= ?")
            query_params.append((datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"))
        elif date_filter == "year":
            where_clauses.append("timestamp >= ?")
            query_params.append(
                (datetime.now() - relativedelta(months=12)).strftime("%Y-%m-%d %H:%M:%S")
            )

        def make_query(select_part, extra=None):
            clauses = where_clauses[:]
            params  = query_params[:]
            if extra:
                clauses.append(extra)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            return f"{select_part}{where}", params

        # ── Stat counters ──────────────────────────────────────────────────
        today = datetime.now().strftime("%Y-%m-%d")
        events_today      = _count_with_source(cur, sources, "date = ?",          [today])
        events_last_hour  = _count_with_source(
            cur, sources, "timestamp >= ?",
            [(datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")],
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
        chart_data = _build_chart_data(cur, sources, date_filter)

        # ── Historical hourly average ──────────────────────────────────────
        historical_avg = _historical_hour_average(cur, sources)

    return jsonify({
        "eventsToday":                 events_today,
        "eventsLastHour":              events_last_hour,
        "eventsActive":                events_active,
        "totalIncidents":              total_incidents,
        "incidentsByType":             incidents_by_type,
        "topLocations":                top_locations,
        "hourlyData":                  chart_data,
        "historicalCurrentHourAverage": historical_avg,
    })


def _count_with_source(cur, sources, extra_cond, extra_params):
    clauses = ([f"source IN ({','.join('?' for _ in sources)})"] if sources else []) + [extra_cond]
    params  = (list(sources) if sources else []) + extra_params
    cur.execute(f"SELECT COUNT(*) FROM incidents WHERE {' AND '.join(clauses)}", params)
    return cur.fetchone()[0]


def _range_count(cur, sources, start_str, end_str):
    clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
    params  = list(sources) if sources else []
    clauses += ["timestamp >= ?", "timestamp < ?"]
    params  += [start_str, end_str]
    cur.execute(
        f"SELECT COUNT(*) FROM incidents WHERE {' AND '.join(clauses)}", params
    )
    return cur.fetchone()[0]


def _build_chart_data(cur, sources, date_filter):
    now = datetime.now()
    if date_filter == "year":
        return [
            _range_count(
                cur, sources,
                (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(months=11 - i)).strftime("%Y-%m-%d %H:%M:%S"),
                (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(months=10 - i)).strftime("%Y-%m-%d %H:%M:%S"),
            )
            for i in range(12)
        ]
    elif date_filter == "month":
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            _range_count(
                cur, sources,
                (base - timedelta(days=29 - i)).strftime("%Y-%m-%d %H:%M:%S"),
                (base - timedelta(days=28 - i)).strftime("%Y-%m-%d %H:%M:%S"),
            )
            for i in range(30)
        ]
    elif date_filter == "week":
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            _range_count(
                cur, sources,
                (base - timedelta(days=6 - i)).strftime("%Y-%m-%d %H:%M:%S"),
                (base - timedelta(days=5 - i)).strftime("%Y-%m-%d %H:%M:%S"),
            )
            for i in range(7)
        ]
    else:  # default: last 24h by hour
        start24 = now - timedelta(hours=24)
        return [
            _range_count(
                cur, sources,
                (start24 + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                min(start24 + timedelta(hours=i + 1), now).strftime("%Y-%m-%d %H:%M:%S"),
            )
            for i in range(24)
        ]


def _historical_hour_average(cur, sources):
    now          = datetime.now()
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
    return send_from_directory(TARGET_DIR, filename)


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

@app.route("/api/incidents/<incident_id>/like", methods=["POST", "DELETE"])
def like_incident(incident_id):
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
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO likes (incident_no, device_uuid, timestamp) VALUES (?, ?, ?)",
                            (incident_id, device_uuid, timestamp))
                cur.execute("UPDATE incidents SET likes = likes + 1 WHERE incident_no = ?",
                            (incident_id,))
            conn.commit()

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
    device_uuid  = _get_or_create_uuid(request)
    new_comment  = request.json.get("comment", "")
    username     = request.json.get("username", "Anonymous")
    timestamp    = request.json.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    if not new_comment:
        return jsonify({"error": "Empty comment"}), 400

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
