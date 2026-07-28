"""Thread-safe in-process primitives used by the backend API layer."""

import time
from collections import OrderedDict
from contextlib import contextmanager
from threading import Lock


def parse_rate_limit(limit_spec):
    """Parse strings such as ``120 per minute`` into count and seconds."""
    count_part, separator, period_part = str(limit_spec).partition(" per ")
    try:
        max_requests = max(1, int(count_part.strip()))
    except ValueError:
        max_requests = 60

    period = period_part.strip().lower() if separator else "minute"
    if period.startswith("hour"):
        window_seconds = 3600
    elif period.startswith("second"):
        window_seconds = 1
    else:
        window_seconds = 60
    return max_requests, window_seconds


class BoundedTTLCache:
    """A small least-recently-used cache with per-entry expiration."""

    def __init__(self, max_entries):
        self.max_entries = max(1, int(max_entries))
        self._entries = OrderedDict()
        self._lock = Lock()

    def get(self, key):
        now = time.monotonic()
        with self._lock:
            cached = self._entries.get(key)
            if cached is None:
                return None
            expires_at, payload = cached
            if expires_at <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return payload

    def set(self, key, payload, ttl):
        now = time.monotonic()
        with self._lock:
            expired = [
                cache_key
                for cache_key, (expires_at, _) in self._entries.items()
                if expires_at <= now
            ]
            for cache_key in expired:
                self._entries.pop(cache_key, None)

            self._entries[key] = (now + max(0, ttl), payload)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self):
        with self._lock:
            self._entries.clear()


class RateLimiter:
    """A bounded, thread-safe sliding-window request limiter."""

    def __init__(self, max_buckets):
        self.max_buckets = max(1, int(max_buckets))
        self._hits = OrderedDict()
        self._lock = Lock()

    def allow(self, client_key, bucket, limit_spec):
        max_requests, window_seconds = parse_rate_limit(limit_spec)
        now = time.monotonic()
        key = (client_key, bucket)

        with self._lock:
            window = [
                hit_at
                for hit_at in self._hits.get(key, ())
                if now - hit_at < window_seconds
            ]
            allowed = len(window) < max_requests
            if allowed:
                window.append(now)
            self._hits[key] = window
            self._hits.move_to_end(key)

            stale_before = now - 3600
            stale_keys = [
                stored_key
                for stored_key, hits in self._hits.items()
                if not hits or hits[-1] <= stale_before
            ]
            for stored_key in stale_keys:
                self._hits.pop(stored_key, None)
            while len(self._hits) > self.max_buckets:
                self._hits.popitem(last=False)

            return allowed


class KeyedLockPool:
    """Provide per-key locks and discard them when no caller still needs them."""

    def __init__(self):
        self._entries = {}
        self._guard = Lock()

    @contextmanager
    def hold(self, key):
        with self._guard:
            lock, users = self._entries.get(key, (Lock(), 0))
            self._entries[key] = (lock, users + 1)

        lock.acquire()
        try:
            yield
        finally:
            lock.release()
            with self._guard:
                stored_lock, users = self._entries[key]
                if users == 1:
                    self._entries.pop(key, None)
                else:
                    self._entries[key] = (stored_lock, users - 1)
