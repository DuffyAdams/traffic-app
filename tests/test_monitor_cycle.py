import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import Future
from datetime import datetime
from unittest.mock import patch

import db
import monitor
from config import ensure_pst


class MonitorCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "traffic-test.db")
        db.init_db(self.db_path)
        self.db_patch = patch.object(monitor, "DB_FILE", self.db_path)
        self.db_patch.start()

        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executemany(
                """
                INSERT INTO incidents
                    (incident_no, date, timestamp, source, active, details)
                VALUES (?, '2026-07-17', '2026-07-17 12:00:00', ?, 1, '[]')
                """,
                [("CHP-1", "CHP"), ("SDPD-1", "SDPD")],
            )
            conn.commit()

    def tearDown(self):
        monitor._batch_future = None
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def _active_state(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return dict(conn.execute("SELECT incident_no, active FROM incidents"))

    def test_failed_source_is_not_deactivated(self):
        def failed_chp():
            raise RuntimeError("upstream unavailable")

        with patch.object(monitor, "BATCH_LLM_ENABLED", False):
            monitor.run_monitor_cycle({"CHP": failed_chp, "SDPD": lambda: []})

        self.assertEqual(
            self._active_state(),
            {"CHP-1": 1, "SDPD-1": 0},
        )

    def test_all_source_failure_preserves_every_active_incident(self):
        def failed():
            raise RuntimeError("upstream unavailable")

        with (
            patch.object(monitor, "BATCH_LLM_ENABLED", False),
            self.assertRaisesRegex(RuntimeError, "All configured traffic sources failed"),
        ):
            monitor.run_monitor_cycle({"CHP": failed, "SDPD": failed})

        self.assertEqual(
            self._active_state(),
            {"CHP-1": 1, "SDPD-1": 1},
        )

    def test_batch_submission_waits_for_each_incidents_collection_window(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET batch_queued_at = CASE incident_no
                    WHEN 'CHP-1' THEN '2026-07-17 11:50:00'
                    ELSE '2026-07-17 11:59:00'
                END,
                batch_enriched_at = NULL
                """
            )
            conn.commit()

        class CapturingExecutor:
            records = None

            def submit(self, _function, records):
                self.records = records
                future = Future()
                future.set_result(None)
                return future

        executor = CapturingExecutor()
        fixed_now = ensure_pst(datetime(2026, 7, 17, 12, 0, 0))
        monitor._batch_future = None
        with (
            patch.object(monitor, "BATCH_LLM_ENABLED", True),
            patch.object(monitor, "BATCH_LLM_INTERVAL_SECONDS", 300),
            patch.object(monitor, "_batch_executor", executor),
            patch.object(monitor, "now_pst", return_value=fixed_now),
        ):
            monitor._submit_batch_refinement_if_due()

        self.assertEqual(
            [record["incident_no"] for record in executor.records],
            ["CHP-1"],
        )


if __name__ == "__main__":
    unittest.main()
