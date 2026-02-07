# geocoding.py
"""
Geocoding module for traffic scraper.
Provides normalized street handling, SQLite caching, and San Diego bounding box validation.
"""

import re
import time
import hashlib
import sqlite3
import threading
from typing import Optional, Dict, Tuple
from geopy.geocoders import Nominatim

# Thread lock for cache operations
_cache_lock = threading.Lock()

# Thread lock and timing for Nominatim rate limiting
_nominatim_lock = threading.Lock()
_last_request_time = 0

# San Diego bounding box (approximate metro area)
SD_BOUNDS = {
    "min_lat": 32.5,
    "max_lat": 33.3,
    "min_lon": -117.6,
    "max_lon": -116.9
}

# Abbreviation expansion map
ABBREVIATIONS = {
    r"\bSt\b": "Street",
    r"\bAve\b": "Avenue",
    r"\bBlvd\b": "Boulevard",
    r"\bPky\b": "Parkway",
    r"\bPkwy\b": "Parkway",
    r"\bDr\b": "Drive",
    r"\bRd\b": "Road",
    r"\bLn\b": "Lane",
    r"\bCt\b": "Court",
    r"\bPl\b": "Place",
    r"\bHwy\b": "Highway",
    r"\bFwy\b": "Freeway",
    r"\bCir\b": "Circle",
    r"\bTer\b": "Terrace",
    r"\bWy\b": "Way",
}


def normalize_street(street: str) -> str:
    """
    Normalize a street string for consistent geocoding.
    - Removes 'BLOCK' prefix
    - Removes leading zeros from numbers (04th -> 4th)
    - Collapses whitespace
    - Converts slashes to 'and'
    """
    if not street:
        return ""
    
    result = street.strip()
    
    # Remove "BLOCK" prefix (common in SDFD/SDPD)
    result = re.sub(r'\bBLOCK\s+', '', result, flags=re.IGNORECASE)
    
    # Replace slashes with " and "
    result = result.replace("/", " and ")
    
    # Remove leading zeros from numbers: "04th" -> "4th", "0123 Main" -> "123 Main"
    result = re.sub(r'\b0+(\d+)', r'\1', result)
    
    # Collapse multiple whitespace
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result


def expand_abbreviations(street: str) -> str:
    """Expand common street abbreviations to full words."""
    result = street
    for pattern, replacement in ABBREVIATIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def is_in_san_diego(lat: float, lon: float) -> bool:
    """Check if coordinates are within San Diego metro bounding box."""
    return (
        SD_BOUNDS["min_lat"] <= lat <= SD_BOUNDS["max_lat"] and
        SD_BOUNDS["min_lon"] <= lon <= SD_BOUNDS["max_lon"]
    )


def _query_hash(query: str) -> str:
    """Generate a hash for a normalized query string."""
    normalized = query.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()


class GeocodingCache:
    """SQLite-based cache for geocoding results."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_table()
    
    def _init_table(self):
        """Create cache tables if they don't exist."""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT,
                    latitude REAL,
                    longitude REAL,
                    precision TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_geocode_cache_query ON geocode_cache(query)")
            
            # Table for reverse geocoding results
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reverse_geocode_cache (
                    coords_hash TEXT PRIMARY KEY,
                    latitude REAL,
                    longitude REAL,
                    address_json TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()
    
    def get(self, query: str) -> Optional[Dict]:
        """
        Look up a cached geocoding result.
        Returns dict with lat, lon, precision or None if not cached.
        """
        qhash = _query_hash(query)
        with _cache_lock:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT latitude, longitude, precision FROM geocode_cache WHERE query_hash = ?",
                    (qhash,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "Latitude": row["latitude"],
                        "Longitude": row["longitude"],
                        "precision": row["precision"]
                    }
        return None

    def get_reverse(self, lat: float, lon: float) -> Optional[Dict]:
        """Look up a cached reverse geocoding result."""
        # Use truncated coordinates for cache key to handle minor floating point diffs
        coords_str = f"{lat:.5f},{lon:.5f}"
        chash = hashlib.md5(coords_str.encode()).hexdigest()
        
        with _cache_lock:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT address_json FROM reverse_geocode_cache WHERE coords_hash = ?",
                    (chash,)
                )
                row = cur.fetchone()
                if row:
                    import json
                    return json.loads(row["address_json"])
        return None
    
    def set_reverse(self, lat: float, lon: float, address: Dict):
        """Store a reverse geocoding result in cache."""
        coords_str = f"{lat:.5f},{lon:.5f}"
        chash = hashlib.md5(coords_str.encode()).hexdigest()
        from datetime import datetime
        import json
        now = datetime.now().isoformat()
        
        with _cache_lock:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reverse_geocode_cache 
                    (coords_hash, latitude, longitude, address_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chash, lat, lon, json.dumps(address), now)
                )
                conn.commit()
    
    def set(self, query: str, lat: float, lon: float, precision: str):
        """Store a geocoding result in cache."""
        qhash = _query_hash(query)
        from datetime import datetime
        now = datetime.now().isoformat()
        
        with _cache_lock:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO geocode_cache 
                    (query_hash, query, latitude, longitude, precision, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (qhash, query, lat, lon, precision, now)
                )
                conn.commit()


