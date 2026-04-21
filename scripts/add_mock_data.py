import os
import sqlite3
import random
from datetime import datetime, timedelta
import uuid
import json

# Project root is one directory above scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(PROJECT_ROOT, "traffic_data.db")

def add_mock_data():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    now = datetime.now()
    incident_types = ["Traffic Collision", "Traffic Hazard", "Disabled Vehicle", "Fire", "Medical Emergency"]
    locations = ["1-5 N / 1-8 E", "163 S / FRIARS RD", "I-805 S / SR-94", "I-15 N / MIRA MESA BLVD", "SR-52 E / CONVOY ST"]
    cities = ["San Diego", "Chula Vista", "Oceanside", "Escondido", "Carlsbad"]

    print("Adding mock data...")

    # Generate data for the past 7 days
    for day_offset in range(7):
        target_date = now - timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")

        # Generate a random number of incidents per day (e.g., 20 to 100)
        # To test the "spike", let's make one day have significantly more incidents
        num_incidents = random.randint(20, 50)
        if day_offset == 1: # Make yesterday have a spike
             num_incidents = 150

        for _ in range(num_incidents):
            # Random time within the day
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            
            # To test hourly spikes, concentrate incidents in specific hours
            if day_offset == 1 and random.random() < 0.5:
                hour = 17 # 5 PM rush hour spike

            incident_time = target_date.replace(hour=hour, minute=minute, second=second)
            timestamp_str = incident_time.strftime("%Y-%m-%d %H:%M:%S")

            incident_no = f"MOCK-{uuid.uuid4().hex[:8].upper()}"
            city = random.choice(cities)
            neighborhood = f"{city} Neighborhood"
            location = random.choice(locations)
            location_desc = f"Near {location}"
            type_val = random.choice(incident_types)
            details = json.dumps([f"Mock detail 1 for {incident_no}", "Mock detail 2"])
            description = f"Mock description for {type_val} at {location}"
            latitude = 32.7157 + random.uniform(-0.1, 0.1)
            longitude = -117.1611 + random.uniform(-0.1, 0.1)
            map_filename = "mock_map.png"
            likes = random.randint(0, 10)
            active = 1 if day_offset == 0 and hour >= now.hour - 2 else 0 # make some of today active
            source = random.choice(["CHP", "SDPD", "SDFD"])
            geocode_precision = "street"

            cur.execute("""
                INSERT INTO incidents 
                (incident_no, date, timestamp, city, neighborhood, location, location_desc, type, details, 
                 description, latitude, longitude, map_filename, likes, comments, active, source, geocode_precision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(incident_no), date_str, timestamp_str, city, neighborhood, location, location_desc, type_val,
                  details, description, latitude, longitude, map_filename, likes, '[]', active, source, geocode_precision))

    conn.commit()
    conn.close()
    print("Mock data added successfully!")

if __name__ == "__main__":
    add_mock_data()
