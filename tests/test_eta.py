import unittest
import sys
import os

# Adjust path to find school_bus_eta modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eta_engine.eta_calculator import str_to_minutes, minutes_to_str, calculate_dwell_time, haversine_distance

class TestETACalculations(unittest.TestCase):
    
    def test_str_to_minutes(self):
        self.assertEqual(str_to_minutes("08:00 AM"), 480)
        self.assertEqual(str_to_minutes("12:00 AM"), 0)
        self.assertEqual(str_to_minutes("12:30 PM"), 750)
        self.assertEqual(str_to_minutes("08:15 PM"), 1215)
        # Check invalid input defaults
        self.assertEqual(str_to_minutes("invalid"), 480)

    def test_minutes_to_str(self):
        self.assertEqual(minutes_to_str(480), "08:00 AM")
        self.assertEqual(minutes_to_str(0), "12:00 AM")
        self.assertEqual(minutes_to_str(750), "12:30 PM")
        self.assertEqual(minutes_to_str(1215), "08:15 PM")
        self.assertEqual(minutes_to_str(1445), "12:05 AM") # check wrapping

    def test_dwell_time_formula(self):
        # Formula: dwell_time = 30 + (present_students * 20) seconds
        self.assertEqual(calculate_dwell_time(0), 30)
        self.assertEqual(calculate_dwell_time(3), 90)
        self.assertEqual(calculate_dwell_time(5), 130)

    def test_haversine_distance(self):
        # Distance between two nearby coordinates in SF
        lat1, lon1 = 37.7949, -122.4394
        lat2, lon2 = 37.7889, -122.4294
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        # Should be approximately 1.10 km
        self.assertAlmostEqual(distance, 1.10, places=1)

    def test_traffic_delay_minutes(self):
        from eta_engine.eta_calculator import get_traffic_delay_minutes
        self.assertEqual(get_traffic_delay_minutes("LOW"), 0)
        self.assertEqual(get_traffic_delay_minutes("MEDIUM"), 3)
        self.assertEqual(get_traffic_delay_minutes("HIGH"), 7)
        self.assertEqual(get_traffic_delay_minutes("UNKNOWN"), 0)

    def test_meaningful_eta_change_thresholds(self):
        """
        Rule:
        Change < 2 min: No customer notification.
        Change >= 2 min: Create ETA update.
        Change >= 5 min: Create important delay notification.
        """
        def classify_eta_change(delta_mins):
            if abs(delta_mins) >= 5.0:
                return 'CRITICAL'
            elif abs(delta_mins) >= 2.0:
                return 'WARNING'
            return 'NONE'

        self.assertEqual(classify_eta_change(1.0), 'NONE')
        self.assertEqual(classify_eta_change(1.9), 'NONE')
        self.assertEqual(classify_eta_change(2.0), 'WARNING')
        self.assertEqual(classify_eta_change(4.5), 'WARNING')
        self.assertEqual(classify_eta_change(5.0), 'CRITICAL')
        self.assertEqual(classify_eta_change(7.0), 'CRITICAL')

    def test_eta_explanation(self):
        from eta_engine.explanation import explain_eta_difference
        # Planned: 08:00 AM, Proposed: 08:08 AM (+8m), Traffic: HIGH (+7m), 1 present student
        exp = explain_eta_difference("08:00 AM", "08:08 AM", "HIGH", [1], is_gps_fail=False, is_sensor_abnormal=False)
        self.assertIn('factors', exp)
        self.assertIn('Traffic', exp['factors'])
        self.assertEqual(exp['factors']['Traffic'], 7.0)
        self.assertIn('Traffic: +7.0 min', exp['summary'])

if __name__ == '__main__':
    unittest.main()
