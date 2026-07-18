import unittest
from unittest.mock import patch

from api_support import BoundedTTLCache, RateLimiter, parse_rate_limit


class ApiSupportTests(unittest.TestCase):
    def test_parse_rate_limit(self):
        self.assertEqual(parse_rate_limit("20 per second"), (20, 1))
        self.assertEqual(parse_rate_limit("120 per minute"), (120, 60))
        self.assertEqual(parse_rate_limit("10 per hour"), (10, 3600))

    def test_ttl_cache_expires_and_evicts_least_recently_used_entry(self):
        cache = BoundedTTLCache(max_entries=2)
        with patch("api_support.time.monotonic", return_value=10):
            cache.set("a", 1, ttl=5)
            cache.set("b", 2, ttl=5)
            self.assertEqual(cache.get("a"), 1)
            cache.set("c", 3, ttl=5)
            self.assertIsNone(cache.get("b"))

        with patch("api_support.time.monotonic", return_value=16):
            self.assertIsNone(cache.get("a"))
            self.assertIsNone(cache.get("c"))

    def test_rate_limiter_enforces_window(self):
        limiter = RateLimiter(max_buckets=10)
        with patch("api_support.time.monotonic", side_effect=[0, 0.1, 0.2, 61]):
            self.assertTrue(limiter.allow("client", "read", "2 per minute"))
            self.assertTrue(limiter.allow("client", "read", "2 per minute"))
            self.assertFalse(limiter.allow("client", "read", "2 per minute"))
            self.assertTrue(limiter.allow("client", "read", "2 per minute"))


if __name__ == "__main__":
    unittest.main()
