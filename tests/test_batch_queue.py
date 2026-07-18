import gc
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

import db
import monitor


class BatchQueueTests(unittest.TestCase):
    def test_new_incident_is_queued_and_refinement_is_applied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "traffic-test.db")
            with patch.object(db, "DB_FILE", db_path):
                db.init_db()
                db.save_or_update_incident(
                    {
                        "No.": "TEST-1",
                        "Date": "2026-07-17",
                        "Timestamp": "2026-07-17 18:00:00",
                        "Location": "I-5 / Test Rd",
                        "Type": "Traffic Collision",
                        "Details": ["Two lanes blocked"],
                        "Source": "CHP",
                    },
                    generate_description_on_insert=False,
                )

            with closing(sqlite3.connect(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                record = dict(conn.execute("SELECT * FROM incidents").fetchone())

            self.assertIsNotNone(record["batch_queued_at"])
            self.assertIsNone(record["batch_enriched_at"])

            fake_results = [
                {
                    "item_id": 1,
                    "summary": "Two lanes blocked by a collision. 🚧",
                    "severity": 3,
                }
            ]
            with (
                patch.object(monitor, "DB_FILE", db_path),
                patch.object(
                    monitor,
                    "generate_batch_descriptions",
                    return_value=fake_results,
                ),
            ):
                monitor._refine_description_batch([record])

            with closing(sqlite3.connect(db_path)) as conn:
                updated = conn.execute(
                    """
                    SELECT description, severity, batch_enriched_at
                    FROM incidents
                    WHERE incident_no = ? AND date = ?
                    """,
                    ("TEST-1", "2026-07-17"),
                ).fetchone()

            self.assertEqual(updated[0], "Two lanes blocked by a collision. 🚧")
            self.assertEqual(updated[1], 3)
            self.assertIsNotNone(updated[2])
            gc.collect()


if __name__ == "__main__":
    unittest.main()
