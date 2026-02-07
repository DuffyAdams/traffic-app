# traffic_scraper.py
import os
import re
import sys
import json
import time
import uuid
import sqlite3
import subprocess
import threading
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Database lock for thread safety
db_lock = threading.Lock()
# Print lock for thread-safe logging
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    """Thread-safe print function."""
    with print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()

import requests
from bs4 import BeautifulSoup
import pytz
from flask import Flask, jsonify, send_from_directory, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

# Import geocoding module
from geocoding import GeocodingCache, geocode_location as geo_geocode_location, reverse_geocode

# -----------------------------------
# Configuration and Setup
# -----------------------------------
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR = os.path.join(BASE_DIR, "traffic-app", "maps")
DB_FILE = os.path.join(BASE_DIR, "traffic_data.db")
MAP_GENERATOR = os.path.join(BASE_DIR, "generate_map.py")

os.makedirs(TARGET_DIR, exist_ok=True)

# Initialize geocoding cache
geo_cache = GeocodingCache(DB_FILE)

# Retrieve the API key from the environment
GPT_KEY = os.getenv("GPT_KEY")

# Check if the API key is loaded correctly
#if not GPT_KEY:
#    raise ValueError("GPT_KEY not found in environment variables. Ensure it is set in the .env file.")

# Initialize the OpenAI client with the API key
client = OpenAI(api_key=GPT_KEY)

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}
PARAMS = {"ddlComCenter": "BCCC"}
CHP_SCRAPE_URL = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"
SDPD_SCRAPE_URL = "https://webapps.sandiego.gov/sdpdonline"
SDFD_API_URL = "https://webapps.sandiego.gov/SDFireDispatch/api/v1/Incidents"
HEALTHCHECK_URL = "https://hc-ping.com/7299c402-d91d-4d89-8f84-5e6b510631c0"

# Regex patterns
VIEWSTATE_PATTERN = re.compile(
    r'<input\s+type="hidden"\s+name="__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]+)"\s*/?>'
)
LAT_LON_PATTERN = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
BRACKETS_PATTERN = re.compile(r"\[.*?\]")
EXCLUDED_DETAILS = {"Unit At Scene", "Unit Enroute", "Unit Assigned"}

# Cookie settings
COOKIE_NAME = "traffic_app_uuid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year

# Flask app setup
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "traffic-app", "dist"))
CORS(app, resources={r"/api/*": {"origins": "*"}, r"/maps/*": {"origins": "*"}})

# Test mode flag

TESTMODE = True

