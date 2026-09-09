import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import init_db, get_db_connection
from simulator.failure_simulator import set_failure_status, is_failure_active
from eta_engine.fallback import get_fallback_gps, get_fallback_traffic, get_fallback_speed

class TestFailureFallbacks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Ensure database is initialized for tests
        init_db()

    def setUp(self):
        # Reset failures before each test
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE failures SET status = 'INACTIVE';")
        conn.commit()
        conn.close()

    def test_toggle_failure_status(self):
        # Check initial
        self.assertFalse(is_failure_active('gps'))
        
        # Activate GPS failure
        set_failure_status('gps', 'ACTIVE')
        self.assertTrue(is_failure_active('gps'))

        # Deactivate GPS failure
        set_failure_status('gps', 'INACTIVE')
        self.assertFalse(is_failure_active('gps'))

    def test_gps_fallback(self):
        # No fallback initially
        self.assertIsNone(get_fallback_gps('101'))
        
        # Activate GPS failure
        set_failure_status('gps', 'ACTIVE')
        gps = get_fallback_gps('101')
        self.assertIsNotNone(gps)
        # Should be valid lat/lon coordinates in the SF area
        lat, lon = gps[0], gps[1]
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lon, float)
        # Latitude should be in San Francisco range (37.5 to 38.0)
        self.assertGreater(lat, 37.5)
        self.assertLess(lat, 38.0)
        # Longitude should be in SF range (-122.6 to -122.3)
        self.assertGreater(lon, -122.6)
        self.assertLess(lon, -122.3)

    def test_traffic_fallback(self):
        # No fallback initially
        self.assertIsNone(get_fallback_traffic('Route 1'))
        
        # Activate traffic failure
        set_failure_status('traffic', 'ACTIVE')
        self.assertEqual(get_fallback_traffic('Route 1'), 'MEDIUM')

    def test_sensor_fallback(self):
        # No fallback initially
        self.assertIsNone(get_fallback_speed('101'))
        
        # Activate sensor failure
        set_failure_status('sensor', 'ACTIVE')
        self.assertEqual(get_fallback_speed('101'), 30.0)

if __name__ == '__main__':
    unittest.main()
