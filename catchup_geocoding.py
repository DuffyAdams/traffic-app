import sqlite3
import os
import sys
import subprocess
import threading
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import shared geocoding module
from geocoding import GeocodingCache, geocode_location, normalize_street

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "traffic_data.db")
TARGET_DIR = os.path.join(BASE_DIR, "traffic-app", "maps")
MAP_GENERATOR = os.path.join(BASE_DIR, "generate_map.py")

# Initialize shared geocoding cache
geo_cache = GeocodingCache(DB_FILE)

def run_map_generator(incident_no, lat, lon):
    filename_date_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = os.path.join(TARGET_DIR, f"map_{incident_no}_{filename_date_str}.png")
    cmd = [sys.executable, MAP_GENERATOR, str(lon), str(lat), filename]
    try:
        subprocess.run(cmd, check=True)
        return os.path.basename(filename)
    except Exception as e:
        print(f"Map gen error: {e}")
    return None


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
        
        map_file = run_map_generator(incident_no, lat, lon)
        if map_file:
            with db_lock:
                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                    conn.execute("""
                        UPDATE incidents 
                        SET latitude = ?, longitude = ?, map_filename = ?, geocode_precision = ? 
                        WHERE incident_no = ?
                    """, (lat, lon, map_file, precision, incident_no))
                    conn.commit()
            print(f"Updated {incident_no} [precision={precision}]")
    else:
        print(f"Could not geocode {incident_no}: {query}")

def catchup():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Find incidents needing geocoding (SDPD, SDFD sources)
    cur.execute("""
        SELECT incident_no, source, location, details 
        FROM incidents 
        WHERE (latitude IS NULL OR map_filename IS NULL OR map_filename = '') 
        AND source IN ('SDPD', 'SDFD')
    """)
    rows = cur.fetchall()
    conn.close()
    
    print(f"Found {len(rows)} incidents needing geocoding.")
    
    if not rows:
        return

    # Use a thread pool to process incidents in parallel.
    # We use multiple threads to allow map generation and geocoding to overlap.
    # geocoding.py handles the Nominatim rate limit internally.
    max_workers = 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_incident, row) for row in rows]
        for _ in as_completed(futures):
            pass

if __name__ == "__main__":
    catchup()