# -----------------------------------
# Database Functions
# -----------------------------------
def init_db():
    """Initialize SQLite database with updated schema."""
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for concurrency
        conn.execute("PRAGMA synchronous=NORMAL") # Optimized for performance
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys globally
        cur = conn.cursor()
        # Incidents table with an extra 'active' column
        cur.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_no TEXT,
                date TEXT,
                timestamp TEXT,
                city TEXT,
                neighborhood TEXT,
                location TEXT,
                location_desc TEXT,
                type TEXT,
                details TEXT,
                description TEXT,
                latitude REAL,
                longitude REAL,
                map_filename TEXT,
                likes INTEGER DEFAULT 0,
                comments TEXT DEFAULT '[]',
                active INTEGER DEFAULT 1,
                source TEXT DEFAULT 'CHP',
                PRIMARY KEY (incident_no, date)
            )
        """)
        
        # Migration: Add source column if it doesn't exist
        try:
            cur.execute("ALTER TABLE incidents ADD COLUMN source TEXT DEFAULT 'CHP'")
        except sqlite3.OperationalError:
            pass  # Column likely exists
        
        # Migration: Add geocode_precision column
        try:
            cur.execute("ALTER TABLE incidents ADD COLUMN geocode_precision TEXT DEFAULT 'unknown'")
        except sqlite3.OperationalError:
            pass  # Column likely exists
        # Likes table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                device_uuid TEXT,
                incident_no TEXT,
                timestamp TEXT,
                PRIMARY KEY (device_uuid, incident_no)
            )
        """)
        # Comments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_uuid TEXT,
                incident_no TEXT,
                username TEXT,
                comment TEXT,
                timestamp TEXT
            )
        """)
        
        # Update existing traffic collision types to standardize naming
        cur.execute("""
            UPDATE incidents
            SET type = 'Traffic Collision'
            WHERE type LIKE 'Trfc Collision%'
        """)
        
        # Standardize other incident types
        cur.execute("""
            UPDATE incidents
            SET type = 'Maintenance'
            WHERE type = 'Assist CT with Maintenance'
        """)
        
        cur.execute("""
            UPDATE incidents
            SET type = 'Road Conditions'
            WHERE type = 'Road/Weather Conditions'
        """)

        cur.execute("""
            UPDATE incidents
            SET type = 'Debris from Vehicle'
            WHERE type = 'Object Flying From Veh'
        """)
        
        cur.execute("""
            UPDATE incidents
            SET type = 'Construction'
            WHERE type = 'Assist with Construction'
        """)
        
        # Filter out "Request CalTrans Notify" types
        cur.execute("""
            DELETE FROM incidents
            WHERE type = 'Request CalTrans Notify'
        """)
        
        # Performance optimization: Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_active ON incidents(active)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_date ON incidents(date)")
        
        conn.commit()

def read_incidents(limit=20, offset=0, incident_types=None, locations=None, sources=None, active_only=False, cursor=None, date_filter=None):
    """Read a limited set of incidents from the database along with their comments."""
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = "SELECT * FROM incidents"
            params = []
            conditions = []

            if sources:
                placeholders = ",".join("?" for _ in sources)
                conditions.append(f"source IN ({placeholders})")
                params.extend(sources)

            if incident_types:
                placeholders = ",".join("?" for _ in incident_types)
                conditions.append(f"type IN ({placeholders})")
                params.extend(incident_types)

            if locations:
                placeholders = ",".join("?" for _ in locations)
                conditions.append(f"location IN ({placeholders})")
                params.extend(locations)

            if active_only:
                conditions.append("active = 1")

            if date_filter in ['day', 'daily']:
                today = datetime.now().strftime("%Y-%m-%d")
                conditions.append("date = ?")
                params.append(today)

            if cursor:
                # cursor is expected to be "timestamp|incident_no"
                if "|" in cursor:
                    ts_part, id_part = cursor.split("|", 1)
                    conditions.append("(timestamp, incident_no) < (?, ?)")
                    params.extend([ts_part, id_part])
                else:
                    # Fallback for old simple cursors
                    conditions.append("timestamp < ?")
                    params.append(cursor)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC, incident_no DESC LIMIT ?"
            params.append(limit)

            cur.execute(query, tuple(params))
            incidents = [dict(row) for row in cur.fetchall()]
            for inc in incidents:
                incident_no = inc["incident_no"]
                cur.execute(
                    "SELECT username, comment, timestamp FROM comments WHERE incident_no = ? ORDER BY timestamp ASC",
                    (incident_no,)
                )
                inc["comments"] = [
                    {"username": row[0] or "Anonymous", "comment": row[1], "timestamp": row[2]}
                    for row in cur.fetchall()
                ]
                try:
                    inc["Details"] = json.loads(inc["details"]) if inc["details"] else []
                except Exception:
                    inc["Details"] = []
            return incidents


def incident_exists(incident_no, date):
    """Check if an incident exists in the database."""
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM incidents WHERE incident_no = ? AND date = ?", (str(incident_no), date))
            return cur.fetchone() is not None


# -----------------------------------
# Google AI Helper Functions
# -----------------------------------
def load_system_prompt(filename):
    with open(filename, 'r') as file:
        return file.read().strip()

call_count = 0

def generate_description(data):
    global call_count
    call_count += 1
    safe_print("GPT API Calls:" + str(call_count))

    try:
        # Generate a tweet-friendly description using ChatGPT's GPT-4o-mini model
        prompt = (
            f"Neighborhood: {data.get('Neighborhood')}\n"
            f"Location: {data.get('Location')} - {data.get('Location Desc.')}\n"
            f"Type: {data.get('Type')}\n"
            f"Details: {', '.join(data.get('Details', []))}"
        )

        system_prompt = (
            "Provide a factual, tweet-length summary using the details given. "
            "Do not add any warnings, advice, hashtags, or extra commentary. "
            "Keep the summary under 200 characters. Add related emojis."
        )

        user_message = f"Summarize this traffic incident in one fluent sentence.\n{prompt}"

        if TESTMODE:  # Return the prompt for debugging in test mode
            return f"{system_prompt}\n\n{user_message}"
        else:
            response = client.chat.completions.create(
                model="gpt-5-nano-2025-08-07",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]
            )
            return response.choices[0].message.content.strip()

    except Exception as e:
        safe_print(f"Error generating description: {e}")
        return "Traffic incident reported."

# -----------------------------------
# Save or Update Incident
# -----------------------------------
def save_or_update_incident(data):
    if not data:
        return False

    incident_no = data.get("No.") or data.get("Incident No.")
    if not incident_no:
        safe_print("No incident number found in data.")
        return False

    date = data.get("Date", datetime.now().strftime("%Y-%m-%d"))
    new_timestamp = data.get("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    city = data.get("City", "")
    neighborhood = data.get("Neighborhood", "")
    location = data.get("Location", "")
    location_desc = data.get("Location Desc.", "")

    # Standardize traffic collision type
    type_field = data.get("Type", "")
    if type_field and type_field.startswith("Trfc Collision"):
        type_field = "Traffic Collision"

    new_details = data.get("Details", [])
    if isinstance(new_details, str):
        new_details = [new_details]
    details_json = json.dumps(new_details)

    latitude = data.get("Latitude")
    longitude = data.get("Longitude")
    new_map_filename = data.get("MapFilename", "")
    source = data.get("Source", "CHP")
    geocode_precision = data.get("precision", "unknown")

    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM incidents WHERE incident_no = ? AND date = ?", (str(incident_no), date))
            existing = cur.fetchone()
            if existing:
                existing_data = dict(existing)
                updates = []
                params = []
                
                # Update details and description if changed
                if details_json != existing_data.get("details", ""):
                    new_description = generate_description(data)
                    updates.append("details = ?, description = ?")
                    params.extend([details_json, new_description])
                
                # Update coordinates if missing or changed
                if latitude and latitude != existing_data.get("latitude"):
                    updates.append("latitude = ?")
                    params.append(latitude)
                if longitude and longitude != existing_data.get("longitude"):
                    updates.append("longitude = ?")
                    params.append(longitude)
                    
                # Update geocode_precision if we have a new value
                if geocode_precision != "unknown" and geocode_precision != existing_data.get("geocode_precision"):
                    updates.append("geocode_precision = ?")
                    params.append(geocode_precision)
                    
                # Update map filename if missing or changed
                if new_map_filename and new_map_filename != existing_data.get("map_filename"):
                    updates.append("map_filename = ?")
                    params.append(new_map_filename)

                if updates:
                    updates.append("active = 1")
                    query = f"UPDATE incidents SET {', '.join(updates)} WHERE incident_no = ? AND date = ?"
                    params.extend([str(incident_no), date])
                    cur.execute(query, tuple(params))
                    conn.commit()
                    safe_print(f"Incident {incident_no} updated.")
                    return True
                else:
                    safe_print(f"No changes for incident {incident_no}.")
                    return False
            else:
                # For new incidents, generate the description before inserting
                new_description = generate_description(data)
                cur.execute("""
                    INSERT INTO incidents 
                    (incident_no, date, timestamp, city, neighborhood, location, location_desc, type, details, 
                     description, latitude, longitude, map_filename, likes, comments, active, source, geocode_precision)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (str(incident_no), date, new_timestamp, city, neighborhood, location, location_desc, type_field,
                      details_json, new_description, latitude, longitude, new_map_filename, 0, '[]', source, geocode_precision))
                conn.commit()
                safe_print(f"Incident {incident_no} inserted.")
                return True


