"""Lightweight runtime metrics for the traffic app."""

from __future__ import annotations

import threading
import time
from collections import deque

from .config import now_pst


_lock = threading.Lock()
_api_requests_served = 0
_api_request_timestamps = deque()
_scrape_samples = 0
_scrape_total_seconds = 0.0
_last_successful_scrape_at = None
_last_successful_scrape_monotonic = None
_process_started_at = now_pst().isoformat()
_process_started_monotonic = time.monotonic()


def _prune_request_timestamps(now_ts):
    cutoff = now_ts - 3600
    while _api_request_timestamps and _api_request_timestamps[0] < cutoff:
        _api_request_timestamps.popleft()


def record_api_request():
    """Count one API request served by the Flask app."""
    global _api_requests_served

    now_ts = time.monotonic()
    with _lock:
        _api_requests_served += 1
        _api_request_timestamps.append(now_ts)
        _prune_request_timestamps(now_ts)


def record_scrape_success(duration_seconds):
    """Track a successful scrape cycle and its duration."""
    global _scrape_samples, _scrape_total_seconds
    global _last_successful_scrape_at, _last_successful_scrape_monotonic

    with _lock:
        _scrape_samples += 1
        _scrape_total_seconds += max(float(duration_seconds), 0.0)
        _last_successful_scrape_at = now_pst().isoformat()
        _last_successful_scrape_monotonic = time.monotonic()


def _format_elapsed(delta_seconds):
    delta_seconds = max(int(delta_seconds), 0)
    if delta_seconds < 60:
        return f"{delta_seconds} seconds ago"
    minutes, _ = divmod(delta_seconds, 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        if minutes:
            return (
                f"{hours} hour{'s' if hours != 1 else ''}, "
                f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            )
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days, hours = divmod(hours, 24)
    if hours:
        return (
            f"{days} day{'s' if days != 1 else ''}, "
            f"{hours} hour{'s' if hours != 1 else ''} ago"
        )
    return f"{days} day{'s' if days != 1 else ''} ago"


def _recent_request_counts(now_ts):
    requests_last_minute = sum(
        1 for timestamp in _api_request_timestamps if now_ts - timestamp <= 60
    )
    requests_last_five_minutes = sum(
        1 for timestamp in _api_request_timestamps if now_ts - timestamp <= 300
    )
    requests_last_hour = len(_api_request_timestamps)
    rpm = requests_last_five_minutes / 5 if requests_last_five_minutes else 0.0
    return requests_last_minute, requests_last_five_minutes, requests_last_hour, rpm


def get_runtime_metrics():
    """Return a snapshot of in-memory runtime metrics."""
    now_ts = time.monotonic()
    with _lock:
        _prune_request_timestamps(now_ts)
        average_scrape_time = (
            _scrape_total_seconds / _scrape_samples if _scrape_samples else 0.0
        )
        last_successful_scrape_at = _last_successful_scrape_at
        last_successful_scrape_monotonic = _last_successful_scrape_monotonic
        api_requests_served = _api_requests_served
        process_started_at = _process_started_at
        recent_counts = _recent_request_counts(now_ts)

    last_successful_scrape = "No successful scrape yet"
    scrape_freshness_seconds = None
    if last_successful_scrape_monotonic is not None:
        scrape_freshness_seconds = max(
            int(now_ts - last_successful_scrape_monotonic),
            0,
        )
        last_successful_scrape = _format_elapsed(scrape_freshness_seconds)

    process_uptime_seconds = max(int(now_ts - _process_started_monotonic), 0)
    (
        requests_last_minute,
        requests_last_five_minutes,
        requests_last_hour,
        requests_per_minute,
    ) = recent_counts

    return {
        "apiRequestsServed": api_requests_served,
        "averageScrapeTime": round(average_scrape_time, 1),
        "lastSuccessfulScrape": last_successful_scrape,
        "lastSuccessfulScrapeAt": last_successful_scrape_at,
        "scrapeFreshnessSeconds": scrape_freshness_seconds,
        "requestsLastMinute": requests_last_minute,
        "requestsLastFiveMinutes": requests_last_five_minutes,
        "requestsLastHour": requests_last_hour,
        "requestsPerMinute": round(requests_per_minute, 1),
        "processStartedAt": process_started_at,
        "processUptimeSeconds": process_uptime_seconds,
    }
