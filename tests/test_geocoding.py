import os
import tempfile
import unittest

from backend.geocoding import (
    GeocodingCache,
    _build_query_variations,
    expand_abbreviations,
    is_in_san_diego,
    normalize_street,
)


class StreetNormalizationTests(unittest.TestCase):
    def test_normalize_street(self):
        cases = {
            "BLOCK 4500 UNIVERSITY AVE": "4500 UNIVERSITY AVE",
            "04th St": "4th St",
            "0123 Main St": "123 Main St",
            "  multiple   spaces  ": "multiple spaces",
            "Main St / 5th Ave": "Main St and 5th Ave",
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(normalize_street(raw_value), expected)

    def test_expand_abbreviations(self):
        cases = {
            "Main St": "Main Street",
            "5th Ave": "5th Avenue",
            "Ocean Blvd": "Ocean Boulevard",
            "Harbor Dr": "Harbor Drive",
        }
        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(expand_abbreviations(raw_value), expected)

    def test_san_diego_bounds(self):
        self.assertTrue(is_in_san_diego(32.7157, -117.1611))
        self.assertTrue(is_in_san_diego(33.1425, -117.2297))
        self.assertFalse(is_in_san_diego(34.0522, -118.2437))
        self.assertFalse(is_in_san_diego(33.5, -117.0))

    def test_query_variations_are_bounded_and_unique(self):
        variations = _build_query_variations("University Ave and 30th St")
        queries = [query for query, _ in variations]
        self.assertLessEqual(len(queries), 6)
        self.assertEqual(len(queries), len(set(queries)))
        self.assertTrue(all("San Diego, CA" in query for query in queries))


class GeocodingCacheTests(unittest.TestCase):
    def test_forward_and_reverse_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = GeocodingCache(os.path.join(temp_dir, "geocoding.db"))
            cache.set("Test Street, San Diego, CA", 32.7157, -117.1611, "street")
            cache.set_reverse(
                32.7157,
                -117.1611,
                {"road": "Test Street", "city": "San Diego"},
            )

            self.assertEqual(
                cache.get("Test Street, San Diego, CA"),
                {
                    "Latitude": 32.7157,
                    "Longitude": -117.1611,
                    "precision": "street",
                },
            )
            self.assertEqual(
                cache.get_reverse(32.7157, -117.1611),
                {"road": "Test Street", "city": "San Diego"},
            )
            self.assertIsNone(cache.get("Missing Street, San Diego, CA"))


if __name__ == "__main__":
    unittest.main()