# -----------------------------------
# UUID Management
# -----------------------------------
def get_or_create_uuid(req):
    device_uuid = req.cookies.get(COOKIE_NAME)
    if not device_uuid:
        device_uuid = str(uuid.uuid4())
        safe_print(f"New UUID generated: {device_uuid}")
    else:
        safe_print(f"Reusing existing UUID: {device_uuid}")
    return device_uuid

# -----------------------------------
# Scraper Functions
# -----------------------------------
def get_viewstate(html_text):
    match = VIEWSTATE_PATTERN.search(html_text)
    return match.group(1) if match else None

def extract_traffic_info(response_text):
    matches = LAT_LON_PATTERN.findall(response_text)
    
    # Parse with BeautifulSoup to properly extract time + details
    soup = BeautifulSoup(response_text, "html.parser")
    details_table = soup.find("table", id="tblDetails")
    details = []
    
    if details_table:
        rows = details_table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                # First cell is time, last cell (colspan=6) is detail text
                time_cell = cells[0].get_text(strip=True)
                detail_cell = cells[-1].get_text(strip=True) if cells[-1].get("colspan") else ""
                
                if detail_cell and not any(excluded in detail_cell for excluded in EXCLUDED_DETAILS):
                    # Combine time with detail
                    combined = f"[{time_cell}] {detail_cell}" if time_cell else detail_cell
                    details.append(combined)
    
    if matches:
        last_valid_coords = {}
        for match in matches:
            lat_str, lon_str = match.split()
            if len(lat_str.split(".")[-1]) == 6 and len(lon_str.split(".")[-1]) == 6:
                last_valid_coords = {"Latitude": float(lat_str), "Longitude": float(lon_str), "Details": details}
        return last_valid_coords
    return {}

def geocode_location(location_query):
    """
    Geocode a location string into coordinates.
    Uses the new geocoding module with caching and bounding box validation.
    
    Returns: dict with Latitude, Longitude, precision keys, or None if not found.
    """
    return geo_geocode_location(location_query, cache=geo_cache, debug_print=safe_print)

def get_location(lat, lon):
    """Reverse geocode coordinates to get address info."""
    return reverse_geocode(lat, lon, cache=geo_cache, debug_print=safe_print)


def get_incident_details(row_index, viewstate):
    try:
        data = {
            "__LASTFOCUS": "",
            "__EVENTTARGET": "gvIncidents",
            "__EVENTARGUMENT": f"Select${row_index}",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": "B13DF00D",
            "ddlComCenter": "BCCC",
            "ddlSearches": "Choose One",
            "ddlResources": "Choose One",
            "ddlResources": "Choose One",
        }
        post_response = requests.post(CHP_SCRAPE_URL, params=PARAMS, headers=HEADERS, data=data)
        post_response.raise_for_status()
        details_data = extract_traffic_info(post_response.text)
        if details_data:
            location_info = get_location(details_data.get("Latitude"), details_data.get("Longitude"))
            if location_info:
                details_data["Neighborhood"] = location_info.get("neighbourhood", "N/A")
                details_data["City"] = location_info.get("city", "N/A")
            return details_data
        return {}
    except requests.exceptions.RequestException as e:
        safe_print(f"Network or HTTP error getting incident details for index {row_index}: {e}")
        return {}
    except Exception as e:
        safe_print(f"An unexpected error occurred getting incident details for index {row_index}: {e}")
        return {}

