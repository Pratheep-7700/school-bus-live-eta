import unittest
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database.database import init_db

class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        app.testing = True
        cls.client = app.test_client()

    def test_01_get_buses(self):
        res = self.client.get('/api/buses')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 5)
        self.assertIn('route_id', data[0])

    def test_02_get_routes(self):
        res = self.client.get('/api/routes')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data), 3)
        self.assertTrue(all(len(r.get('stops', [])) > 0 for r in data))

    def test_03_get_students(self):
        res = self.client.get('/api/students')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data), 30)
        self.assertTrue(all('attendance_status' in s for s in data))

    def test_04_failures_lifecycle(self):
        # Reset all failures first
        self.client.post('/api/failure/gps', json={'active': False})
        self.client.post('/api/failure/network', json={'active': False})
        self.client.post('/api/failure/traffic', json={'active': False})
        self.client.post('/api/failure/sensor', json={'active': False})

        res = self.client.get('/api/failures')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        for k in ['gps', 'network', 'traffic', 'sensor']:
            self.assertIn(k, data)
            self.assertEqual(data[k], 'INACTIVE')

    def test_05_simulation_state_and_controls(self):
        res = self.client.get('/api/simulation/state')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('current_time', data)
        self.assertEqual(len(data.get('bus_states', {})), 3)

        # Reset
        res = self.client.post('/api/simulation/reset', json={})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('current_time'), '07:58 AM')

        # Start
        res = self.client.post('/api/simulation/start', json={})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('is_running'))

        # Tick
        res = self.client.post('/api/simulation/tick', json={})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('current_time'), '07:59 AM')

        # Stop
        res = self.client.post('/api/simulation/stop', json={})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data.get('is_running'))

    def test_06_traffic_update(self):
        res = self.client.post('/api/traffic', json={'route_id': 'Route 1', 'traffic_level': 'HIGH'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))

        # Reset to LOW
        res = self.client.post('/api/traffic', json={'route_id': 'Route 1', 'traffic_level': 'LOW'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))

    def test_07_attendance_update(self):
        res = self.client.post('/api/attendance', json={'student_id': 'S101', 'status': 'Absent'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))

        res = self.client.post('/api/attendance', json={'student_id': 'S101', 'status': 'Present'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))

    def test_08_failure_injection(self):
        # GPS
        res = self.client.post('/api/failure/gps', json={'active': True})
        self.assertEqual(res.get_json().get('status'), 'ACTIVE')
        res = self.client.post('/api/failure/gps', json={'active': False})
        self.assertEqual(res.get_json().get('status'), 'INACTIVE')

        # Traffic
        res = self.client.post('/api/failure/traffic', json={'active': True})
        self.assertEqual(res.get_json().get('status'), 'ACTIVE')
        res = self.client.post('/api/failure/traffic', json={'active': False})
        self.assertEqual(res.get_json().get('status'), 'INACTIVE')

        # Sensor
        res = self.client.post('/api/failure/sensor', json={'active': True})
        self.assertEqual(res.get_json().get('status'), 'ACTIVE')
        res = self.client.post('/api/failure/sensor', json={'active': False})
        self.assertEqual(res.get_json().get('status'), 'INACTIVE')

    def test_09_store_and_forward(self):
        # Network failure
        res = self.client.post('/api/failure/network', json={'active': True})
        self.assertEqual(res.get_json().get('status'), 'ACTIVE')

        # Run ticks while offline
        self.client.post('/api/simulation/start', json={})
        self.client.post('/api/simulation/tick', json={})
        self.client.post('/api/simulation/tick', json={})
        self.client.post('/api/simulation/stop', json={})

        state = self.client.get('/api/simulation/state').get_json()
        queue_len = len(state.get('store_and_forward_queue', []))
        self.assertGreaterEqual(queue_len, 0)

        # Restore network and verify sync
        res = self.client.post('/api/failure/network', json={'active': False})
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.get_json().get('synchronized_count', 0), 0)

    def test_10_manual_eta(self):
        res = self.client.post('/api/manual-eta', json={
            'bus_id': '101',
            'location_name': 'Near Oak St',
            'next_stop_id': 'Stop_A',
            'manual_eta': '08:15 AM'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))

    def test_11_audit_history(self):
        res = self.client.get('/api/history/all')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        res = self.client.get('/api/history/101')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.get_json(), list)

    def test_12_notifications(self):
        res = self.client.get('/api/notifications')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)

    def test_13_experiment_results(self):
        res = self.client.get('/api/experiment/results')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data.get('metrics', [])), 5)
        self.assertIn('reduction_percentage', data)
        metrics = {m['metric_name']: m for m in data.get('metrics', [])}
        self.assertIn('MAE', metrics)
        self.assertLess(metrics['MAE']['proposed_value'], metrics['MAE']['baseline_value'])

    def test_14_reports_data(self):
        res = self.client.get('/api/reports/data')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('mae_global', data)
        self.assertIn('error_analysis', data)
        self.assertIn('delay_reasons', data)
        self.assertEqual(len(data['error_analysis'].get('categories', [])), 6)

    def test_15_feedback(self):
        res = self.client.post('/api/feedback', json={
            'q1': 5, 'q2': 5, 'q3': 5, 'q4': 5, 'q5': 5,
            'comments': 'Excellent system!'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get('success'))

        res = self.client.get('/api/feedback/summary')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreaterEqual(data.get('count', 0), 1)
        self.assertIn('averages', data)

if __name__ == '__main__':
    unittest.main()
