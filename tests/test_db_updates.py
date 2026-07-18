import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import db


class IncidentUpdateTests(unittest.TestCase):
    def test_existing_incident_refreshes_all_mutable_source_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "traffic-test.db")
            with patch.object(db, "DB_FILE", db_path):
                db.init_db()
                original = {
                    "No.": "TEST-1",
                    "Date": "2026-07-17",
                    "Timestamp": "2026-07-17 12:00:00",
                    "City": "San Diego",
                    "Neighborhood": "Old Town",
                    "Location": "Old location",
                    "Location Desc.": "Old cross street",
                    "Type": "Traffic Hazard",
                    "Details": [],
                    "Source": "CHP",
                }
                db.save_or_update_incident(
                    original,
                    generate_description_on_insert=False,
                )

                existing = db.fetch_existing_incidents(
                    [("TEST-1", "2026-07-17")]
                )[("TEST-1", "2026-07-17")]
                changed = {
                    **original,
                    "Timestamp": "2026-07-17 12:05:00",
                    "Neighborhood": "Mission Valley",
                    "Location": "I-8 / SR-163",
                    "Location Desc.": "Westbound lanes",
                    "Type": "Traffic Collision",
                    "Latitude": 0.0,
                    "Longitude": 0.0,
                }
                status = db.save_or_update_incident(
                    changed,
                    existing_record=existing,
                    return_status=True,
                    generate_description_on_insert=False,
                )

            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    """
                    SELECT timestamp, neighborhood, location, location_desc,
                           type, latitude, longitude
                    FROM incidents WHERE incident_no = 'TEST-1'
                    """
                ).fetchone()

        self.assertEqual(status, "updated")
        self.assertEqual(
            row,
            (
                "2026-07-17 12:05:00",
                "Mission Valley",
                "I-8 / SR-163",
                "Westbound lanes",
                "Traffic Collision",
                0.0,
                0.0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
