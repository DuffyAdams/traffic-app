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
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
import pytz
from flask import Flask, jsonify, send_from_directory, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI

# -----------------------------------
# Configuration and Setup
# -----------------------------------
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_DIR = os.path.join(BASE_DIR, "traffic-app", "maps")
DB_FILE = os.path.join(BASE_DIR, "traffic_data.db")
MAP_GENERATOR = os.path.join(BASE_DIR, "generate_map.py")

os.makedirs(TARGET_DIR, exist_ok=True)

# Retrieve the API key from the environment
GPT_KEY = os.getenv("GPT_KEY")

# Check if the API key is loaded correctly
if not GPT_KEY:
    raise ValueError("GPT_KEY not found in environment variables. Ensure it is set in the .env file.")

# Initialize the OpenAI client with the API key
client = OpenAI(api_key=GPT_KEY)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}
PARAMS = {"ddlComCenter": "BCCC"}
SCRAPE_URL = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"

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
TESTMODE = False

# -----------------------------------
# Database Functions
# -----------------------------------
def init_db():
    """Initialize SQLite database with updated schema."""
    with sqlite3.connect(DB_FILE) as conn:
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
                PRIMARY KEY (incident_no, date)
            )
        """)
        # Likes table
        cur.execute("DROP TABLE IF EXISTS likes")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                device_uuid TEXT,
                incident_no TEXT,
                timestamp TEXT,
                PRIMARY KEY (device_uuid, incident_no)
            )
        """)
        # Comments table
        cur.execute("DROP TABLE IF EXISTS comments")
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
        
        conn.commit()

def read_incidents(limit=20, offset=0, incident_type=None, active_only=False):
    """Read a limited set of incidents from the database along with their comments."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        query = "SELECT * FROM incidents"
        params = []
        conditions = []

        if incident_type:
            conditions.append("type = ?")
            params.append(incident_type)
        
        if active_only:
            conditions.append("active = 1")
            conditions.append("map_filename IS NOT NULL") # Only show active incidents that have a map

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

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
    with sqlite3.connect(DB_FILE) as conn:
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
    print("GPT API Calls:" + str(call_count))

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
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]
            )
            return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error generating description: {e}")
        return "Traffic incident reported."

# -----------------------------------
# Save or Update Incident
# -----------------------------------
def save_or_update_incident(data):
    if not data:
        return False

    incident_no = data.get("No.") or data.get("Incident No.")
    if not incident_no:
        print("No incident number found in data.")
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

    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM incidents WHERE incident_no = ? AND date = ?", (str(incident_no), date))
        existing = cur.fetchone()
        if existing:
            existing_data = dict(existing)
            if details_json != existing_data.get("details", ""):
                # Only generate a new description if details have changed
                new_description = generate_description(data)
                cur.execute("""
                    UPDATE incidents 
                    SET details = ?, description = ?, active = 1
                    WHERE incident_no = ? AND date = ?
                """, (details_json, new_description, str(incident_no), date))
                conn.commit()
                print(f"Incident {incident_no} updated (details only).")
                return True
            else:
                print(f"No changes in details for incident {incident_no}.")
                return False
        else:
            # For new incidents, generate the description before inserting
            new_description = generate_description(data)
            cur.execute("""
                INSERT INTO incidents 
                (incident_no, date, timestamp, city, neighborhood, location, location_desc, type, details, 
                 description, latitude, longitude, map_filename, likes, comments, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (str(incident_no), date, new_timestamp, city, neighborhood, location, location_desc, type_field,
                  details_json, new_description, latitude, longitude, new_map_filename, 0, '[]'))
            conn.commit()
            print(f"Incident {incident_no} inserted.")
            return True

# -----------------------------------
# UUID Management
# -----------------------------------
def get_or_create_uuid(req):
    device_uuid = req.cookies.get(COOKIE_NAME)
    if not device_uuid:
        device_uuid = str(uuid.uuid4())
        print(f"New UUID generated: {device_uuid}")
    else:
        print(f"Reusing existing UUID: {device_uuid}")
    return device_uuid

# -----------------------------------
# Scraper Functions
# -----------------------------------
def get_viewstate(html_text):
    match = VIEWSTATE_PATTERN.search(html_text)
    return match.group(1) if match else None

def extract_traffic_info(response_text):
    matches = LAT_LON_PATTERN.findall(response_text)
    details_pattern = re.compile(r'<td[^>]*colspan="6"[^>]*>(.*?)</td>', re.DOTALL)
    raw_details = details_pattern.findall(response_text)
    details = [BRACKETS_PATTERN.sub("", detail).strip() for detail in raw_details
               if not any(excluded in detail for excluded in EXCLUDED_DETAILS)]
    if matches:
        last_valid_coords = {}
        for match in matches:
            lat_str, lon_str = match.split()
            if len(lat_str.split(".")[-1]) == 6 and len(lon_str.split(".")[-1]) == 6:
                last_valid_coords = {"Latitude": float(lat_str), "Longitude": float(lon_str), "Details": details}
        return last_valid_coords
    return {}

def get_location(lat, lon):
    try:
        geolocator = Nominatim(user_agent="traffic_scraper")
        location = geolocator.reverse((lat, lon), exactly_one=True)
        return location.raw.get("address") if location else None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

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
        }
        post_response = requests.post(SCRAPE_URL, params=PARAMS, headers=HEADERS, data=data)
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
        print(f"Network or HTTP error getting incident details for index {row_index}: {e}")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred getting incident details for index {row_index}: {e}")
        return {}

