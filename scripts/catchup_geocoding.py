import sqlite3
import os
import sys
import threading
import json
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor, as_completed

# Project root is one directory above scripts/ — needed for imports and paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Import shared geocoding module (lives at project root)
from geocoding import GeocodingCache, geocode_location  # noqa: E402
DB_FILE = os.path.join(PROJECT_ROOT, "traffic_data.db")

# Initialize shared geocoding cache
geo_cache = GeocodingCache(DB_FILE)

db_lock = threading.Lock()

def process_incident(row):
    incident_no = row['incident_no']
    source = row['source']
    location_str = row['location']
    
    details = json.loads(row['details']) if row['details'] else []
    
    # Build query based on source
    query = ""
    if source == "SDPD":
        query = f"{location_str}, San Diego, CA"
    elif source == "SDFD":
        cross = ""
        for d in details:
            if "Cross Street:" in d:
                cross = d.replace("Cross Street:", "").strip()
                break
        if cross and cross != "N/A":
            query = f"{location_str} and {cross}, San Diego, CA"
        else:
            query = f"{location_str}, San Diego, CA"
    
    # Use shared geocoding function with cache
    result = geocode_location(query, cache=geo_cache)
    
    if result:
        lat = result["Latitude"]
        lon = result["Longitude"]
        precision = result.get("precision", "unknown")
        
        with db_lock:
            with closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
                conn.execute(
                    """
                    UPDATE incidents
                    SET latitude = ?, longitude = ?, geocode_precision = ?
                    WHERE incident_no = ?
                    """,
                    (lat, lon, precision, incident_no),
                )
                conn.commit()
        print(f"Updated {incident_no} [precision={precision}]")
    else:
        print(f"Could not geocode {incident_no}: {query}")

def catchup():
    with closing(sqlite3.connect(DB_FILE, timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT incident_no, source, location, details
            FROM incidents
            WHERE (latitude IS NULL OR longitude IS NULL)
              AND source IN ('SDPD', 'SDFD')
            """
        ).fetchall()
    
    print(f"Found {len(rows)} incidents needing geocoding.")
    
    if not rows:
        return

    # Use a thread pool to process incidents in parallel.
    # geocoding.py serializes Nominatim calls to honor its rate limit.
    max_workers = 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_incident, row) for row in rows]
        for _ in as_completed(futures):
            pass

if __name__ == "__main__":
    catchup()
