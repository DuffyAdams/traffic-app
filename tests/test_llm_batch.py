import json
import unittest
from types import SimpleNamespace

from llm import _format_batch_incident, _parse_batch_response


def _response(payload):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload))
            )
        ]
    )


class BatchDescriptionTests(unittest.TestCase):
    def setUp(self):
        self.payload = [
            _format_batch_incident(
                1,
                {
                    "incident_no": "A-1",
                    "location": "I-5 / Main St",
                    "type": "SIG Alert",
                    "details": '["Two lanes blocked"]',
                },
            ),
            _format_batch_incident(
                2,
                {
                    "incident_no": "A-2",
                    "location": "SR-163 / Friars Rd",
                    "type": "Traffic Collision",
                    "details": [],
                },
            ),
        ]

    def test_validates_complete_batch_and_forces_sig_alert_to_five(self):
        response = _response(
            {
                "incidents": [
                    {"item_id": 1, "summary": "Two lanes blocked. 🚧", "severity": 3},
                    {"item_id": 2, "summary": "Collision reported. 🚗", "severity": 2},
                ]
            }
        )

        results = _parse_batch_response(response, self.payload)

        self.assertEqual(results[0]["severity"], 5)
        self.assertEqual(results[1]["severity"], 2)

    def test_rejects_incomplete_batch(self):
        response = _response(
            {
                "incidents": [
                    {"item_id": 1, "summary": "Two lanes blocked.", "severity": 5}
                ]
            }
        )

        with self.assertRaisesRegex(ValueError, "omitted"):
            _parse_batch_response(response, self.payload)

    def test_rejects_duplicate_item_ids(self):
        response = _response(
            {
                "incidents": [
                    {"item_id": 1, "summary": "First result.", "severity": 5},
                    {"item_id": 1, "summary": "Duplicate result.", "severity": 5},
                ]
            }
        )

        with self.assertRaisesRegex(ValueError, "duplicate"):
            _parse_batch_response(response, self.payload)


if __name__ == "__main__":
    unittest.main()