def _build_query_variations(location_query: str) -> list:
    """
    Build a limited set of query variations to try.
    Returns list of (query_string, precision_label) tuples.
    """
    city_suffix = ", San Diego, CA"
    
    # Normalize the input
    clean_q = normalize_street(location_query)
    
    # Remove any existing city suffix to avoid duplication
    clean_q = clean_q.replace(", San Diego, CA", "").replace(", San Diego County, CA", "").strip()
    
    variations = []
    
    # Check if this is an intersection
    if " and " in clean_q.lower():
        # Split on " and " (case-insensitive)
        parts = re.split(r'\s+and\s+', clean_q, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) >= 2:
            p1, p2 = parts[0], parts[1]
            
            # Try intersection formats (limit to 4 intersection attempts)
            variations.append((f"{p1} & {p2}{city_suffix}", "intersection"))
            variations.append((f"{p2} & {p1}{city_suffix}", "intersection"))
            
            # Expanded versions
            p1_exp = expand_abbreviations(p1)
            p2_exp = expand_abbreviations(p2)
            if p1_exp != p1 or p2_exp != p2:
                variations.append((f"{p1_exp} & {p2_exp}{city_suffix}", "intersection"))
            
            # Fall back to main street only (labeled as approximate)
            variations.append((f"{p1}{city_suffix}", "approximate"))
            variations.append((f"{p1_exp}{city_suffix}", "approximate"))
    else:
        # Single address
        variations.append((f"{clean_q}{city_suffix}", "street"))
        
        # Try expanded version
        expanded = expand_abbreviations(clean_q)
        if expanded != clean_q:
            variations.append((f"{expanded}{city_suffix}", "street"))
        
        # If there's a house number, try without it
        street_only = re.sub(r'^\d+\s+', '', clean_q)
        if street_only != clean_q:
            variations.append((f"{street_only}{city_suffix}", "approximate"))
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q, precision in variations:
        if q not in seen:
            seen.add(q)
            unique.append((q, precision))
    
    return unique[:6]  # Limit to max 6 attempts


def geocode_location(
    location_query: str,
    cache: Optional[GeocodingCache] = None,
    debug_print=None
) -> Optional[Dict]:
    """
    Geocode a location string into coordinates.
    
    Args:
        location_query: The address/intersection to geocode
        cache: Optional GeocodingCache instance for caching
        debug_print: Optional function for debug output (defaults to print)
    
    Returns:
        Dict with Latitude, Longitude, and precision keys, or None if not found.
        precision: "intersection" | "street" | "approximate"
    """
    if debug_print is None:
        debug_print = print
    
    if not location_query:
        return None
    
    # Normalize the query first
    normalized = normalize_street(location_query)
    
    # Check cache first
    if cache:
        cached = cache.get(normalized)
        if cached:
            debug_print(f"CACHE HIT: '{normalized}' -> ({cached['Latitude']}, {cached['Longitude']})")
            return cached
    
    # Build query variations
    variations = _build_query_variations(location_query)
    
    geolocator = Nominatim(user_agent="traffic_scraper_geocoder", timeout=10)
    
    for query, precision in variations:
        try:
            debug_print(f"GEOCODE: Trying '{query}'")
            
            # Global rate limiting for Nominatim
            with _nominatim_lock:
                global _last_request_time
                elapsed = time.time() - _last_request_time
                if elapsed < 1.1:
                    time.sleep(1.1 - elapsed)
                
                location = geolocator.geocode(query, addressdetails=True)
                _last_request_time = time.time()
            
            if location:
                lat, lon = location.latitude, location.longitude
                
                # Validate: must be in San Diego bounding box
                if not is_in_san_diego(lat, lon):
                    debug_print(f"GEOCODE: Rejected '{query}' - outside San Diego bounds ({lat}, {lon})")
                    continue
                
                # Also validate address string contains California or San Diego
                addr = location.address or ""
                if "California" not in addr and "San Diego" not in addr:
                    debug_print(f"GEOCODE: Rejected '{query}' - address doesn't mention CA/SD: {addr[:80]}")
                    continue
                
                debug_print(f"GEOCODE: Success '{query}' -> ({lat}, {lon}) [precision={precision}]")
                
                result = {
                    "Latitude": lat,
                    "Longitude": lon,
                    "precision": precision
                }
                
                # Cache the result
                if cache:
                    cache.set(normalized, lat, lon, precision)
                
                return result
                
        except Exception as e:
            debug_print(f"GEOCODE: Error for '{query}': {e}")
    
    debug_print(f"GEOCODE: All attempts failed for '{location_query}'")
    return None


# Convenience function for reverse geocoding (unchanged logic)
def reverse_geocode(lat: float, lon: float, cache: Optional[GeocodingCache] = None, debug_print=None) -> Optional[Dict]:
    """Reverse geocode coordinates to get address info."""
    if debug_print is None:
        debug_print = print
    
    if cache:
        cached = cache.get_reverse(lat, lon)
        if cached:
            debug_print(f"REVERSE CACHE HIT: ({lat}, {lon})")
            return cached
    
    try:
        geolocator = Nominatim(user_agent="traffic_scraper_reverse_geocoder", timeout=10)
        
        # Global rate limiting for Nominatim
        with _nominatim_lock:
            global _last_request_time
            elapsed = time.time() - _last_request_time
            if elapsed < 1.1:
                time.sleep(1.1 - elapsed)
            
            location = geolocator.reverse((lat, lon), exactly_one=True)
            _last_request_time = time.time()
            
        if location and location.raw.get("address"):
            address = location.raw.get("address")
            if cache:
                cache.set_reverse(lat, lon, address)
            return address
        return None
    except Exception as e:
        debug_print(f"Reverse geocoding error: {e}")
        return None
