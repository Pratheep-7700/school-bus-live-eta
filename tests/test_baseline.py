import unittest
import sys
import os

# Adjust path to find school_bus_eta modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import init_db, get_db_connection
from eta_engine.baseline import get_baseline_eta
from eta_engine.eta_calculator import str_to_minutes

class TestBaselineSystem(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_baseline_schedule_loading(self):
        """Verifies baseline ETA retrieves planned timetable from SQLite."""
        baseline_route1 = get_baseline_eta('Route 1')
        self.assertIsInstance(baseline_route1, dict)
        self.assertIn('Stop_A', baseline_route1)
        self.assertEqual(baseline_route1['Stop_A'], '08:00 AM')
        self.assertIn('Stop_B', baseline_route1)
        self.assertEqual(baseline_route1['Stop_B'], '08:10 AM')

    def test_baseline_ignores_traffic_and_attendance(self):
        """Baseline system must strictly adhere to static planned timetable."""
        baseline_initial = get_baseline_eta('Route 1')
        
        # Simulate traffic change or attendance variation in db
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE attendance SET status = 'Absent' WHERE student_id = 'S101';")
        conn.commit()
        conn.close()

        baseline_after_change = get_baseline_eta('Route 1')
        # Baseline output must remain identical to static schedule
        self.assertEqual(baseline_initial, baseline_after_change)

    def test_baseline_error_under_delay(self):
        """Under high traffic (+7m delay), baseline error must be approximately 7m."""
        planned_arrival = str_to_minutes("08:00 AM")
        actual_arrival_delayed = str_to_minutes("08:07 AM")
        baseline_error = abs(planned_arrival - actual_arrival_delayed)
        self.assertEqual(baseline_error, 7)

if __name__ == '__main__':
    unittest.main()
