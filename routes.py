# routes.py
"""
Flask API routes for the traffic app.
Import this module to register all routes on the shared `app` instance.
"""

import ipaddress
import os
import queue
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from threading import Lock

import requests
from dateutil.relativedelta import relativedelta
from flask import abort, jsonify, request, send_from_directory

from config import (
    app, DB_FILE, TARGET_DIR, COOKIE_NAME, COOKIE_MAX_AGE, COOKIE_SECURE, db_lock,
    API_READ_RATE_LIMIT, API_WRITE_RATE_LIMIT, TRUST_PROXY_HEADERS,
    HTTP_TIMEOUT_SECONDS, now_pst, pst_timestamp_str,
)
from db import read_incidents, with_user_like_state
from logger import safe_print
from runtime_metrics import get_runtime_metrics, record_api_request


MAX_INCIDENT_LIMIT = 150
MAX_FILTER_VALUES = 25
MAX_FILTER_LENGTH = 80
MAX_COMMENT_LENGTH = 500
MAX_USERNAME_LENGTH = 40
READ_CACHE_TTL = 20
STATS_CACHE_TTL = 45
STATIC_ASSET_MAX_AGE_SECONDS = int(os.environ.get("STATIC_ASSET_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30)))
API_EVENT_BATCH_SIZE = int(os.environ.get("API_EVENT_BATCH_SIZE", "50"))
API_EVENT_FLUSH_SECONDS = float(os.environ.get("API_EVENT_FLUSH_SECONDS", "1.0"))
API_EVENT_QUEUE_SIZE = int(os.environ.get("API_EVENT_QUEUE_SIZE", "10000"))
ALLOWED_DATE_FILTERS = {None, "day", "daily", "week", "month", "year"}
ALLOWED_SOURCES = {"CHP", "SDPD", "SDSO", "SDFD"}
TRAFFIC_APP_PUBLIC_URL = os.environ.get("TRAFFIC_APP_PUBLIC_URL", "https://traffic-app.duffyadams.com")
METRICS_PUBLIC_URL = os.environ.get("METRICS_PUBLIC_URL", "https://metrics.duffyadams.com")
TRAFFIC_APP_PUBLIC_HOST = TRAFFIC_APP_PUBLIC_URL.split("://", 1)[-1].split("/", 1)[0]
METRICS_PUBLIC_HOST = METRICS_PUBLIC_URL.split("://", 1)[-1].split("/", 1)[0]
RESPONSE_CACHE_MAX_ENTRIES = int(os.environ.get("RESPONSE_CACHE_MAX_ENTRIES", "256"))
RATE_LIMIT_MAX_BUCKETS = int(os.environ.get("RATE_LIMIT_MAX_BUCKETS", "4096"))
INCIDENT_CACHE_ARGS = {"limit", "cursor", "type", "location", "source", "active_only", "date_filter"}
STATS_CACHE_ARGS = {"source", "date_filter"}

TRUSTED_PROXY_NETWORKS = []
for raw_network in os.environ.get("TRUSTED_PROXY_CIDRS", "127.0.0.0/8,::1/128").split(","):
    raw_network = raw_network.strip()
    if not raw_network:
        continue
    try:
        TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(raw_network, strict=False))
    except ValueError:
        safe_print(f"Ignoring invalid TRUSTED_PROXY_CIDRS entry: {raw_network}")

_response_cache = {}
_cache_lock = Lock()
_singleflight_locks = {}
_singleflight_guard = Lock()
_rate_limit_hits = {}
_rate_limit_lock = Lock()
_api_event_queue = queue.Queue(maxsize=API_EVENT_QUEUE_SIZE)
_api_event_drop_count = 0


def _get_singleflight_lock(key):
    with _singleflight_guard:
        lock = _singleflight_locks.get(key)
        if lock is None:
            lock = Lock()
            _singleflight_locks[key] = lock
        return lock


# ---------------------------------------------------------------------------
# Cookie helper
# ---------------------------------------------------------------------------

def _normalize_uuid(value):
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _get_or_create_uuid(req):
    device_uuid = _normalize_uuid(req.cookies.get(COOKIE_NAME))
    return device_uuid or str(uuid.uuid4())


def _set_uuid_cookie(response, device_uuid):
    """Attach UUID cookie to a response if missing or invalid."""
    if _normalize_uuid(request.cookies.get(COOKIE_NAME)) != device_uuid:
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=COOKIE_SECURE,
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


def _cache_key(prefix, allowed_args=None, *extra_parts):
    args = tuple(
        sorted(
            (key, tuple(sorted(value.strip() for value in values)))
            for key, values in request.args.lists()
            if allowed_args is None or key in allowed_args
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


def _prune_response_cache(now):
    expired = [key for key, (expires_at, _) in _response_cache.items() if expires_at <= now]
    for key in expired:
        _response_cache.pop(key, None)

    while len(_response_cache) >= RESPONSE_CACHE_MAX_ENTRIES:
        _response_cache.pop(next(iter(_response_cache)), None)


def _set_cached_response(key, payload, ttl):
    now = time.time()
    with _cache_lock:
        _prune_response_cache(now)
        _response_cache[key] = (now + ttl, payload)


def _api_event_worker():
    batch = []
    while True:
        try:
            item = _api_event_queue.get(timeout=API_EVENT_FLUSH_SECONDS)
            batch.append(item)
            while len(batch) < API_EVENT_BATCH_SIZE:
                try:
                    batch.append(_api_event_queue.get_nowait())
                except queue.Empty:
                    break
        except queue.Empty:
            pass

        if not batch:
            continue

        try:
            with db_lock:
                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                    conn.cursor().executemany(
                        """
                        INSERT INTO api_events (device_uuid, route, request_type, host, client_ip, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        batch,
                    )
                    conn.commit()
        except Exception as exc:
            safe_print(f"Analytics batch insert failed: {exc}")
        finally:
            batch.clear()


threading.Thread(target=_api_event_worker, name="api-event-writer", daemon=True).start()


@app.before_request
def _track_api_requests():
    if request.path.startswith("/api/"):
        record_api_request()


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


def _is_trusted_proxy(remote_addr):
    if not remote_addr or not TRUSTED_PROXY_NETWORKS:
        return False
    try:
        ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    return any(ip in network for network in TRUSTED_PROXY_NETWORKS)


def _client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if TRUST_PROXY_HEADERS and forwarded_for and _is_trusted_proxy(request.remote_addr):
        candidate = forwarded_for.split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return request.remote_addr or "unknown"


def _prune_rate_limit_buckets(now):
    stale_keys = [
        key for key, hits in _rate_limit_hits.items()
        if not hits or now - max(hits) >= 3600
    ]
    for key in stale_keys:
        _rate_limit_hits.pop(key, None)

    while len(_rate_limit_hits) > RATE_LIMIT_MAX_BUCKETS:
        _rate_limit_hits.pop(next(iter(_rate_limit_hits)), None)


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
        if len(_rate_limit_hits) > RATE_LIMIT_MAX_BUCKETS:
            _prune_rate_limit_buckets(now)


def _range_key(date_filter):
    return date_filter or "day"


def _range_label(date_filter):
    labels = {
        "day": "Today",
        "daily": "Today",
        "week": "Last 7 days",
        "month": "Last 30 days",
        "year": "Last 12 months",
        None: "Today",
    }
    return labels.get(date_filter, "Today")


def _range_start(now, date_filter):
    selected = _range_key(date_filter)
    if selected == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if selected == "week":
        return now - timedelta(days=7)
    if selected == "month":
        return now - timedelta(days=30)
    if selected == "year":
        return now - relativedelta(months=12)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _timestamp_clause(column, date_filter, now):
    start = _range_start(now, date_filter)
    return f"{column} >= ?", [start.strftime("%Y-%m-%d %H:%M:%S")]


def _date_clause(column, date_filter, now):
    selected = _range_key(date_filter)
    if selected == "day":
        return f"{column} = ?", [now.strftime("%Y-%m-%d")]
    start = _range_start(now, date_filter)
    return f"{column} >= ?", [start.strftime("%Y-%m-%d")]


def _record_api_event(device_uuid, route_name, request_type="read"):
    global _api_event_drop_count

    if not device_uuid:
        return

    host = (request.host or "").split(":", 1)[0]
    event = (
        device_uuid,
        route_name,
        request_type,
        host,
        _client_ip(),
        pst_timestamp_str(),
    )
    try:
        _api_event_queue.put_nowait(event)
    except queue.Full:
        _api_event_drop_count += 1
        if _api_event_drop_count % 100 == 1:
            safe_print(f"Analytics event queue full; dropped {_api_event_drop_count} events")


def _finalize_api_response(response, device_uuid, route_name, request_type="read"):
    _record_api_event(device_uuid, route_name, request_type=request_type)
    return _set_uuid_cookie(response, device_uuid)


def _count_query(cur, query, params=()):
    cur.execute(query, params)
    return cur.fetchone()[0] or 0


def _probe_url(url, timeout=HTTP_TIMEOUT_SECONDS):
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return {
            "ok": response.ok,
            "statusCode": response.status_code,
            "latencyMs": latency_ms,
            "url": url,
        }
    except Exception as exc:
        return {
            "ok": False,
            "statusCode": None,
            "latencyMs": None,
            "url": url,
            "error": str(exc),
        }


def _scrape_health_status(scrape_freshness_seconds):
    if scrape_freshness_seconds is None:
        return "Unknown"
    if scrape_freshness_seconds <= 90:
        return "Healthy"
    if scrape_freshness_seconds <= 300:
        return "Delayed"
    return "Stale"


# ---------------------------------------------------------------------------
# Incident list & stats
# ---------------------------------------------------------------------------

@app.route("/api/incidents")
def get_incidents():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    limit = _parse_limit()
    cursor = request.args.get("cursor")
    if cursor and len(cursor) > 120:
        abort(400, description="Invalid cursor")
    incident_types = _clean_filter_values("type")
    locations = _clean_filter_values("location")
    sources = _clean_filter_values("source", ALLOWED_SOURCES)
    active_only = request.args.get("active_only", "false").lower() == "true"
    date_filter = _get_date_filter()

    cache_key = _cache_key("incidents", INCIDENT_CACHE_ARGS)
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
    return _finalize_api_response(response, device_uuid, "incidents")


@app.route("/api/incident_stats")
def get_incident_stats():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    date_filter = _get_date_filter()
    sources = _clean_filter_values("source", ALLOWED_SOURCES)
    now = now_pst()

    cache_key = _cache_key("incident_stats", STATS_CACHE_ARGS)
    cached_payload = _get_cached_response(cache_key)
    if cached_payload is not None:
        response = jsonify(cached_payload)
        return _finalize_api_response(response, device_uuid, "incident_stats")

    with _get_singleflight_lock(cache_key):
        cached_payload = _get_cached_response(cache_key)
        if cached_payload is not None:
            response = jsonify(cached_payload)
            return _finalize_api_response(response, device_uuid, "incident_stats")

        payload = _build_incident_stats_payload(date_filter, sources, now)
        _set_cached_response(cache_key, payload, STATS_CACHE_TTL)

    response = jsonify(payload)
    return _finalize_api_response(response, device_uuid, "incident_stats")


def _build_incident_stats_payload(date_filter, sources, now):
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()

        where_clauses, query_params = [], []

        if sources:
            placeholders = ",".join("?" for _ in sources)
            where_clauses.append(f"source IN ({placeholders})")
            query_params.extend(sources)

        if _range_key(date_filter) == "day":
            where_clauses.append("date = ?")
            query_params.append(now.strftime("%Y-%m-%d"))
        elif _range_key(date_filter) == "week":
            where_clauses.append("timestamp >= ?")
            query_params.append((now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"))
        elif _range_key(date_filter) == "month":
            where_clauses.append("timestamp >= ?")
            query_params.append((now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"))
        elif _range_key(date_filter) == "year":
            where_clauses.append("timestamp >= ?")
            query_params.append(
                (now - relativedelta(months=12)).strftime("%Y-%m-%d %H:%M:%S")
            )

        def make_query(select_part, extra=None):
            clauses = where_clauses[:]
            params = query_params[:]
            if extra:
                clauses.append(extra)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            return f"{select_part}{where}", params

        today = now.strftime("%Y-%m-%d")
        events_today = _count_with_source(cur, sources, "date = ?", [today])
        events_last_hour = _count_with_source(
            cur,
            sources,
            "timestamp >= ?",
            [(now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")],
        )
        q, p = make_query("SELECT COUNT(*) FROM incidents", "active = 1")
        cur.execute(q, p)
        events_active = cur.fetchone()[0]

        q, p = make_query("SELECT COUNT(*) FROM incidents")
        cur.execute(q, p)
        total_incidents = cur.fetchone()[0]

        q, p = make_query("SELECT type, COUNT(*) as count FROM incidents")
        cur.execute(q + " GROUP BY type ORDER BY count DESC", p)
        incidents_by_type = {row[0]: row[1] for row in cur.fetchall()}

        q, p = make_query(
            "SELECT location, COUNT(*) as count FROM incidents",
            "location IS NOT NULL AND location != ''",
        )
        cur.execute(q + " GROUP BY location ORDER BY count DESC LIMIT 10", p)
        top_locations = {row[0]: row[1] for row in cur.fetchall()}

        chart_data = _build_chart_data(cur, sources, _range_key(date_filter), now)
        historical_avg = _historical_hour_average(cur, sources, now)

    runtime_snapshot = get_runtime_metrics()
    payload = {
        "rangeKey": _range_key(date_filter),
        "rangeLabel": _range_label(date_filter),
        "eventsToday": events_today,
        "eventsLastHour": events_last_hour,
        "eventsActive": events_active,
        "totalIncidents": total_incidents,
        "incidentsByType": incidents_by_type,
        "topLocations": top_locations,
        "hourlyData": chart_data,
        "historicalCurrentHourAverage": historical_avg,
        "generatedAt": now.isoformat(),
        "apiRequestsServed": runtime_snapshot["apiRequestsServed"],
        "averageScrapeTime": runtime_snapshot["averageScrapeTime"],
        "lastSuccessfulScrape": runtime_snapshot["lastSuccessfulScrape"],
        "lastSuccessfulScrapeAt": runtime_snapshot["lastSuccessfulScrapeAt"],
    }
    return payload


@app.route("/api/dashboard_metrics")
def get_dashboard_metrics():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    date_filter = _get_date_filter()
    now = now_pst()
    range_key = _range_key(date_filter)
    range_label = _range_label(date_filter)

    incident_clause, incident_params = _date_clause("date", range_key, now)
    event_clause, event_params = _timestamp_clause("timestamp", range_key, now)
    traffic_host = TRAFFIC_APP_PUBLIC_HOST
    metrics_host = METRICS_PUBLIC_HOST

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()

        total_incidents = _count_query(cur, "SELECT COUNT(*) FROM incidents")
        active_incidents = _count_query(cur, "SELECT COUNT(*) FROM incidents WHERE active = 1")
        incidents_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM incidents WHERE {incident_clause}",
            tuple(incident_params),
        )
        tracked_days = _count_query(cur, "SELECT COUNT(DISTINCT date) FROM incidents") or 0

        comments_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM comments WHERE {event_clause}",
            tuple(event_params),
        )
        likes_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM likes WHERE {event_clause}",
            tuple(event_params),
        )

        traffic_app_requests_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM api_events WHERE host = ? AND {event_clause}",
            (traffic_host, *event_params),
        )
        traffic_app_unique_visitors_in_range = _count_query(
            cur,
            f"""
            SELECT COUNT(DISTINCT device_uuid)
            FROM api_events
            WHERE host = ? AND {event_clause} AND device_uuid IS NOT NULL AND device_uuid != ''
            """,
            (traffic_host, *event_params),
        )
        metrics_page_requests_in_range = _count_query(
            cur,
            f"SELECT COUNT(*) FROM api_events WHERE host = ? AND {event_clause}",
            (metrics_host, *event_params),
        )
        metrics_page_unique_visitors_in_range = _count_query(
            cur,
            f"""
            SELECT COUNT(DISTINCT device_uuid)
            FROM api_events
            WHERE host = ? AND {event_clause} AND device_uuid IS NOT NULL AND device_uuid != ''
            """,
            (metrics_host, *event_params),
        )

    runtime_snapshot = get_runtime_metrics()
    average_incidents_per_day = (
        round(total_incidents / tracked_days, 1) if tracked_days else 0.0
    )
    scrape_health_status = _scrape_health_status(runtime_snapshot["scrapeFreshnessSeconds"])
    public_site_health = _probe_url(f"{TRAFFIC_APP_PUBLIC_URL}/")
    public_api_health = _probe_url(f"{TRAFFIC_APP_PUBLIC_URL}/api/healthz")

    payload = {
        "rangeKey": range_key,
        "rangeLabel": range_label,
        "totalIncidentsIngested": total_incidents,
        "activeIncidents": active_incidents,
        "incidentsInRange": incidents_in_range,
        "averageIncidentsPerDay": average_incidents_per_day,
        "trafficAppRequestsInRange": traffic_app_requests_in_range,
        "trafficAppUniqueVisitorsInRange": traffic_app_unique_visitors_in_range,
        "metricsPageRequestsInRange": metrics_page_requests_in_range,
        "metricsPageUniqueVisitorsInRange": metrics_page_unique_visitors_in_range,
        "commentsInRange": comments_in_range,
        "likesInRange": likes_in_range,
        "engagementActionsInRange": comments_in_range + likes_in_range,
        "apiRequestsServed": runtime_snapshot["apiRequestsServed"],
        "averageScrapeTime": runtime_snapshot["averageScrapeTime"],
        "lastSuccessfulScrape": runtime_snapshot["lastSuccessfulScrape"],
        "lastSuccessfulScrapeAt": runtime_snapshot["lastSuccessfulScrapeAt"],
        "scrapeFreshnessSeconds": runtime_snapshot["scrapeFreshnessSeconds"],
        "scrapeHealthStatus": scrape_health_status,
        "requestsPerMinute": runtime_snapshot["requestsPerMinute"],
        "requestsLastMinute": runtime_snapshot["requestsLastMinute"],
        "requestsLastFiveMinutes": runtime_snapshot["requestsLastFiveMinutes"],
        "requestsLastHour": runtime_snapshot["requestsLastHour"],
        "processStartedAt": runtime_snapshot["processStartedAt"],
        "processUptimeSeconds": runtime_snapshot["processUptimeSeconds"],
        "publicSiteHealth": public_site_health,
        "publicApiHealth": public_api_health,
        "generatedAt": now.isoformat(),
    }
    response = jsonify(payload)
    return _finalize_api_response(response, device_uuid, "dashboard_metrics")


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
            cur.execute("SELECT 1 FROM incidents WHERE incident_no = ?", (incident_id,))
            if not cur.fetchone():
                abort(404, description="Incident not found")
            if request.method == "DELETE":
                cur.execute("DELETE FROM likes WHERE incident_no = ? AND device_uuid = ?",
                            (incident_id, device_uuid))
                if cur.rowcount:
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
    return _finalize_api_response(response, device_uuid, "incident_like", request_type="write")


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

    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1 FROM incidents WHERE incident_no = ?", (incident_id,))
                if not cur.fetchone():
                    abort(404, description="Incident not found")

                cur.execute(
                    "SELECT COUNT(*) FROM comments WHERE incident_no = ? AND device_uuid = ?",
                    (incident_id, device_uuid),
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
    return _finalize_api_response(response, device_uuid, "incident_comment", request_type="write")


# ---------------------------------------------------------------------------
# User identity
# ---------------------------------------------------------------------------

@app.route("/api/user/check", methods=["GET"])
def check_user():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    device_uuid = _get_or_create_uuid(request)
    response = jsonify({"uuid": device_uuid})
    return _finalize_api_response(response, device_uuid, "user_check")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/api/healthz", methods=["GET"])
def healthz():
    _enforce_rate_limit("read", API_READ_RATE_LIMIT)
    runtime_snapshot = get_runtime_metrics()
    return jsonify(
        {
            "ok": True,
            "generatedAt": now_pst().isoformat(),
            "lastSuccessfulScrapeAt": runtime_snapshot["lastSuccessfulScrapeAt"],
            "scrapeHealthStatus": _scrape_health_status(runtime_snapshot["scrapeFreshnessSeconds"]),
        }
    )


# ---------------------------------------------------------------------------
# SPA catch-all
# ---------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_app(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        max_age = STATIC_ASSET_MAX_AGE_SECONDS if path.startswith(("assets/", "map_tiles/")) else None
        return send_from_directory(app.static_folder, path, max_age=max_age)
    return send_from_directory(app.static_folder, "index.html", max_age=0)
