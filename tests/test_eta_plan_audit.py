import unittest
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.database import init_db, get_db_connection, insert_eta_plan_audit, query_eta_plan_audit, get_eta_plan_audit_by_id

class TestETAPlanAuditTrail(unittest.TestCase):
    """
    Tests for Improvement 2: Audit Trail Schema and Immutable Ledger.
    Validates append-only semantics, historical timeline, API endpoints,
    and trigger filtering.
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        app.testing = True
        cls.client = app.test_client()

    def test_01_schema_columns_exist(self):
        """Validates that all specified schema columns exist in eta_plan_audit table."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(eta_plan_audit);")
        columns = [row['name'] for row in cursor.fetchall()]
        conn.close()

        required_columns = [
            "id", "bus_id", "route_id", "trip_id", "stop_id",
            "event_type", "trigger_factor", "trigger_details",
            "previous_eta", "new_eta", "previous_delay_minutes",
            "new_delay_minutes", "previous_plan", "new_plan",
            "explanation", "telemetry_snapshot", "created_at", "created_by"
        ]
        for col in required_columns:
            self.assertIn(col, columns, f"Column '{col}' must exist in eta_plan_audit")

    def test_02_immutable_append_only_timeline(self):
        """Verifies that ETA updates insert new records without modifying previous ones."""
        # Insert Record 1: 08:40
        id1 = insert_eta_plan_audit(
            bus_id="101",
            route_id="Route 1",
            previous_eta="08:35",
            new_eta="08:40",
            previous_delay_minutes=0.0,
            new_delay_minutes=5.0,
            event_type="RECALCULATION",
            trigger_factor="GPS_TELEMETRY",
            explanation="Initial telemetry recalculation"
        )
        rec1 = get_eta_plan_audit_by_id(id1)
        self.assertIsNotNone(rec1)
        self.assertEqual(rec1["new_eta"], "08:40")

        # Insert Record 2: 08:40 -> 08:45
        id2 = insert_eta_plan_audit(
            bus_id="101",
            route_id="Route 1",
            previous_eta="08:40",
            new_eta="08:45",
            previous_delay_minutes=5.0,
            new_delay_minutes=10.0,
            event_type="RECALCULATION",
            trigger_factor="HIGH_BOARDING_TIME",
            explanation="Higher boarding time at previous stop"
        )
        rec2 = get_eta_plan_audit_by_id(id2)
        self.assertIsNotNone(rec2)
        self.assertEqual(rec2["previous_eta"], "08:40")
        self.assertEqual(rec2["new_eta"], "08:45")

        # Verify Record 1 was NOT modified
        rec1_after = get_eta_plan_audit_by_id(id1)
        self.assertEqual(rec1_after["new_eta"], "08:40")
        self.assertNotEqual(id1, id2)

    def test_03_audit_api_list_and_filters(self):
        """Validates GET /api/audit/eta with query filters."""
        # Insert test records
        insert_eta_plan_audit(
            bus_id="999",
            route_id="Route 9",
            trip_id="TRIP-999",
            trigger_factor="TEST_TRIGGER_SPECIAL",
            new_eta="09:00 AM",
            explanation="Special filter test"
        )

        # 1. Query without filters
        res = self.client.get('/api/audit/eta')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        # 2. Filter by bus_id
        res_bus = self.client.get('/api/audit/eta?bus_id=999')
        self.assertEqual(res_bus.status_code, 200)
        data_bus = res_bus.get_json()
        self.assertTrue(all(r["bus_id"] == "999" for r in data_bus))

        # 3. Filter by trigger_factor
        res_trigger = self.client.get('/api/audit/eta?trigger_factor=TEST_TRIGGER_SPECIAL')
        self.assertEqual(res_trigger.status_code, 200)
        data_trigger = res_trigger.get_json()
        self.assertTrue(all(r["trigger_factor"] == "TEST_TRIGGER_SPECIAL" for r in data_trigger))

    def test_04_audit_api_get_by_id(self):
        """Validates GET /api/audit/eta/<id> returns complete record with snapshot and plans."""
        snapshot = {"speed": 34.5, "battery": 98}
        prev_plan = {"eta": "08:15 AM"}
        new_plan = {"eta": "08:18 AM"}

        rec_id = insert_eta_plan_audit(
            bus_id="102",
            route_id="Route 2",
            previous_eta="08:15 AM",
            new_eta="08:18 AM",
            trigger_factor="TRAFFIC_DELAY",
            trigger_details="Segment congestion detected",
            previous_plan=prev_plan,
            new_plan=new_plan,
            telemetry_snapshot=snapshot,
            explanation="Traffic delay added 3 minutes"
        )

        res = self.client.get(f'/api/audit/eta/{rec_id}')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["id"], rec_id)
        self.assertEqual(data["bus_id"], "102")
        self.assertEqual(data["trigger_factor"], "TRAFFIC_DELAY")
        self.assertIn("speed", data["telemetry_snapshot"])

        # Non-existent ID returns 404
        res_404 = self.client.get('/api/audit/eta/999999')
        self.assertEqual(res_404.status_code, 404)

if __name__ == '__main__':
    unittest.main()
