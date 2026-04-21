"""
Test script for the new geocoding module.
Tests normalization, caching, bounding box validation, and precision labeling.
"""

import os
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from geocoding import (
    normalize_street, 
    expand_abbreviations, 
    is_in_san_diego, 
    GeocodingCache, 
    geocode_location,
    _build_query_variations
)

DB_FILE = os.path.join(os.path.dirname(__file__), "traffic_data.db")

def test_normalize_street():
    """Test street normalization."""
    print("\n=== Testing normalize_street() ===")
    
    test_cases = [
        ("BLOCK 4500 UNIVERSITY AVE", "4500 UNIVERSITY AVE"),
        ("04th St", "4th St"),
        ("0123 Main St", "123 Main St"),
        ("  multiple   spaces  ", "multiple spaces"),
        ("Main St / 5th Ave", "Main St and 5th Ave"),
    ]
    
    for input_str, expected in test_cases:
        result = normalize_street(input_str)
        status = "✓" if result == expected else "✗"
        print(f"  {status} normalize_street('{input_str}') = '{result}' (expected: '{expected}')")

def test_expand_abbreviations():
    """Test abbreviation expansion."""
    print("\n=== Testing expand_abbreviations() ===")
    
    test_cases = [
        ("Main St", "Main Street"),
        ("5th Ave", "5th Avenue"),
        ("Ocean Blvd", "Ocean Boulevard"),
        ("Harbor Dr", "Harbor Drive"),
    ]
    
    for input_str, expected in test_cases:
        result = expand_abbreviations(input_str)
        status = "✓" if result == expected else "✗"
        print(f"  {status} expand_abbreviations('{input_str}') = '{result}' (expected: '{expected}')")

def test_bounding_box():
    """Test San Diego bounding box validation."""
    print("\n=== Testing is_in_san_diego() ===")
    
    test_cases = [
        (32.7157, -117.1611, True, "Downtown San Diego"),
        (32.7627, -117.2320, True, "La Jolla"),
        (32.5411, -117.0361, True, "Imperial Beach"),
        (33.1425, -117.2297, True, "Carlsbad (border)"),
        (34.0522, -118.2437, False, "Los Angeles"),
        (33.5, -117.0, False, "Inland/Riverside area"),
    ]
    
    for lat, lon, expected, desc in test_cases:
        result = is_in_san_diego(lat, lon)
        status = "✓" if result == expected else "✗"
        print(f"  {status} is_in_san_diego({lat}, {lon}) = {result} (expected: {expected}) [{desc}]")

def test_query_variations():
    """Test query variation generation."""
    print("\n=== Testing _build_query_variations() ===")
    
    test_cases = [
        "University Ave and 30th St",
        "4500 BLOCK UNIVERSITY AVE",
        "Main St",
    ]
    
    for query in test_cases:
        variations = _build_query_variations(query)
        print(f"\n  Query: '{query}'")
        print(f"  Variations ({len(variations)}):")
        for q, precision in variations:
            print(f"    - [{precision}] {q}")

def test_cache():
    """Test geocoding cache."""
    print("\n=== Testing GeocodingCache ===")
    
    cache = GeocodingCache(DB_FILE)
    
    # Test set and get
    test_query = "Test Street, San Diego, CA"
    cache.set(test_query, 32.7157, -117.1611, "street")
    
    result = cache.get(test_query)
    if result:
        print(f"  ✓ Cache set/get works: {result}")
    else:
        print("  ✗ Cache set/get failed")
    
    # Test cache miss
    miss_result = cache.get("Nonexistent Street, CA")
    if miss_result is None:
        print("  ✓ Cache miss correctly returns None")
    else:
        print("  ✗ Cache miss should return None")

def test_geocode_live():
    """Test live geocoding (optional - makes API calls)."""
    print("\n=== Testing geocode_location() (LIVE) ===")
    print("  Note: This makes live Nominatim API calls")
    
    cache = GeocodingCache(DB_FILE)
    
    test_addresses = [
        "University Ave and 30th St, San Diego, CA",
        "3900 BLOCK UNIVERSITY AVE",
    ]
    
    for addr in test_addresses:
        print(f"\n  Geocoding: '{addr}'")
        result = geocode_location(addr, cache=cache)
        if result:
            print(f"    ✓ Result: ({result['Latitude']:.4f}, {result['Longitude']:.4f}) [precision={result['precision']}]")
        else:
            print("    ✗ No result")

if __name__ == "__main__":
    print("=" * 60)
    print("GEOCODING MODULE TEST SUITE")
    print("=" * 60)
    
    test_normalize_street()
    test_expand_abbreviations()
    test_bounding_box()
    test_query_variations()
    test_cache()
    
    # Ask before running live tests
    print("\n" + "=" * 60)
    response = input("Run live geocoding tests? (y/n): ").strip().lower()
    if response == 'y':
        test_geocode_live()
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
