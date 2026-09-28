import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.eta_explanation_service import ETAExplanationService, explain_eta

class TestETAExplanationService(unittest.TestCase):
    """
    Tests for Improvement 1: Natural Language ETA Explanations rule engine.
    Validates data-backed reason determination, dominant factor ranking,
    structured output formats, and mandatory fallbacks.
    """

    def test_01_bus_on_schedule(self):
        """When delay <= 1 minute, status must be ON_TIME with 'Bus is currently on schedule.'"""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:40 AM"
        )
        self.assertEqual(result["status"], "ON_TIME")
        self.assertEqual(result["primary_reason"], "ON_SCHEDULE")
        self.assertIn("Bus is currently on schedule", result["explanation"])
        self.assertEqual(len(result["factors"]), 0)

        # Marginal 1 minute delay is still on schedule
        result_1m = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:41 AM"
        )
        self.assertEqual(result_1m["status"], "ON_TIME")

    def test_02_bus_running_early(self):
        """When delay < -1 minute, status must be EARLY."""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:37 AM"
        )
        self.assertEqual(result["status"], "EARLY")
        self.assertEqual(result["primary_reason"], "AHEAD_OF_SCHEDULE")
        self.assertIn("ahead of schedule", result["explanation"].lower())

    def test_03_boarding_time_delay(self):
        """When previous stop boarding time exceeds average, identify HIGH_BOARDING_TIME."""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:45 AM",
            previous_stop_boarding_time=195.0, # 195s vs 45s average = 150s (2.5 mins)
            average_boarding_time=45.0
        )
        self.assertEqual(result["status"], "DELAYED")
        self.assertEqual(result["primary_reason"], "HIGH_BOARDING_TIME")
        self.assertIn("higher-than-average boarding time at the previous stop", result["explanation"])
        self.assertEqual(result["delay_minutes"], 5.0)
        self.assertGreater(len(result["factors"]), 0)
        self.assertEqual(result["factors"][0]["factor"], "boarding_time")

    def test_04_traffic_delay(self):
        """When traffic delay is dominant, identify TRAFFIC_DELAY."""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:48 AM",
            traffic_delay=8.0
        )
        self.assertEqual(result["status"], "DELAYED")
        self.assertEqual(result["primary_reason"], "TRAFFIC_DELAY")
        self.assertIn("slower traffic on the current route", result["explanation"])
        self.assertEqual(result["factors"][0]["factor"], "traffic")
        self.assertEqual(result["factors"][0]["impact_minutes"], 8.0)

    def test_05_slower_route_travel_time(self):
        """When travel time exceeds expected, identify ROUTE_TRAVEL_DELAY."""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:44 AM",
            expected_travel_time=10.0,
            actual_or_est_travel_time=14.0
        )
        self.assertEqual(result["status"], "DELAYED")
        self.assertEqual(result["primary_reason"], "ROUTE_TRAVEL_DELAY")
        self.assertIn("slower-than-expected travel time", result["explanation"])

    def test_06_multiple_factors_combination(self):
        """When multiple factors exist, identify dominant and mention secondary factor."""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:47 AM",
            previous_stop_boarding_time=250.0, # ~3.4 min impact
            average_boarding_time=45.0,
            traffic_delay=2.0 # secondary factor
        )
        self.assertEqual(result["status"], "DELAYED")
        self.assertEqual(result["primary_reason"], "HIGH_BOARDING_TIME")
        self.assertIn("mainly due to", result["explanation"])
        self.assertIn("higher-than-average boarding time", result["explanation"])
        self.assertIn("slower traffic", result["explanation"])
        self.assertEqual(len(result["factors"]), 2)

    def test_07_mandatory_unknown_fallback(self):
        """When delay exists but telemetry does not support a specific factor, return mandatory fallback."""
        result = explain_eta(
            scheduled_arrival_time="08:40 AM",
            predicted_arrival_time="08:45 AM"
            # No factors provided
        )
        self.assertEqual(result["status"], "DELAYED")
        self.assertEqual(result["primary_reason"], "UNKNOWN_CAUSE")
        self.assertIn("The system could not determine a specific cause from the available telemetry", result["explanation"])
        self.assertEqual(len(result["factors"]), 0)

    def test_08_structured_format_contract(self):
        """Validates all mandatory keys in the structured response contract."""
        result = explain_eta(
            scheduled_arrival_time="08:42",
            predicted_arrival_time="08:47",
            traffic_delay=5.0
        )
        for key in ["eta", "delay_minutes", "status", "primary_reason", "explanation", "factors"]:
            self.assertIn(key, result)
        self.assertIsInstance(result["factors"], list)
        self.assertIsInstance(result["delay_minutes"], float)

if __name__ == '__main__':
    unittest.main()
