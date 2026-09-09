import unittest
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import init_db, get_db_connection
from simulator.simulation import load_sim_state, save_sim_state, log_notification, log_audit_history, synchronize_network_queue

class TestAuditLogsAndSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        # Clear audit logs and notifications
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM eta_history;")
        cursor.execute("DELETE FROM notifications;")
        conn.commit()
        conn.close()

    def test_log_notification_online(self):
        conn = get_db_connection()
        state = {
            'current_time': '08:05 AM',
            'store_and_forward_queue': []
        }
        
        # Log when network is ONLINE (is_network_unavailable = False)
        log_notification(conn, state, '101', 'Test message online', 'INFO', False)
        conn.commit()
        
        # Read from DB
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications;")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['message'], 'Test message online')
        self.assertEqual(len(state['store_and_forward_queue']), 0)
        conn.close()

    def test_log_notification_offline_store_and_forward(self):
        conn = get_db_connection()
        state = {
            'current_time': '08:05 AM',
            'store_and_forward_queue': []
        }
        
        # Log when network is OFFLINE (is_network_unavailable = True)
        log_notification(conn, state, '101', 'Test message offline', 'INFO', True)
        conn.commit()
        
        # Check that it's NOT in SQLite
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications;")
        self.assertEqual(len(cursor.fetchall()), 0)
        
        # Check that it IS in the local queue
        self.assertEqual(len(state['store_and_forward_queue']), 1)
        self.assertEqual(state['store_and_forward_queue'][0]['message'], 'Test message offline')
        conn.close()

    def test_store_and_forward_synchronization(self):
        state = load_sim_state()
        state['store_and_forward_queue'] = [
            {
                'type': 'notification',
                'timestamp': '08:06 AM',
                'bus_id': '101',
                'message': 'Queued offline notification 1',
                'msg_type': 'WARNING'
            },
            {
                'type': 'audit',
                'timestamp': '08:06 AM',
                'bus_id': '101',
                'route_id': 'Route 1',
                'previous_eta': '08:10 AM',
                'new_eta': '08:12 AM',
                'delay_minutes': 2.0,
                'reason': 'Queued offline audit 1',
                'traffic_level': 'LOW',
                'student_count': 4,
                'dwell_time': 1.5,
                'gps_status': 'ONLINE',
                'network_status': 'OFFLINE',
                'notification_sent': 1,
                'source': 'AUTO'
            }
        ]
        save_sim_state(state)

        # Sync queue to SQLite
        sync_count = synchronize_network_queue()
        self.assertEqual(sync_count, 2)

        # Check DB entries
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM notifications;")
        notifications = cursor.fetchall()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]['message'], 'Queued offline notification 1')

        cursor.execute("SELECT * FROM eta_history;")
        audits = cursor.fetchall()
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]['reason'], 'Queued offline audit 1')
        self.assertEqual(audits[0]['new_eta'], '08:12 AM')
        
        conn.close()

        # Check that state queue is empty after sync
        state_after = load_sim_state()
        self.assertEqual(len(state_after['store_and_forward_queue']), 0)

if __name__ == '__main__':
    unittest.main()
