import requests
from bs4 import BeautifulSoup
import re
from geopy.geocoders import Nominatim
import os
import sqlite3
import json
from datetime import datetime
import subprocess
import time
import sys
import pytz
import threading
import uuid
from flask import Flask, jsonify, send_from_directory, request, make_response
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

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}
PARAMS = {"ddlComCenter": "BCCC"}
SCRAPE_URL = "https://cad.chp.ca.gov/traffic.aspx?__EVENTTARGET=ddlComCenter&ddlComCenter=BCCC"

# Regex patterns
VIEWSTATE_PATTERN = re.compile(r'<input\s+type="hidden"\s+name="__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]+)"\s*/?>')
LAT_LON_PATTERN = re.compile(r"(\d+\.\d+ -\d+\.\d+)")
BRACKETS_PATTERN = re.compile(r"\[.*?\]")
EXCLUDED_DETAILS = {"Unit At Scene", "Unit Enroute", "Unit Assigned"}

# Cookie settings
COOKIE_NAME = "traffic_app_uuid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year in seconds

# Flask app setup
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "traffic-app", "dist"))

# -----------------------------------
# Database Functions
# -----------------------------------
def init_db():
    """Initialize SQLite database with updated schema using UUID instead of IP."""
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        # Updated incidents table with date column for composite key
        cur.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_no TEXT,
                date TEXT,  -- Added for daily uniqueness
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
                PRIMARY KEY (incident_no, date)
            )
        """)
        
        # Recreate likes table to use UUID instead of IP address
        cur.execute("DROP TABLE IF EXISTS likes")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                device_uuid TEXT,
                incident_no TEXT,
                timestamp TEXT,
                PRIMARY KEY (device_uuid, incident_no)
            )
        """)
        
        # Recreate comments table to use UUID instead of IP address
        cur.execute("DROP TABLE IF EXISTS comments")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                device_uuid TEXT,
                incident_no TEXT,
                username TEXT,
                comment TEXT,
                timestamp TEXT,
                PRIMARY KEY (device_uuid, incident_no)
            )
        """)
        conn.commit()

def incident_exists(incident_no, date=None):
    """Check if an incident exists for the given number and date."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM incidents WHERE incident_no = ? AND date = ?",
            (str(incident_no), date)
        )
        return cur.fetchone() is not None

