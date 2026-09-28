import unittest
import json
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.database import init_db, get_db_connection, is_telemetry_processed

class TestStoreAndForwardTelemetry(unittest.TestCase):
    """
    Tests for Improvement 3: Store-and-Forward Telemetry Ingestion and Deduplication.
    Validates online ingestion flow, duplicate rejection, batch synchronization,
    and automatic audit logging.
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        app.testing = True
        cls.client = app.test_client()

    def test_01_telemetry_ingestion_success(self):
        """Validates that valid telemetry updates bus, recalculates ETA, and inserts audit record."""
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "bus_id": "101",
            "timestamp": "08:05 AM",
            "latitude": 37.7949,
            "longitude": -122.4394,
            "speed": 28.5,
            "route_id": "Route 1",
            "trip_id": "TRIP-Route1"
        }

        res = self.client.post('/api/telemetry', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["event_id"], event_id)
        self.assertIn("eta", data)
        self.assertIn("explanation", data)
        self.assertIn("audit_id", data)

        # Verify event was recorded for deduplication
        self.assertTrue(is_telemetry_processed(event_id))

    def test_02_telemetry_deduplication(self):
        """Duplicate event_id must return DUPLICATE status and not be re-inserted."""
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "bus_id": "101",
            "timestamp": "08:06 AM",
            "latitude": 37.7940,
            "longitude": -122.4380,
            "speed": 29.0,
            "route_id": "Route 1"
        }

        # First delivery
        res1 = self.client.post('/api/telemetry', json=payload)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.get_json()["status"], "SUCCESS")

        # Duplicate delivery
        res2 = self.client.post('/api/telemetry', json=payload)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["status"], "DUPLICATE")
        self.assertIn("already processed", data2["message"].lower())

    def test_03_batch_sync_queue(self):
        """Validates POST /api/telemetry/sync handles multiple buffered items with deduplication."""
        id1 = str(uuid.uuid4())
        id2 = str(uuid.uuid4())

        batch = [
            {
                "event_id": id1,
                "bus_id": "102",
                "timestamp": "08:07 AM",
                "latitude": 37.7550,
                "longitude": -122.4490,
                "speed": 31.0,
                "route_id": "Route 2"
            },
            {
                "event_id": id2,
                "bus_id": "103",
                "timestamp": "08:07 AM",
                "latitude": 37.7550,
                "longitude": -122.3990,
                "speed": 30.5,
                "route_id": "Route 3"
            }
        ]

        # Sync batch
        res = self.client.post('/api/telemetry/sync', json={"batch": batch})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["processed_count"], 2)
        self.assertEqual(data["duplicate_count"], 0)

        # Resend same batch (simulating network retry of already-synced batch)
        res_retry = self.client.post('/api/telemetry/sync', json={"batch": batch})
        self.assertEqual(res_retry.status_code, 200)
        data_retry = res_retry.get_json()
        self.assertEqual(data_retry["duplicate_count"], 2)
        self.assertEqual(data_retry["processed_count"], 0)

    def test_04_missing_bus_id_error(self):
        """Missing bus_id must return 400 error."""
        res = self.client.post('/api/telemetry', json={"event_id": str(uuid.uuid4())})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["status"], "ERROR")

if __name__ == '__main__':
    unittest.main()
