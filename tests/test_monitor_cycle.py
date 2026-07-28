import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

from backend import db, monitor


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
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def _active_state(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return dict(conn.execute("SELECT incident_no, active FROM incidents"))

    def test_monitor_has_no_deferred_batch_refinement_pipeline(self):
        self.assertFalse(hasattr(monitor, "_submit_batch_refinement_if_due"))
        self.assertFalse(hasattr(monitor, "_refine_description_batch"))

    def test_pending_mistral_refresh_is_recovered_after_restart(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET details = '["Pending lane update"]',
                    llm_pending_at = '2026-07-17 12:01:00', active = 1
                WHERE incident_no = 'CHP-1'
                """
            )
            conn.commit()

        with patch.object(monitor, "_schedule_description_refresh") as schedule:
            monitor._recover_pending_mistral_refreshes()

        recovered = schedule.call_args.args[0]
        self.assertEqual(recovered["No."], "CHP-1")
        self.assertEqual(recovered["Details"], ["Pending lane update"])

    def test_transient_mistral_failure_keeps_pending_work_for_retry(self):
        details = '["Lane blocked"]'
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET details = ?, llm_pending_at = '2026-07-17 12:01:00', active = 1
                WHERE incident_no = 'CHP-1'
                """,
                (details,),
            )
            conn.commit()

        incident = {
            "No.": "CHP-1",
            "Date": "2026-07-17",
            "Details": ["Lane blocked"],
        }
        with patch.object(
            monitor,
            "generate_description",
            side_effect=RuntimeError("temporary provider failure"),
        ):
            monitor._refresh_incident_description(incident)

        with closing(sqlite3.connect(self.db_path)) as conn:
            pending_after_failure = conn.execute(
                "SELECT llm_pending_at FROM incidents WHERE incident_no = 'CHP-1'"
            ).fetchone()[0]
        self.assertIsNotNone(pending_after_failure)

        with patch.object(
            monitor,
            "generate_description",
            return_value=("Lane remains blocked", 2),
        ):
            monitor._refresh_incident_description(incident)

        with closing(sqlite3.connect(self.db_path)) as conn:
            pending_after_success = conn.execute(
                "SELECT llm_pending_at FROM incidents WHERE incident_no = 'CHP-1'"
            ).fetchone()[0]
        self.assertIsNone(pending_after_success)

    def test_existing_incident_detail_changes_get_a_mistral_refresh(self):
        incident = {
            "No.": "CHP-1",
            "Date": "2026-07-17",
            "Source": "CHP",
            "Details": ["Two lanes now blocked"],
            "Latitude": 32.7,
            "Longitude": -117.1,
        }
        existing = {
            "incident_no": "CHP-1",
            "date": "2026-07-17",
            "details": '["One lane blocked"]',
            "latitude": 32.7,
            "longitude": -117.1,
        }

        with (
            patch.object(monitor, "save_or_update_incident"),
            patch.object(monitor, "_schedule_description_refresh") as schedule,
        ):
            monitor.process_and_save_incident(incident, existing)

        schedule.assert_called_once_with(incident)

    def test_stale_mistral_refresh_cannot_overwrite_newer_incident_details(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET details = ?, description = ?, active = 1
                WHERE incident_no = 'CHP-1'
                """,
                ('["Newest lane update"]', "Newest summary"),
            )
            conn.commit()

        stale_incident = {
            "No.": "CHP-1",
            "Date": "2026-07-17",
            "Details": ["Older lane update"],
        }
        with patch.object(
            monitor,
            "generate_description",
            return_value=("Stale summary", 2),
        ):
            monitor._refresh_incident_description(stale_incident)

        with closing(sqlite3.connect(self.db_path)) as conn:
            description = conn.execute(
                "SELECT description FROM incidents WHERE incident_no = 'CHP-1'"
            ).fetchone()[0]

        self.assertEqual(description, "Newest summary")

    def test_mistral_refresh_cannot_overwrite_inactive_incident_summary(self):
        details = '["Lane reopened"]'
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET details = ?, description = ?, active = 0
                WHERE incident_no = 'CHP-1'
                """,
                (details, "Incident cleared"),
            )
            conn.commit()

        incident = {
            "No.": "CHP-1",
            "Date": "2026-07-17",
            "Details": "Lane reopened",
        }
        with patch.object(
            monitor,
            "generate_description",
            return_value=("Still blocking a lane", 2),
        ):
            monitor._refresh_incident_description(incident)

        with closing(sqlite3.connect(self.db_path)) as conn:
            description = conn.execute(
                "SELECT description FROM incidents WHERE incident_no = 'CHP-1'"
            ).fetchone()[0]

        self.assertEqual(description, "Incident cleared")

    def test_final_mistral_summary_atomically_marks_incident_inactive(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE incidents
                SET details = '["Lane reopened"]', description = 'Old summary', active = 1
                WHERE incident_no = 'CHP-1'
                """
            )
            conn.commit()

        with patch.object(
            monitor,
            "generate_description",
            return_value=("Incident cleared", 1),
        ):
            monitor._generate_final_descriptions({"CHP": set()})

        with closing(sqlite3.connect(self.db_path)) as conn:
            description, active = conn.execute(
                "SELECT description, active FROM incidents WHERE incident_no = 'CHP-1'"
            ).fetchone()

        self.assertEqual(description, "Incident cleared")
        self.assertEqual(active, 0)

    def test_failed_source_is_not_deactivated(self):
        def failed_chp():
            raise RuntimeError("upstream unavailable")

        monitor.run_monitor_cycle({"CHP": failed_chp, "SDPD": lambda: []})

        self.assertEqual(
            self._active_state(),
            {"CHP-1": 1, "SDPD-1": 0},
        )

    def test_all_source_failure_preserves_every_active_incident(self):
        def failed():
            raise RuntimeError("upstream unavailable")

        with self.assertRaisesRegex(RuntimeError, "All configured traffic sources failed"):
            monitor.run_monitor_cycle({"CHP": failed, "SDPD": failed})

        self.assertEqual(
            self._active_state(),
            {"CHP-1": 1, "SDPD-1": 1},
        )


if __name__ == "__main__":
    unittest.main()