def save_to_db(data):
    """Save incident data to the database with date for uniqueness."""
    if not data:
        return False

    incident_no = data.get("No.") or data.get("Incident No.")
    if not incident_no:
        print("No incident number found in data.")
        return False

    date = data.get("Date", datetime.now().strftime("%Y-%m-%d"))
    timestamp = data.get("Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    city = data.get("City", "")
    neighborhood = data.get("Neighborhood", "")
    location = data.get("Location", "")
    location_desc = data.get("Location Desc.", "")
    type_field = data.get("Type", "")
    details = json.dumps(data.get("Details", []))
    description = data.get("Description", "")
    latitude = data.get("Latitude")
    longitude = data.get("Longitude")
    map_filename = data.get("MapFilename", "")
    likes = data.get("likes", 0)
    comments = json.dumps(data.get("comments", []))

    if incident_exists(incident_no, date):
        return False

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO incidents 
                (incident_no, date, timestamp, city, neighborhood, location, location_desc, type, details, 
                 description, latitude, longitude, map_filename, likes, comments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(incident_no), date, timestamp, city, neighborhood, location, location_desc, type_field,
                  details, description, latitude, longitude, map_filename, likes, comments))
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def read_incidents():
    """Read all incidents from the database with comments."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM incidents ORDER BY timestamp DESC")
        incidents = [dict(row) for row in cur.fetchall()]

        for inc in incidents:
            incident_no = inc["incident_no"]
            cur.execute(
                "SELECT username, comment FROM comments WHERE incident_no = ? ORDER BY timestamp ASC",
                (incident_no,)
            )
            inc["comments"] = [{"username": row[0] or "Anonymous", "comment": row[1]} for row in cur.fetchall()]
            inc["Details"] = json.loads(inc["details"]) if inc["details"] else []
        return incidents

# -----------------------------------
# UUID Management
# -----------------------------------
def get_or_create_uuid(request):
    """Get UUID from cookie or create a new one if not present."""
    device_uuid = request.cookies.get(COOKIE_NAME)
    if not device_uuid:
        device_uuid = str(uuid.uuid4())
        print(f"New UUID generated: {device_uuid}")
    else:
        print(f"Reusing existing UUID: {device_uuid}")
    return device_uuid

# -----------------------------------
# Scraper Functions
# -----------------------------------
def generate_description(data):
    """Generate a tweet-friendly description using OpenAI GPT."""
    try:
        client_gpt = OpenAI(api_key=os.getenv("GPT_KEY"))
        prompt = (
            f"Neighborhood: {data['Neighborhood']}\n"
            f"Location: {data['Location']} - {data['Location Desc.']}\n"
            f"Type: {data['Type']}\n"
            f"Details: {', '.join(data['Details'])}\n"
        )
        response = client_gpt.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "give brief, neutral updates without any extra additions. Interpret abbreviations like 'No' as Northbound, 'So' as Southbound, 'OOG' as out of gas and any other CHP abbreviations. Also add some relatated emojis. Make the posts less than 200 characters."},
                {"role": "user", "content": f"Summarize this traffic incident for a tweet:\n{prompt}"}
            ],
            max_tokens=50,
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating description: {e}")
        return "Traffic incident reported."

def scrape_table():
    """Scrape the first row of the incident table, skipping 'Media Log'."""
    try:
        response = requests.get(SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="gvIncidents")
        if not table:
            print("No incident table found.")
            return None

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = table.find_all("tr")
        if len(rows) < 2:
            print("No incident rows found.")
            return None

        row_data = [cell.get_text(strip=True) for cell in rows[1].find_all("td")]
        if "Location" in headers and row_data[headers.index("Location")] == "Media Log":
            print("Skipping 'Media Log' entry.")
            return None

        return dict(zip(headers, row_data))
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

def get_viewstate(response_text):
    """Extract __VIEWSTATE from HTML."""
    match = VIEWSTATE_PATTERN.search(response_text)
    return match.group(1) if match else None

def extract_traffic_info(response_text):
    """Extract coordinates and details from response."""
    matches = LAT_LON_PATTERN.findall(response_text)
    details_pattern = re.compile(r'<td[^>]*colspan="6"[^>]*>(.*?)</td>', re.DOTALL)
    raw_details = details_pattern.findall(response_text)
    details = [BRACKETS_PATTERN.sub("", detail).strip() for detail in raw_details
               if not any(excluded in detail for excluded in EXCLUDED_DETAILS)]

    if matches:
        last_valid_coords = None
        for match in matches:
            lat_str, lon_str = match.split()
            # Check if the coordinates have 6 decimal places
            if len(lat_str.split(".")[-1]) == 6 and len(lon_str.split(".")[-1]) == 6:
                last_valid_coords = {"Latitude": float(lat_str), "Longitude": float(lon_str), "Details": details}
        return last_valid_coords  # Return the last valid coordinates found
    return None

def get_location(lat, lon):
    """Reverse geocode coordinates to get location details."""
    try:
        geolocator = Nominatim(user_agent="traffic_scraper")
        location = geolocator.reverse((lat, lon), exactly_one=True)
        return location.raw.get("address") if location else None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

def get_coordinates():
    """Fetch coordinates and details via GET and POST requests."""
    try:
        response = requests.get(SCRAPE_URL, headers=HEADERS)
        response.raise_for_status()
        viewstate_value = get_viewstate(response.text)
        if not viewstate_value:
            print("No __VIEWSTATE found.")
            return None

        data = {
            "__LASTFOCUS": "",
            "__EVENTTARGET": "gvIncidents",
            "__EVENTARGUMENT": "Select$0",
            "__VIEWSTATE": viewstate_value,
            "__VIEWSTATEGENERATOR": "B13DF00D",
            "ddlComCenter": "BCCC",
            "ddlSearches": "Choose One",
            "ddlResources": "Choose One",
        }
        post_response = requests.post(SCRAPE_URL, params=PARAMS, headers=HEADERS, data=data)
        post_response.raise_for_status()

        coordinates_data = extract_traffic_info(post_response.text)
        if coordinates_data:
            location_info = get_location(coordinates_data["Latitude"], coordinates_data["Longitude"])
            if location_info:
                coordinates_data["Neighborhood"] = location_info.get("neighbourhood", "N/A")
                coordinates_data["City"] = location_info.get("city", "N/A")
        return coordinates_data
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

def get_merged_data():
    """Merge table data with coordinates and generate description."""
    table_data = scrape_table()
    if not table_data:
        return None

    table_data.pop("Area", None)
    coordinates_data = get_coordinates()
    if coordinates_data:
        merged_data = {**table_data, **coordinates_data}
        required_fields = ["City", "Neighborhood", "Location", "Location Desc.", "Type", "Details"]
        if all(key in merged_data for key in required_fields):
            merged_data["Description"] = generate_description(merged_data)
        else:
            merged_data["Description"] = "Traffic incident reported."
        merged_data["Date"] = datetime.now().strftime("%Y-%m-%d")  # Add date for uniqueness
        return merged_data
    return None

def run_map_generator(merged_data):
    """Run map generator script and update data with filename."""
    if not os.path.exists(MAP_GENERATOR):
        print(f"Map generator script not found at '{MAP_GENERATOR}'.")
        return

    try:
        lon = merged_data.get("Longitude")
        lat = merged_data.get("Latitude")
        local_timezone = pytz.timezone("America/Los_Angeles")
        incident_time = datetime.now(local_timezone)
        timestamp_str = incident_time.strftime("%Y-%m-%d %H:%M:%S")
        filename_date_str = incident_time.strftime("%Y%m%d_%H%M")
        filename = os.path.join(TARGET_DIR, f"map_{filename_date_str}.png")

        cmd = [sys.executable, MAP_GENERATOR, str(lon), str(lat), filename]
        subprocess.run(cmd, check=True)
        print("Map generated successfully.")

        merged_data["Timestamp"] = timestamp_str
        merged_data["MapFilename"] = os.path.basename(filename)
    except subprocess.CalledProcessError as e:
        print(f"Error running map generator: {e}")
def monitor_traffic_data(interval=60):
    """Monitor traffic data and process new incidents."""
    print("Starting continuous traffic monitoring...")
    print(f"Data saved to: {DB_FILE}")
    print(f"Map generator: {MAP_GENERATOR}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            print(f"\nChecking updates... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            merged_data = get_merged_data()

            if merged_data:
                incident_no = merged_data.get("No.") or merged_data.get("Incident No.")
                if not incident_no:
                    print("WARNING: No incident number found. Processing anyway.")
                    run_map_generator(merged_data)
                    save_to_db(merged_data)
                    print("Processed incident without number.")
                    time.sleep(interval)
                    continue

                date = merged_data["Date"]
                if not incident_exists(incident_no, date):
                    print(f"Processing new incident {incident_no} for {date}")
                    run_map_generator(merged_data)
                    if save_to_db(merged_data):
                        print(f"Incident {incident_no} saved and map generated.")
                    else:
                        print("Failed to save incident.")
                else:
                    print(f"Incident {incident_no} for {date} already exists.")
            else:
                print("No valid data retrieved.")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nError: {e}")
        raise

# -----------------------------------
# Flask API Endpoints
# -----------------------------------
@app.route("/api/incidents")
def get_incidents():
    """Return all incidents and set UUID cookie if needed."""
    response = jsonify(read_incidents())
    
    # Set UUID cookie if not present
    if COOKIE_NAME not in request.cookies:
        device_uuid = str(uuid.uuid4())
        response.set_cookie(
            COOKIE_NAME, 
            device_uuid, 
            max_age=COOKIE_MAX_AGE, 
            secure=False,  # Allow HTTP for development
            httponly=True,  # Not accessible via JavaScript
            samesite='Lax'  # Restrict cross-site requests
        )
    
    return response

@app.route("/maps/<filename>")
def get_map(filename):
    return send_from_directory(TARGET_DIR, filename)

@app.route("/api/incidents/<incident_id>/like", methods=["POST"])
def like_incident(incident_id):
    """Like an incident using UUID instead of IP address."""
    device_uuid = get_or_create_uuid(request)
    
    with sqlite3.connect(DB_FILE) as conn:
        # Enable foreign key support explicitly
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        
        # Check if user already liked this incident
        cur.execute("SELECT 1 FROM likes WHERE incident_no = ? AND device_uuid = ?", 
                   (incident_id, device_uuid))
        if cur.fetchone():
            return jsonify({"error": "You already liked this post."}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add the like with better error handling
        try:
            cur.execute("INSERT INTO likes (incident_no, device_uuid, timestamp) VALUES (?, ?, ?)", 
                       (incident_id, device_uuid, timestamp))
            cur.execute("UPDATE incidents SET likes = likes + 1 WHERE incident_no = ?", 
                       (incident_id,))
            conn.commit()
            
            cur.execute("SELECT likes FROM incidents WHERE incident_no = ?", (incident_id,))
            result = cur.fetchone()
            if result:
                likes_count = result[0]
            else:
                return jsonify({"error": "Incident not found"}), 404
                
        except sqlite3.IntegrityError:
            # This handles any potential race conditions or unique constraint violations
            conn.rollback()
            return jsonify({"error": "Could not process like. You may have already liked this post."}), 400
    
    # Set cookie only if it's a new UUID (first request)
    response = jsonify({"likes": likes_count})
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME, 
            device_uuid, 
            max_age=COOKIE_MAX_AGE, 
            secure=False,  # Allow HTTP for development
            httponly=True,
            samesite='Lax'
        )
    
    return response

@app.route("/api/incidents/<incident_id>/comment", methods=["POST"])
def comment_incident(incident_id):
    """Comment on an incident using UUID instead of IP address."""
    # Get or create UUID from cookie
    device_uuid = get_or_create_uuid(request)
    
    new_comment = request.json.get("comment", "")
    username = request.json.get("username", "Anonymous")
    if not new_comment:
        return jsonify({"error": "Empty comment"}), 400

    with sqlite3.connect(DB_FILE) as conn:
        # Enable foreign key support explicitly
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        
        # Check if user already commented on this incident
        cur.execute("SELECT 1 FROM comments WHERE incident_no = ? AND device_uuid = ?", 
                   (incident_id, device_uuid))
        if cur.fetchone():
            return jsonify({"error": "You already commented on this post."}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cur.execute(
                "INSERT INTO comments (incident_no, device_uuid, username, comment, timestamp) VALUES (?, ?, ?, ?, ?)",
                (incident_id, device_uuid, username, new_comment, timestamp)
            )
            conn.commit()

            cur.execute("SELECT username, comment FROM comments WHERE incident_no = ? ORDER BY timestamp ASC", 
                        (incident_id,))
            comments = [{"username": row[0] or "Anonymous", "comment": row[1]} for row in cur.fetchall()]
        except sqlite3.IntegrityError:
            conn.rollback()
            return jsonify({"error": "Could not process comment. You may have already commented on this post."}), 400
    
    # Create response with cookie if needed
    response = jsonify({"comments": comments})
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME, 
            device_uuid, 
            max_age=COOKIE_MAX_AGE, 
            secure=False,  # Allow HTTP for development
            httponly=True,
            samesite='Lax'
        )
    
    return response

@app.route("/api/user/check", methods=["GET"])
def check_user():
    """Check if user already has UUID and return it (for client-side use)."""
    device_uuid = get_or_create_uuid(request)
    
    response = jsonify({"uuid": device_uuid})
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(
            COOKIE_NAME, 
            device_uuid, 
            max_age=COOKIE_MAX_AGE, 
            secure=False,  # Allow HTTP for development
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

# -----------------------------------
# Main Execution
# -----------------------------------
def run_scraper_and_server():
    """Run scraper in a thread and start Flask server."""
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