def scrape_chp_incidents():
    try:
        response = requests.get(CHP_SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="gvIncidents")
        if not table:
            safe_print("No incident table found.")
            return []
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = table.find_all("tr")[1:]  # Skip header row
        incidents_list = []
        viewstate = get_viewstate(response.text)
        if not viewstate:
            safe_print("No __VIEWSTATE found.")
            return []

        def process_chp_row(idx, row):
            row_data = [cell.get_text(strip=True) for cell in row.find_all("td")]
            if "Location" in headers and row_data[headers.index("Location")] == "Media Log":
                return None
            
            table_data = dict(zip(headers, row_data))
            additional_details = get_incident_details(idx, viewstate)
            if not additional_details:
                safe_print(f"WARNING: Failed to retrieve additional details for incident at index {idx}. Skipping.")
                return None

            merged_data = {**table_data, **additional_details}
            chp_time = table_data.get("Time", "")
            if chp_time:
                try:
                    now = datetime.now()
                    today_str = now.strftime("%Y-%m-%d")
                    try:
                        dt_obj = datetime.strptime(f"{today_str} {chp_time}", "%Y-%m-%d %I:%M %p")
                    except ValueError:
                        dt_obj = datetime.strptime(f"{today_str} {chp_time}", "%Y-%m-%d %H:%M")
                    
                    # If the parsed time is significantly in the future, it must be from yesterday
                    if dt_obj > now + timedelta(minutes=5):
                        dt_obj -= timedelta(days=1)

                    merged_data["Timestamp"] = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                    merged_data["Date"] = dt_obj.strftime("%Y-%m-%d")
                except Exception as e:
                    safe_print(f"Error parsing CHP time '{chp_time}': {e}")
                    now = datetime.now()
                    merged_data["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    merged_data["Date"] = now.strftime("%Y-%m-%d")
            else:
                now = datetime.now()
                merged_data["Timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
                merged_data["Date"] = now.strftime("%Y-%m-%d")

            merged_data["Source"] = "CHP"
            return merged_data

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_chp_row, idx, row) for idx, row in enumerate(rows)]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    incidents_list.append(result)

        return incidents_list
    except Exception as e:
        safe_print("Error scraping CHP incidents:", e)
        return []

