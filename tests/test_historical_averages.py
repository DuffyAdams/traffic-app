import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import timedelta
from unittest.mock import patch

from backend import db, routes
from backend.config import now_pst


class HistoricalAverageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "traffic-test.db")
        db.init_db(self.db_path)
        self.patches = [
            patch.object(db, "DB_FILE", self.db_path),
            patch.object(routes, "DB_FILE", self.db_path),
        ]
        for active_patch in self.patches:
            active_patch.start()
        routes._clear_response_cache()
        self.client = routes.app.test_client()

    def tearDown(self):
        routes._clear_response_cache()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def _insert_incidents(self, timestamp, count, prefix, next_id):
        rows = []
        for offset in range(count):
            incident_id = next_id + offset
            rows.append(
                (
                    f"{prefix}-{incident_id}",
                    timestamp.strftime("%Y-%m-%d"),
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "CHP",
                    0,
                )
            )
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executemany(
                """
                INSERT INTO incidents
                    (incident_no, date, timestamp, source, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        return next_id + count

    def test_historical_average_uses_matching_weekday_and_hour(self):
        now = now_pst().replace(minute=30, second=0, microsecond=0)
        next_id = 1
        for weeks_ago, count in ((1, 20), (2, 10), (3, 30)):
            next_id = self._insert_incidents(
                now - timedelta(days=7 * weeks_ago),
                count,
                "MATCH",
                next_id,
            )

        next_id = self._insert_incidents(
            now - timedelta(days=7, hours=2),
            15,
            "OTHER-HOUR",
            next_id,
        )
        self._insert_incidents(
            now - timedelta(days=6),
            25,
            "OTHER-DAY",
            next_id,
        )

        with (
            patch.object(routes, "now_pst", return_value=now),
            patch.object(routes, "_record_api_event"),
        ):
            response = self.client.get("/api/incident_stats?date_filter=day")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["historicalCurrentHourAverage"], 20.0)


if __name__ == "__main__":
    unittest.main()
