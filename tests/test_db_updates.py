import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from backend import db


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

    def test_legacy_pending_batch_work_migrates_only_for_active_incidents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "traffic-test.db")
            with patch.object(db, "DB_FILE", db_path):
                db.init_db()
                with closing(sqlite3.connect(db_path)) as conn:
                    conn.executemany(
                        """
                        INSERT INTO incidents (
                            incident_no, date, active, batch_queued_at,
                            batch_enriched_at
                        ) VALUES (?, '2026-07-17', ?, '2026-07-17 12:00:00', NULL)
                        """,
                        [("ACTIVE-1", 1), ("INACTIVE-1", 0)],
                    )
                    conn.commit()

                db.init_db()
                db.init_db()

            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    """
                    SELECT incident_no, llm_pending_at, batch_queued_at,
                           batch_enriched_at
                    FROM incidents
                    ORDER BY incident_no
                    """
                ).fetchall()

        self.assertEqual(
            rows,
            [
                ("ACTIVE-1", "2026-07-17 12:00:00", None, None),
                ("INACTIVE-1", None, None, None),
            ],
        )

    def test_init_db_preserves_existing_caltrans_notification_incidents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "traffic-test.db")
            with patch.object(db, "DB_FILE", db_path):
                db.init_db()
                with closing(sqlite3.connect(db_path)) as conn:
                    conn.execute(
                        """
                        INSERT INTO incidents (
                            incident_no, date, timestamp, type, source
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            "CALTRANS-1",
                            "2026-07-17",
                            "2026-07-17 12:00:00",
                            "Request CalTrans Notify",
                            "CHP",
                        ),
                    )
                    conn.commit()

                db.init_db()

            with closing(sqlite3.connect(db_path)) as conn:
                preserved_count = conn.execute(
                    "SELECT COUNT(*) FROM incidents WHERE incident_no = ?",
                    ("CALTRANS-1",),
                ).fetchone()[0]

        self.assertEqual(preserved_count, 1)


if __name__ == "__main__":
    unittest.main()