def scrape_sdpd_incidents():
    safe_print("Scraping SDPD incidents...")
    try:
        # Fetch the SDPD page
        response = requests.get(SDPD_SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        table = soup.find("table", id="myDataTable")
        if not table:
            safe_print("No SDPD table found.")
            return []
            
        rows = table.find("tbody").find_all("tr")
        incidents = []
        
        headers = ["Call DateTime", "Call Type", "Division", "Neighborhood", "Block Address"]
        
        for row in rows:
            cols = [ele.text.strip() for ele in row.find_all("td")]
            if not cols:
                continue
                
            # Create a dictionary from the row
            # Columns: Call DateTime, Call Type, Division, Neighborhood, Block Address
            if len(cols) < 5:
                continue
                
            dt_str = cols[0]
            call_type = cols[1]
            division = cols[2]
            neighborhood = cols[3]
            address = cols[4]
            
            # Create a consistent ID using hash of date + address + type
            unique_str = f"{dt_str}_{address}_{call_type}"
            incident_id = "SDPD-" + hashlib.md5(unique_str.encode()).hexdigest()[:8]
            
            # Parse date
            try:
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                date_val = dt_obj.strftime("%Y-%m-%d")
                time_val = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                date_val = datetime.now().strftime("%Y-%m-%d")
                time_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            incident = {
                "No.": incident_id,
                "Date": date_val,
                "Timestamp": time_val,
                "City": "San Diego",
                "Neighborhood": neighborhood,
                "Location": address,
                "Location Desc.": division,
                "Type": call_type,
                "Details": [f"Division: {division}", f"Neighborhood: {neighborhood}"],
                "Source": "SDPD"
            }
            incidents.append(incident)
            
        safe_print(f"Found {len(incidents)} SDPD incidents.")
        return incidents
        
    except Exception as e:
        safe_print(f"Error scraping SDPD: {e}")
        return []

def scrape_sdfd_incidents():
    safe_print("Scraping SDFD incidents...")
    try:
        response = requests.get(SDFD_API_URL, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        
        incidents = []
        
        for item in data:
            # Fields: ResponseDateString, CallType, Address, CrossStreet, Units (list of objects)
            dt_str = item.get("ResponseDateString", "")
            call_type = item.get("CallType", "")
            address = item.get("Address", "")
            cross_street = item.get("CrossStreet", "")
            # Fields: ResponseDateString, CallType, Address, CrossStreet, Units (list of objects)
            dt_str = item.get("ResponseDate", "") or item.get("ResponseDateString", "")
            call_type = item.get("CallType", "")
            address = item.get("Address", "")
            cross_street = item.get("CrossStreet", "")
            units = item.get("Units", [])
            unit_codes = [u.get("Code") for u in units] if units else []
            
            # Create ID
            unique_str = f"{dt_str}_{address}_{call_type}"
            incident_id = "SDFD-" + hashlib.md5(unique_str.encode()).hexdigest()[:8]
            
             # Parse date
            try:
                # Prefer ISO format from ResponseDate: "2026-01-25T14:10:43-08:00"
                if "T" in dt_str:
                    # simplistic ISO parse: take YYYY-MM-DDTHH:MM:SS
                    dt_val = dt_str[:19]
                    dt_obj = datetime.strptime(dt_val, "%Y-%m-%dT%H:%M:%S")
                else:
                    # Fallback for "2026-01-25  14:10" (double space)
                    cleaned_str = " ".join(dt_str.split()) # Remove extra spaces
                    dt_obj = datetime.strptime(cleaned_str, "%Y-%m-%d %H:%M")
                    
                date_val = dt_obj.strftime("%Y-%m-%d")
                time_val = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                safe_print(f"Date parse error for {dt_str}: {e}")
                date_val = datetime.now().strftime("%Y-%m-%d")
                time_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Attempt flexible parsing or fallback
                date_val = datetime.now().strftime("%Y-%m-%d")
                time_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            details = []
            if cross_street:
                details.append(f"Cross Street: {cross_street}")
            if unit_codes:
                details.append(f"Units: {', '.join(unit_codes)}")

            incident = {
                "No.": incident_id,
                "Date": date_val,
                "Timestamp": time_val,
                "City": "San Diego",
                "Neighborhood": "",
                "Location": address,
                "Location Desc.": cross_street,
                "Type": call_type,
                "Details": details,
                "Source": "SDFD"
            }
            incidents.append(incident)
            
        safe_print(f"Found {len(incidents)} SDFD incidents.")
        return incidents
        
    except Exception as e:
        safe_print(f"Error scraping SDFD: {e}")
        return []


def run_map_generator(merged_data):
    if TESTMODE:
        safe_print(f"TESTMODE: Skipping map generation for {merged_data.get('No.') or merged_data.get('Incident No.', 'unknown')}")
        return
    if not os.path.exists(MAP_GENERATOR):
        safe_print(f"Map generator script not found at '{MAP_GENERATOR}'.")
        return
    try:
        lon = merged_data.get("Longitude")
        lat = merged_data.get("Latitude")
        local_timezone = pytz.timezone("America/Los_Angeles")
        incident_time = datetime.now(local_timezone)
        timestamp_str = incident_time.strftime("%Y-%m-%d %H:%M:%S")
        filename_date_str = incident_time.strftime("%Y%m%d_%H%M%S_%f")
        incident_no = merged_data.get("No.") or merged_data.get("Incident No.", "unknown")
        filename = os.path.join(TARGET_DIR, f"map_{incident_no}_{filename_date_str}.png")
        cmd = [sys.executable, MAP_GENERATOR, str(lon), str(lat), filename]
        subprocess.run(cmd, check=True)
        safe_print(f"Map generated successfully for {incident_no}.")
        merged_data["MapFilename"] = os.path.basename(filename)
    except subprocess.CalledProcessError as e:
        safe_print(f"Error running map generator for {incident_no}: {e}")
    except Exception as e:
        safe_print(f"Unexpected error in run_map_generator for {incident_no}: {e}")

def process_and_save_incident(incident):
    try:
        incident_no = incident.get("No.") or incident.get("Incident No.")
        if not incident_no:
            safe_print("WARNING: No incident number found. Skipping this entry.")
            return None
        
        inc_exists = incident_exists(incident_no, incident.get("Date", datetime.now().strftime("%Y-%m-%d")))
        
        # We geocode if:
        # 1. It's a new incident
        # 2. OR it's an existing incident but missing Latitude/Longitude/Map (one-time catch up)
        needs_geocoding = False
        if not inc_exists:
            needs_geocoding = True
        else:
            # Check if existing record is missing coordinates
            with db_lock:
                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT latitude, map_filename FROM incidents WHERE incident_no = ?", (str(incident_no),))
                    row = cur.fetchone()
                    if row and (row[0] is None or not row[1]):
                        safe_print(f"DEBUG: Incident {incident_no} exists but missing coords/map. Needs geocoding.")
                        needs_geocoding = True

        if needs_geocoding:
            safe_print(f"DEBUG: Processing geocoding for {incident_no} ({incident.get('Source')})")
            # Attempt to geocode if coordinates are missing (for SDPD/SDFD)
            if "Longitude" not in incident or "Latitude" not in incident:
                source = incident.get("Source")
                location_str = incident.get("Location", "")
                if source == "SDPD":
                    query = f"{location_str}, San Diego, CA"
                    coords = geocode_location(query)
                    if coords:
                        incident.update(coords)
                elif source == "SDFD":
                    # SDFD has explicit Address and CrossStreet in API
                    address = incident.get("Location", "")
                    cross = incident.get("Location Desc.", "")
                    
                    # If address already contains the cross street (via '&' or 'and'), don't add it again
                    if cross and cross != "N/A" and cross.lower() not in address.lower():
                        query = f"{address} and {cross}, San Diego, CA"
                    else:
                        query = f"{address}, San Diego, CA"
                    
                    coords = geocode_location(query)
                    if coords:
                        incident.update(coords)

            if "Longitude" in incident and "Latitude" in incident:
                run_map_generator(incident)
        
        save_or_update_incident(incident)
        return str(incident_no)
    except Exception as inc_e:
        safe_print(f"Error processing incident {incident.get('No.')}: {inc_e}")
        return None

def monitor_traffic_data(interval=60):
    safe_print("Starting continuous traffic monitoring...")
    safe_print(f"Data saved to: {DB_FILE}")
    safe_print(f"Map generator: {MAP_GENERATOR}")
    safe_print("Press Ctrl+C to stop.")
    try:
        while True:
            try:
                safe_print(f"Checking updates... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                all_incidents = []
                
                # Parallelize scraping of all sources
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {
                        executor.submit(scrape_chp_incidents): "CHP",
                        executor.submit(scrape_sdpd_incidents): "SDPD",
                        executor.submit(scrape_sdfd_incidents): "SDFD",
                    }
                    for future in as_completed(futures):
                        source = futures[future]
                        try:
                            incidents = future.result()
                            all_incidents.extend(incidents)
                            safe_print(f"{source}: {len(incidents)} incidents fetched")
                        except Exception as e:
                            safe_print(f"Error scraping {source}: {e}")
                
                # Process incidents in parallel
                active_incident_ids = set()
                if all_incidents:
                    # Sort to process CHP first (already has coords)
                    all_incidents.sort(key=lambda x: 0 if x.get("Source") == "CHP" else 1)
                    
                    # Use a ThreadPoolExecutor for incident processing (geocoding, maps, descriptions)
                    # We use 10 workers to allow parallel map generation and OpenAI calls.
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        process_futures = [executor.submit(process_and_save_incident, inc) for inc in all_incidents]
                        for f in as_completed(process_futures):
                            inc_id = f.result()
                            if inc_id:
                                active_incident_ids.add(inc_id)
                else:
                    safe_print("No valid data retrieved from any source.")

                # Mark incidents as inactive if they are not in the current scrape.
                with db_lock:
                    with sqlite3.connect(DB_FILE, timeout=30) as conn:
                        cur = conn.cursor()
                        if active_incident_ids:
                            placeholders = ",".join("?" for _ in active_incident_ids)
                            query = f"UPDATE incidents SET active = 0 WHERE incident_no NOT IN ({placeholders})"
                            cur.execute(query, tuple(active_incident_ids))
                        else:
                            cur.execute("UPDATE incidents SET active = 0")
                        conn.commit()

                # Ping healthcheck for success
                try:
                    requests.get(HEALTHCHECK_URL, timeout=10)
                    safe_print("Healthcheck ping: success")
                except Exception as ping_e:
                    safe_print(f"Failed to ping healthcheck success: {ping_e}")

            except Exception as e:
                safe_print(f"Error in monitoring loop: {e}")
                # Ping healthcheck for failure
                try:
                    requests.get(HEALTHCHECK_URL + "/fail", timeout=10)
                    safe_print("Healthcheck ping: failure")
                except Exception as ping_e:
                    safe_print(f"Failed to ping healthcheck failure: {ping_e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        safe_print("Monitoring stopped by user.")
    except Exception as e:
        safe_print(f"Error: {e}")
        raise

@app.route("/api/incidents")
def get_incidents():
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    cursor = request.args.get("cursor")  # New cursor parameter for cursor-based pagination
    incident_types = request.args.getlist("type") # Added to support filtering by type (list)
    locations = request.args.getlist("location") # Added to support filtering by location (list)
    sources = request.args.getlist("source") # Added to support filtering by source (SDPD, SDFD, CHP)
    active_only = request.args.get("active_only", "false").lower() == "true"
    date_filter = request.args.get("date_filter")

    # Use cursor-based pagination if cursor is provided, otherwise fall back to offset
    if cursor:
        incidents = read_incidents(limit=limit, cursor=cursor, incident_types=incident_types, locations=locations, sources=sources, active_only=active_only, date_filter=date_filter)
    else:
        incidents = read_incidents(limit=limit, offset=offset, incident_types=incident_types, locations=locations, sources=sources, active_only=active_only, date_filter=date_filter)

    response = jsonify(incidents)
    if COOKIE_NAME not in request.cookies:
        device_uuid = str(uuid.uuid4())
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
    return response

@app.route("/api/incident_stats")
def get_incident_stats():
    date_filter = request.args.get("date_filter")
    sources = request.args.getlist("source") # Added source filtering to stats

    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        cur = conn.cursor()

        # Determine date condition if filtering
        # Base query parts
        where_clauses = []
        query_params = []

        if sources:
            placeholders = ",".join("?" for _ in sources)
            where_clauses.append(f"source IN ({placeholders})")
            query_params.extend(sources)

        if date_filter == 'day':
            today = datetime.now().strftime("%Y-%m-%d")
            where_clauses.append("date = ?")
            query_params.append(today)
        elif date_filter == 'week':
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
            where_clauses.append("timestamp >= ?")
            query_params.append(week_ago)
        elif date_filter == 'month':
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            where_clauses.append("timestamp >= ?")
            query_params.append(month_ago)
        elif date_filter == 'year':
            year_ago = (datetime.now() - relativedelta(months=12)).strftime("%Y-%m-%d %H:%M:%S")
            where_clauses.append("timestamp >= ?")
            query_params.append(year_ago)

        base_where = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Helper to construct queries with specific additional conditions
        def make_query(select_part, extra_condition=None):
            clauses = where_clauses[:]
            params = query_params[:]
            if extra_condition:
                clauses.append(extra_condition)
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            return f"{select_part}{where}", params

        # Events Today
        today = datetime.now().strftime("%Y-%m-%d")
        # For 'today' stat, we specifically check date = today, regardless of date_filter in chart
        # But we must respect source filter
        today_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
        today_params = list(sources) if sources else []
        today_clauses.append("date = ?")
        today_params.append(today)
        today_where = " WHERE " + " AND ".join(today_clauses)
        cur.execute(f"SELECT COUNT(*) FROM incidents{today_where}", today_params)
        events_today = cur.fetchone()[0]

        # Events Last Hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        one_hour_ago_str = one_hour_ago.strftime("%Y-%m-%d %H:%M:%S")
        
        last_hour_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
        last_hour_params = list(sources) if sources else []
        last_hour_clauses.append("timestamp >= ?")
        last_hour_params.append(one_hour_ago_str)
        last_hour_where = " WHERE " + " AND ".join(last_hour_clauses)
        
        cur.execute(f"SELECT COUNT(*) FROM incidents{last_hour_where}", last_hour_params)
        events_last_hour = cur.fetchone()[0]

        # Active Events
        q, p = make_query("SELECT COUNT(*) FROM incidents", "active = 1") # Removed map_filename check to include all sources
        cur.execute(q, p)
        events_active = cur.fetchone()[0]

        # Total Incidents
        q, p = make_query("SELECT COUNT(*) FROM incidents")
        cur.execute(q, p)
        total_incidents = cur.fetchone()[0]

        # Incidents by Type
        q, p = make_query("SELECT type, COUNT(*) as count FROM incidents")
        q += " GROUP BY type ORDER BY count DESC"
        cur.execute(q, p)
        incidents_by_type = {row[0]: row[1] for row in cur.fetchall()}

        # Top Locations (top 10)
        q, p = make_query("SELECT location, COUNT(*) as count FROM incidents", "location IS NOT NULL AND location != ''")
        q += " GROUP BY location ORDER BY count DESC LIMIT 10"
        cur.execute(q, p)
        top_locations = {row[0]: row[1] for row in cur.fetchall()}

        # Calculate chart data based on date_filter (reusing base where clauses for source)
        if date_filter == 'year':
            monthly_data = []
            now = datetime.now()
            for i in range(12):
                months_back = 11 - i
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(months=months_back)
                month_end = month_start + relativedelta(months=1)
                month_start_str = month_start.strftime('%Y-%m-%d %H:%M:%S')
                month_end_str = month_end.strftime('%Y-%m-%d %H:%M:%S')

                # Need to construct specific query for this time range + source
                range_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
                range_params = list(sources) if sources else []
                range_clauses.append("timestamp >= ?")
                range_params.append(month_start_str)
                range_clauses.append("timestamp < ?")
                range_params.append(month_end_str)
                
                range_where = " WHERE " + " AND ".join(range_clauses)
                cur.execute(f"SELECT COUNT(*) FROM incidents{range_where}", range_params)
                monthly_data.append(cur.fetchone()[0])
            chart_data = monthly_data

        elif date_filter == 'month':
            daily_data = []
            now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            for i in range(30):
                day_start = now - timedelta(days=29-i)
                day_end = day_start + timedelta(days=1)
                day_start_str = day_start.strftime('%Y-%m-%d %H:%M:%S')
                day_end_str = day_end.strftime('%Y-%m-%d %H:%M:%S')

                range_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
                range_params = list(sources) if sources else []
                range_clauses.append("timestamp >= ?")
                range_params.append(day_start_str)
                range_clauses.append("timestamp < ?")
                range_params.append(day_end_str)
                
                range_where = " WHERE " + " AND ".join(range_clauses)
                cur.execute(f"SELECT COUNT(*) FROM incidents{range_where}", range_params)
                daily_data.append(cur.fetchone()[0])
            chart_data = daily_data

        elif date_filter == 'week':
            daily_data = []
            now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            for i in range(7):
                day_start = now - timedelta(days=6-i)
                day_end = day_start + timedelta(days=1)
                day_start_str = day_start.strftime('%Y-%m-%d %H:%M:%S')
                day_end_str = day_end.strftime('%Y-%m-%d %H:%M:%S')
                
                range_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
                range_params = list(sources) if sources else []
                range_clauses.append("timestamp >= ?")
                range_params.append(day_start_str)
                range_clauses.append("timestamp < ?")
                range_params.append(day_end_str)
                
                range_where = " WHERE " + " AND ".join(range_clauses)
                cur.execute(f"SELECT COUNT(*) FROM incidents{range_where}", range_params)
                daily_data.append(cur.fetchone()[0])
            chart_data = daily_data

        else:
            # Default to day
            now = datetime.now()
            hourly_data = []
            start24h = now - timedelta(hours=24)
            for i in range(24):
                interval_start = start24h + timedelta(hours=i)
                interval_end = interval_start + timedelta(hours=1)
                if interval_end > now:
                    interval_end = now
                interval_start_str = interval_start.strftime('%Y-%m-%d %H:%M:%S')
                interval_end_str = interval_end.strftime('%Y-%m-%d %H:%M:%S')
                
                range_clauses = [f"source IN ({','.join('?' for _ in sources)})"] if sources else []
                range_params = list(sources) if sources else []
                range_clauses.append("timestamp >= ?")
                range_params.append(interval_start_str)
                range_clauses.append("timestamp < ?")
                range_params.append(interval_end_str)
                
                range_where = " WHERE " + " AND ".join(range_clauses)
                cur.execute(f"SELECT COUNT(*) FROM incidents{range_where}", range_params)
                hourly_data.append(cur.fetchone()[0])
            chart_data = hourly_data

        return jsonify({
            "eventsToday": events_today,
            "eventsLastHour": events_last_hour,
            "eventsActive": events_active,
            "totalIncidents": total_incidents,
            "incidentsByType": incidents_by_type,
            "topLocations": top_locations,
            "hourlyData": chart_data
        })

@app.route("/maps/<filename>")
def get_map(filename):
    return send_from_directory(TARGET_DIR, filename)

@app.route("/api/incidents/<incident_id>/like", methods=["POST", "DELETE"])
def like_incident(incident_id):
    device_uuid = get_or_create_uuid(request)

    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cur = conn.cursor()

            if request.method == "DELETE":
                # Handle unlike
                cur.execute("DELETE FROM likes WHERE incident_no = ? AND device_uuid = ?",
                           (incident_id, device_uuid))
                # Using SQLite's standard way to handle non-negative likes
                cur.execute("UPDATE incidents SET likes = MAX(likes - 1, 0) WHERE incident_no = ?",
                           (incident_id,))
                conn.commit()
            else:
                # Existing POST logic
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

    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            cur = conn.cursor()
            cur.execute("SELECT likes FROM incidents WHERE incident_no = ?", (incident_id,))
            result = cur.fetchone()
            likes_count = result[0] if result else 0

    response = jsonify({"likes": likes_count})
    # Set cookie with UUID
    response.set_cookie(
        COOKIE_NAME,
        device_uuid,
        max_age=COOKIE_MAX_AGE,
        secure=False,
        httponly=True,  # ✅ Fixed typo
        samesite='Lax'
    )
    return response

@app.route("/api/incidents/<incident_id>/comment", methods=["POST"])
def comment_incident(incident_id):
    device_uuid = get_or_create_uuid(request)
    new_comment = request.json.get("comment", "")
    username = request.json.get("username", "Anonymous")
    timestamp = request.json.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if not new_comment:
        return jsonify({"error": "Empty comment"}), 400
    
    with sqlite3.connect(DB_FILE, timeout=30) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        try:
            # Check if user has already commented twice on this post
            cur.execute("SELECT COUNT(*) FROM comments WHERE incident_no = ? AND username = ?", (incident_id, username))
            comment_count = cur.fetchone()[0]
            if comment_count >= 2:
                return jsonify({"error": "You can only leave 2 comments per post."}), 400

            cur.execute("INSERT INTO comments (incident_no, device_uuid, username, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
                        (incident_id, device_uuid, username, new_comment, timestamp))
            conn.commit()
            cur.execute("SELECT username, comment, timestamp FROM comments WHERE incident_no = ? ORDER BY timestamp ASC", (incident_id,))
            comments = [{"username": row[0] or "Anonymous", "comment": row[1], "timestamp": row[2]} for row in cur.fetchall()]
        except sqlite3.IntegrityError:
            conn.rollback()
            return jsonify({"error": "Could not process comment."}), 400
    response = jsonify({"comments": comments})
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
    return response

@app.route("/api/user/check", methods=["GET"])
def check_user():
    device_uuid = get_or_create_uuid(request)
    response = jsonify({"uuid": device_uuid})
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
    return response

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_app(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

def run_scraper_and_server():
    init_db()
    scraper_thread = threading.Thread(target=monitor_traffic_data, daemon=True)
    scraper_thread.start()
    safe_print("Starting Flask server...")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)

if __name__ == "__main__":
    safe_print("Traffic Alert System Starting...")
    safe_print(f"Base directory: {BASE_DIR}")
    print(f"Map directory: {TARGET_DIR}")
    print(f"SQLite DB file: {DB_FILE}")
    if not os.path.exists(MAP_GENERATOR):
        print(f"WARNING: Map generator script not found at {MAP_GENERATOR}")
    run_scraper_and_server()
