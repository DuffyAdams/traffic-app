import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

# Add parent dir to path so we can import traffic_scraper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# We need to set up the test DB *before* importing the app
TEST_DB_FILE = os.path.join(os.path.dirname(__file__), "test_traffic_data.db")

# Temporarily override the DB_FILE in traffic_scraper module before it initializes
import traffic_scraper
traffic_scraper.DB_FILE = TEST_DB_FILE
traffic_scraper.TESTMODE = True # ensure we don't accidentally do live stuff if applicable

class TestHistoricalAverages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up the bare database schema once for the test class."""
        # Ensure we start fresh
        if os.path.exists(TEST_DB_FILE):
             os.remove(TEST_DB_FILE)
             
        # Initialize schema via the scraper's own function targeting the test file
        traffic_scraper.init_db()

    def setUp(self):
        """Clean the incidents table before each test."""
        with sqlite3.connect(TEST_DB_FILE) as conn:
            conn.execute("DELETE FROM incidents")
            
        # Create the Flask test client
        self.app = traffic_scraper.app.test_client()
        self.app.testing = True

    @classmethod
    def tearDownClass(cls):
        """Remove the test database file after all tests complete."""
        if os.path.exists(TEST_DB_FILE):
             try:
                 os.remove(TEST_DB_FILE)
             except OSError:
                 pass # Windows file lock fallback

    def inject_mock_incident(self, dt: datetime, incident_no: str, source="CHP"):
        """Helper to inject a single incident at a specific datetime."""
        with sqlite3.connect(TEST_DB_FILE) as conn:
            cur = conn.cursor()
            date_str = dt.strftime("%Y-%m-%d")
            timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                """
                INSERT INTO incidents 
                (incident_no, date, timestamp, source, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (incident_no, date_str, timestamp_str, source, 0)
            )
            
    def test_historical_average_calculation(self):
        """
        Test that the /api/incident_stats endpoint correctly calculates 
        the historical average for the current hour and current day of the week.
        """
        # 1. Determine "Now" as the server will see it
        now = datetime.now()
        
        # 2. We will inject data into the 3 previous weeks at THIS EXACT hour.
        # Week 1 ago: 20 incidents
        # Week 2 ago: 10 incidents
        # Week 3 ago: 30 incidents
        # Total mathematical average expected = (20 + 10 + 30) / 3 = 20.0
        
        # We also inject "noise" data at different hours/days to ensure the SQL filters correctly.
        
        week1_dt = now - timedelta(days=7)
        week2_dt = now - timedelta(days=14)
        week3_dt = now - timedelta(days=21)
        
        # Noise (same day of week, different hour)
        noise_hour_dt = now - timedelta(days=7, hours=2) 
        
        # Noise (different day of week, same hour)
        noise_day_dt = now - timedelta(days=6)
        
        incident_counter = 1
        
        # Inject Week 1 (20 incidents)
        for _ in range(20):
            self.inject_mock_incident(week1_dt, f"MOCK-{incident_counter}")
            incident_counter += 1
            
        # Inject Week 2 (10 incidents)
        for _ in range(10):
            self.inject_mock_incident(week2_dt, f"MOCK-{incident_counter}")
            incident_counter += 1
            
        # Inject Week 3 (30 incidents)
        for _ in range(30):
            self.inject_mock_incident(week3_dt, f"MOCK-{incident_counter}")
            incident_counter += 1
            
        # Inject Noise Hour (15 incidents)
        for _ in range(15):
            self.inject_mock_incident(noise_hour_dt, f"NOISE-HR-{incident_counter}")
            incident_counter += 1
            
        # Inject Noise Day (25 incidents)
        for _ in range(25):
            self.inject_mock_incident(noise_day_dt, f"NOISE-DAY-{incident_counter}")
            incident_counter += 1

        # 3. Hit the endpoint
        response = self.app.get('/api/incident_stats?date_filter=day')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        
        # 4. Assert the baseline
        self.assertIn("historicalCurrentHourAverage", data)
        # We expect exactly 20.0 (60 incidents / 3 distinct weeks)
        self.assertEqual(data["historicalCurrentHourAverage"], 20.0)
        
        print("\n  ✓ test_historical_average_calculation passed (Average successfully calculated as 20.0 with 3 weeks of historical data ignoring noise)")

if __name__ == "__main__":
    print("=" * 60)
    print("HISTORICAL AVERAGES TEST SUITE")
    print("=" * 60)
    unittest.main(verbosity=2)