def scrape_all_incidents():
    try:
        response = requests.get(SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="gvIncidents")
        if not table:
            print("No incident table found.")
            return []
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = table.find_all("tr")[1:]  # Skip header row
        incidents_list = []
        viewstate = get_viewstate(response.text)
        if not viewstate:
            print("No __VIEWSTATE found.")
            return []
        for idx, row in enumerate(rows):
            row_data = [cell.get_text(strip=True) for cell in row.find_all("td")]
            if "Location" in headers and row_data[headers.index("Location")] == "Media Log":
                print(f"Skipping 'Media Log' entry at index {idx}")
                continue
            table_data = dict(zip(headers, row_data))
            additional_details = get_incident_details(idx, viewstate)
            if not additional_details:
                print(f"WARNING: Failed to retrieve additional details for incident at index {idx}. Skipping.")
                continue # Skip this incident if details could not be retrieved

            merged_data = {**table_data, **additional_details}
            # Remove the generate_description() call here to avoid duplicate API calls.
            merged_data["Date"] = datetime.now().strftime("%Y-%m-%d")
            merged_data["Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            incidents_list.append(merged_data)
        return incidents_list
    except Exception as e:
        print("Error scraping incidents:", e)
        return []

def run_map_generator(merged_data):
    if not os.path.exists(MAP_GENERATOR):
        print(f"Map generator script not found at '{MAP_GENERATOR}'.")
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
        print("Map generated successfully.")
        merged_data["Timestamp"] = timestamp_str
        merged_data["MapFilename"] = os.path.basename(filename)
    except subprocess.CalledProcessError as e:
        print(f"Error running map generator: {e}")

def monitor_traffic_data(interval=60):
    print("Starting continuous traffic monitoring...")
    print(f"Data saved to: {DB_FILE}")
    print(f"Map generator: {MAP_GENERATOR}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            print(f"Checking updates... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            incidents = scrape_all_incidents()
            active_incident_ids = set()
            if incidents:
                for incident in incidents:
                    incident_no = incident.get("No.") or incident.get("Incident No.")
                    if not incident_no:
                        print("WARNING: No incident number found. Skipping this entry.")
                        continue
                    active_incident_ids.add(str(incident_no))
                    if not incident_exists(incident_no, incident.get("Date", datetime.now().strftime("%Y-%m-%d"))):
                        if "Longitude" in incident and "Latitude" in incident:
                            run_map_generator(incident)
                    save_or_update_incident(incident)
            else:
                print("No valid data retrieved.")

            # Mark incidents as inactive if they are not in the current scrape.
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                if active_incident_ids:
                    placeholders = ",".join("?" for _ in active_incident_ids)
                    query = f"UPDATE incidents SET active = 0 WHERE incident_no NOT IN ({placeholders})"
                    cur.execute(query, tuple(active_incident_ids))
                else:
                    cur.execute("UPDATE incidents SET active = 0")
                conn.commit()

            time.sleep(interval)
    except KeyboardInterrupt:
        print("Monitoring stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        raise

@app.route("/api/incidents")
def get_incidents():
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    incident_type = request.args.get("type") # Added to support filtering by type
    active_only = request.args.get("active_only", "false").lower() == "true"

    # Modify read_incidents to accept active_only filter
    response = jsonify(read_incidents(limit=limit, offset=offset, incident_type=incident_type, active_only=active_only))
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
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        
        # Events Today
        today = datetime.now().strftime("%Y-%m-%d")
        cur.execute("SELECT COUNT(*) FROM incidents WHERE date = ?", (today,))
        events_today = cur.fetchone()[0]

        # Events Last Hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        one_hour_ago_str = one_hour_ago.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("SELECT COUNT(*) FROM incidents WHERE timestamp >= ?", (one_hour_ago_str,))
        events_last_hour = cur.fetchone()[0]

        # Active Events (only count incidents with a map_filename, as these are displayed)
        cur.execute("SELECT COUNT(*) FROM incidents WHERE active = 1 AND map_filename IS NOT NULL")
        events_active = cur.fetchone()[0]
        
        return jsonify({
            "eventsToday": events_today,
            "eventsLastHour": events_last_hour,
            "eventsActive": events_active
        })

@app.route("/maps/<filename>")
def get_map(filename):
    return send_from_directory(TARGET_DIR, filename)

@app.route("/api/incidents/<incident_id>/like", methods=["POST"])
def like_incident(incident_id):
    device_uuid = get_or_create_uuid(request)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM likes WHERE incident_no = ? AND device_uuid = ?", (incident_id, device_uuid))
        if cur.fetchone():
            return jsonify({"error": "You already liked this post."}), 400
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cur.execute("INSERT INTO likes (incident_no, device_uuid, timestamp) VALUES (?, ?, ?)", (incident_id, device_uuid, timestamp))
            cur.execute("UPDATE incidents SET likes = likes + 1 WHERE incident_no = ?", (incident_id,))
            conn.commit()
            cur.execute("SELECT likes FROM incidents WHERE incident_no = ?", (incident_id,))
            result = cur.fetchone()
            likes_count = result[0] if result else 0
        except sqlite3.IntegrityError:
            conn.rollback()
            return jsonify({"error": "Could not process like."}), 400
    response = jsonify({"likes": likes_count})
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME,
            device_uuid,
            max_age=COOKIE_MAX_AGE,
            secure=False,
            httpy=True,
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
    
    with sqlite3.connect(DB_FILE) as conn:
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
            httpy=True,
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
            httpy=True,
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
    print("Starting Flask server...")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)

if __name__ == "__main__":
    print("Traffic Alert System Starting...")
    print(f"Base directory: {BASE_DIR}")
    print(f"Map directory: {TARGET_DIR}")
    print(f"SQLite DB file: {DB_FILE}")
    if not os.path.exists(MAP_GENERATOR):
        print(f"WARNING: Map generator script not found at {MAP_GENERATOR}")
    run_scraper_and_server()