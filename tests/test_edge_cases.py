import unittest
import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.database import (
    init_db, get_db_connection, is_telemetry_processed, record_processed_telemetry
)
from eta_engine.eta_calculator import (
    str_to_minutes, minutes_to_str, calculate_dwell_time, get_traffic_delay_minutes, get_proposed_eta
)
from eta_engine.fallback import (
    is_failure_active, get_fallback_gps, get_fallback_traffic, get_fallback_speed
)
from simulator.failure_simulator import set_failure_status
from simulator.simulation import synchronize_network_queue, load_sim_state, save_sim_state

class TestEdgeCasesAndBoundaries(unittest.TestCase):
    """
    Validates boundary conditions and edge cases across ETA engine,
    failure fallbacks, offline queue, and API validation.
    """

    @classmethod
    def setUpClass(cls):
        init_db()
        app.testing = True
        cls.client = app.test_client()

    def setUp(self):
        # Reset failure flags to clean baseline
        set_failure_status('gps', 'INACTIVE')
        set_failure_status('network', 'INACTIVE')
        set_failure_status('traffic', 'INACTIVE')
        set_failure_status('sensor', 'INACTIVE')

    # --------------------------------------------------------------------------
    # 1. Attendance & Dwell Time Edge Cases
    # --------------------------------------------------------------------------
    def test_zero_attendance_dwell(self):
        """Zero students present should return exactly the 30-second base dwell time."""
        dwell = calculate_dwell_time(0)
        self.assertEqual(dwell, 30)

    def test_negative_or_none_attendance_dwell(self):
        """Negative or None student counts should be treated as 0 without throwing exceptions."""
        self.assertEqual(calculate_dwell_time(-5), 30)
        self.assertEqual(calculate_dwell_time(None), 30)

    def test_unusually_high_attendance_dwell(self):
        """High attendance (e.g. 50 students) should scale linearly without overflow."""
        dwell = calculate_dwell_time(50)
        # 30s base + (50 * 20s) = 1030s (approx 17.17 minutes)
        self.assertEqual(dwell, 1030)

    # --------------------------------------------------------------------------
    # 2. Traffic Level Edge Cases
    # --------------------------------------------------------------------------
    def test_invalid_or_missing_traffic_value(self):
        """Invalid traffic string or None should safely default to 0 delay."""
        self.assertEqual(get_traffic_delay_minutes(""), 0)
        self.assertEqual(get_traffic_delay_minutes(None), 0)
        self.assertEqual(get_traffic_delay_minutes("SEVERE_JAM"), 0)
        self.assertEqual(get_traffic_delay_minutes("GRIDLOCK"), 0)

    def test_case_insensitive_traffic_value(self):
        """Traffic strings in lower or mixed case should be parsed correctly."""
        self.assertEqual(get_traffic_delay_minutes("low"), 0)
        self.assertEqual(get_traffic_delay_minutes("medium"), 3)
        self.assertEqual(get_traffic_delay_minutes("High"), 7)

    # --------------------------------------------------------------------------
    # 3. GPS & Sensor Telemetry Edge Cases
    # --------------------------------------------------------------------------
    def test_inactive_bus_eta_returns_empty(self):
        """Querying ETA for an inactive bus should return empty dictionaries cleanly."""
        etas, explanations = get_proposed_eta("104", "08:00 AM") # 104 is seeded as INACTIVE
        self.assertEqual(etas, {})
        self.assertEqual(explanations, {})

    def test_abnormal_sensor_speed_fallback(self):
        """When sensor failure is active, abnormal zero speed must fall back to 30.0 km/h."""
        set_failure_status('sensor', 'ACTIVE')
        speed = get_fallback_speed('101')
        self.assertEqual(speed, 30.0)

    def test_gps_fallback_inactive_returns_none(self):
        """When GPS failure is inactive, fallback location should return None."""
        self.assertIsNone(get_fallback_gps('101'))

    def test_gps_fallback_active_returns_coordinates(self):
        """When GPS failure is active, fallback should return last recorded coordinates."""
        set_failure_status('gps', 'ACTIVE')
        coords = get_fallback_gps('101')
        self.assertIsNotNone(coords)
        self.assertEqual(len(coords), 2)
        lat, lon = coords
        self.assertAlmostEqual(lat, 37.7949, places=2)
        self.assertAlmostEqual(lon, -122.4394, places=2)

    # --------------------------------------------------------------------------
    # 4. Clock and Time Formatting Edge Cases
    # --------------------------------------------------------------------------
    def test_midnight_and_boundary_time_conversion(self):
        """Time conversions should handle midnight boundaries and wraparound."""
        self.assertEqual(str_to_minutes("12:00 AM"), 0)
        self.assertEqual(str_to_minutes("11:59 PM"), 1439)
        self.assertEqual(minutes_to_str(0), "12:00 AM")
        self.assertEqual(minutes_to_str(1440), "12:00 AM") # 24h wraparound
        self.assertEqual(minutes_to_str(1470), "12:30 AM")

    def test_malformed_time_string_degradation(self):
        """Malformed time strings must gracefully degrade to 08:00 AM (480) baseline."""
        self.assertEqual(str_to_minutes("invalid-string"), 480)
        self.assertEqual(str_to_minutes("bad:time format"), 480)
        self.assertEqual(str_to_minutes("not_a_time"), 480)
        self.assertEqual(str_to_minutes(""), 480)

    # --------------------------------------------------------------------------
    # 5. Offline Queue & Synchronization Edge Cases
    # --------------------------------------------------------------------------
    def test_empty_offline_queue_synchronization(self):
        """Synchronizing an empty offline queue should return 0 and not fail."""
        state = load_sim_state()
        state['store_and_forward_queue'] = []
        save_sim_state(state)

        count = synchronize_network_queue()
        self.assertEqual(count, 0)

    def test_telemetry_deduplication_isolation(self):
        """Recording a telemetry event ensures duplicate check returns True."""
        ev_id = str(uuid.uuid4())
        self.assertFalse(is_telemetry_processed(ev_id))

        record_processed_telemetry(
            event_id=ev_id,
            bus_id="101",
            route_id="Route 1",
            latitude=37.7949,
            longitude=-122.4394,
            speed=30.0
        )
        self.assertTrue(is_telemetry_processed(ev_id))

        # Re-recording with duplicate ID must not raise exception (INSERT OR IGNORE)
        try:
            record_processed_telemetry(
                event_id=ev_id,
                bus_id="101",
                route_id="Route 1",
                latitude=37.7949,
                longitude=-122.4394,
                speed=30.0
            )
        except Exception as e:
            self.fail(f"Duplicate record insertion raised unexpected exception: {e}")

    # --------------------------------------------------------------------------
    # 6. API Error Validation Edge Cases
    # --------------------------------------------------------------------------
    def test_api_attendance_invalid_status_rejects_400(self):
        """Invalid attendance status must return 400 Bad Request."""
        res = self.client.post('/api/attendance', json={'student_id': 'S101', 'status': 'Late'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.get_json())

    def test_api_attendance_missing_student_id_rejects_400(self):
        """Missing student_id in attendance update must return 400."""
        res = self.client.post('/api/attendance', json={'status': 'Present'})
        self.assertEqual(res.status_code, 400)

    def test_api_traffic_invalid_level_rejects_400(self):
        """Invalid traffic level must return 400 Bad Request."""
        res = self.client.post('/api/traffic', json={'route_id': 'Route 1', 'traffic_level': 'SEVERE'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.get_json())

    def test_api_manual_eta_missing_fields_rejects_400(self):
        """Missing manual_eta or next_stop_id must return 400 Bad Request."""
        res = self.client.post('/api/manual-eta', json={'bus_id': '101'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('error', res.get_json())

    def test_api_telemetry_missing_bus_id_rejects_400(self):
        """POST /api/telemetry without bus_id must return 400 error."""
        res = self.client.post('/api/telemetry', json={'latitude': 37.79, 'longitude': -122.43})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json().get('status'), 'ERROR')

    def test_api_eta_inactive_or_invalid_bus_rejects_400(self):
        """Querying /api/eta/<bus_id> for non-existent bus returns 400."""
        res = self.client.get('/api/eta/999')
        self.assertEqual(res.status_code, 400)

if __name__ == '__main__':
    unittest.main()
