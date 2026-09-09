import json
import os
import sqlite3
from database.database import get_db_connection
from eta_engine.eta_calculator import get_proposed_eta, str_to_minutes, minutes_to_str, haversine_distance, calculate_dwell_time, get_traffic_delay_minutes
from eta_engine.explanation import explain_eta_difference
from eta_engine.baseline import get_baseline_eta

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'simulation_state.json')

def load_sim_state():
    """Loads the current simulation state from the JSON state file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return reset_simulation()

def save_sim_state(state):
    """Saves the simulation state to the JSON state file."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def reset_simulation():
    """Resets the simulation state to the initial conditions (07:58 AM)."""
    # Reset buses in database to their starting stops
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Set buses back to their initial positions (Stop A, Stop D, Stop G)
    cursor.execute("UPDATE buses SET current_latitude = 37.7949, current_longitude = -122.4394, speed = 30.0, status = 'ON_ROUTE' WHERE bus_id = '101';")
    cursor.execute("UPDATE buses SET current_latitude = 37.7549, current_longitude = -122.4494, speed = 30.0, status = 'ON_ROUTE' WHERE bus_id = '102';")
    cursor.execute("UPDATE buses SET current_latitude = 37.7549, current_longitude = -122.3994, speed = 30.0, status = 'ON_ROUTE' WHERE bus_id = '103';")
    cursor.execute("UPDATE buses SET current_latitude = 37.7749, current_longitude = -122.4194, speed = 0.0, status = 'INACTIVE' WHERE bus_id = '104';")
    cursor.execute("UPDATE buses SET current_latitude = 37.7749, current_longitude = -122.4194, speed = 0.0, status = 'INACTIVE' WHERE bus_id = '105';")
    
    # Deactivate all failures
    cursor.execute("UPDATE failures SET status = 'INACTIVE';")
    
    # Reset attendance to default 'Present'
    cursor.execute("UPDATE attendance SET status = 'Present';")
    
    # Clear logs and history
    cursor.execute("DELETE FROM eta_history;")
    cursor.execute("DELETE FROM notifications;")
    conn.commit()
    conn.close()

    state = {
        'is_running': False,
        'current_time': '07:58 AM',
        'tick_count': 0,
        'bus_states': {
            '101': {
                'route_id': 'Route 1',
                'current_stop_index': 0, # Stop A
                'status': 'ON_ROUTE',
                'dwell_remaining_secs': 0,
                'next_stop_id': 'Stop_A',
                'last_eta': '08:00 AM'
            },
            '102': {
                'route_id': 'Route 2',
                'current_stop_index': 0, # Stop D
                'status': 'ON_ROUTE',
                'dwell_remaining_secs': 0,
                'next_stop_id': 'Stop_D',
                'last_eta': '08:00 AM'
            },
            '103': {
                'route_id': 'Route 3',
                'current_stop_index': 0, # Stop G
                'status': 'ON_ROUTE',
                'dwell_remaining_secs': 0,
                'next_stop_id': 'Stop_G',
                'last_eta': '08:00 AM'
            }
        },
        'store_and_forward_queue': [] # In-memory network backup queue
    }
    save_sim_state(state)
    return state

def get_db_failures():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT case_name, status FROM failures;")
    failures = {row['case_name']: row['status'] for row in cursor.fetchall()}
    conn.close()
    return failures

def run_simulation_tick():
    """
    Advances the simulation by 1 tick (1 minute in simulation time).
    Updates bus coordinates, handles stop arrivals, dwell count downs, and ETAs.
    """
    state = load_sim_state()
    if not state['is_running']:
        return state

    current_mins = str_to_minutes(state['current_time'])
    current_mins += 1  # Advance time by 1 minute
    state['current_time'] = minutes_to_str(current_mins)
    state['tick_count'] += 1

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get active failures
    failures = get_db_failures()
    is_gps_unavailable = (failures.get('gps') == 'ACTIVE')
    is_network_unavailable = (failures.get('network') == 'ACTIVE')
    is_traffic_unavailable = (failures.get('traffic') == 'ACTIVE')
    is_sensor_abnormal = (failures.get('sensor') == 'ACTIVE')

    # Default traffic level
    traffic_level = 'LOW'
    # Try to find last set traffic level from history or default to LOW
    cursor.execute("SELECT traffic_level FROM eta_history ORDER BY id DESC LIMIT 1;")
    last_hist = cursor.fetchone()
    if last_hist:
        traffic_level = last_hist['traffic_level']
    if is_traffic_unavailable:
        traffic_level = 'MEDIUM'

    for bus_id, bus_state in state['bus_states'].items():
        if bus_state['status'] == 'COMPLETED':
            continue

        # Fetch route stops
        cursor.execute("SELECT * FROM stops WHERE route_id = ? ORDER BY sequence ASC;", (bus_state['route_id'],))
        stops = [dict(s) for s in cursor.fetchall()]
        current_stop = stops[bus_state['current_stop_index']]
        next_stop = stops[bus_state['current_stop_index']]

        # Get current bus position in DB
        cursor.execute("SELECT current_latitude, current_longitude, speed FROM buses WHERE bus_id = ?;", (bus_id,))
        bus_db = cursor.fetchone()
        bus_lat = bus_db['current_latitude']
        bus_lon = bus_db['current_longitude']
        bus_speed = bus_db['speed']

        if is_sensor_abnormal:
            # Sensor shows 0 speed, but bus is ON_ROUTE. Fallback to previous valid speed (30.0)
            bus_speed = 30.0
        elif bus_speed <= 0:
            bus_speed = 30.0

        if bus_state['status'] == 'DWELLING':
            # Count down dwell time
            bus_state['dwell_remaining_secs'] -= 60
            if bus_state['dwell_remaining_secs'] <= 0:
                # Dwell complete, move to next stop
                bus_state['dwell_remaining_secs'] = 0
                bus_state['current_stop_index'] += 1
                
                if bus_state['current_stop_index'] >= len(stops):
                    bus_state['status'] = 'COMPLETED'
                    cursor.execute("UPDATE buses SET status = 'COMPLETED', speed = 0 WHERE bus_id = ?;", (bus_id,))
                else:
                    bus_state['status'] = 'ON_ROUTE'
                    next_stop = stops[bus_state['current_stop_index']]
                    bus_state['next_stop_id'] = next_stop['stop_id']
                    cursor.execute("UPDATE buses SET status = 'ON_ROUTE' WHERE bus_id = ?;", (bus_id,))
                
                # Write an info notification
                msg = f"Bus {bus_id} departed {current_stop['stop_name']}."
                log_notification(conn, state, bus_id, msg, 'INFO', is_network_unavailable)

        elif bus_state['status'] == 'ON_ROUTE':
            # Calculate distance to next stop
            target_stop = stops[bus_state['current_stop_index']]
            dist = haversine_distance(bus_lat, bus_lon, target_stop['latitude'], target_stop['longitude'])
            
            # Distance bus can travel in 1 minute
            # Speed is in km/h, so km/minute = speed / 60
            travel_dist = (bus_speed / 60.0)
            
            if is_gps_unavailable:
                # GPS failure: bus coordinates are frozen (not updated in db/UI)
                # But physically in the simulation, it still advances.
                pass

            if dist <= travel_dist:
                # Arrived at the stop!
                new_lat = target_stop['latitude']
                new_lon = target_stop['longitude']
                bus_state['status'] = 'DWELLING'
                
                # Dwell time calculation
                cursor.execute("""
                    SELECT COUNT(*) FROM students s
                    JOIN attendance a ON s.student_id = a.student_id
                    WHERE s.stop_id = ? AND a.status = 'Present';
                """, (target_stop['stop_id'],))
                present_students = cursor.fetchone()[0]
                
                # If target stop is school, dwell is 0
                if 'School' in target_stop['stop_name']:
                    bus_state['dwell_remaining_secs'] = 0
                    bus_state['status'] = 'COMPLETED'
                    cursor.execute("UPDATE buses SET current_latitude = ?, current_longitude = ?, speed = 0, status = 'COMPLETED' WHERE bus_id = ?;", (new_lat, new_lon, bus_id))
                    msg = f"Bus {bus_id} has arrived at the School."
                    log_notification(conn, state, bus_id, msg, 'INFO', is_network_unavailable)
                else:
                    dwell_secs = calculate_dwell_time(present_students)
                    bus_state['dwell_remaining_secs'] = dwell_secs
                    
                    # Update coordinates in DB (unless GPS fail makes it appear stuck)
                    if not is_gps_unavailable:
                        cursor.execute("UPDATE buses SET current_latitude = ?, current_longitude = ?, status = 'DWELLING', speed = 0 WHERE bus_id = ?;", (new_lat, new_lon, bus_id))
                    else:
                        cursor.execute("UPDATE buses SET status = 'DWELLING', speed = 0 WHERE bus_id = ?;", (bus_id,))
                        
                    msg = f"Bus {bus_id} arrived at {target_stop['stop_name']}. Dwelling for {dwell_secs}s."
                    log_notification(conn, state, bus_id, msg, 'INFO', is_network_unavailable)
            else:
                # Move closer to target
                fraction = travel_dist / dist
                new_lat = bus_lat + fraction * (target_stop['latitude'] - bus_lat)
                new_lon = bus_lon + fraction * (target_stop['longitude'] - bus_lon)
                
                # Update coordinates in DB (unless GPS is unavailable)
                if not is_gps_unavailable:
                    cursor.execute("UPDATE buses SET current_latitude = ?, current_longitude = ? WHERE bus_id = ?;", (new_lat, new_lon, bus_id))

        # Calculate new dynamic ETA for the remaining stops
        if bus_state['status'] != 'COMPLETED':
            next_stop_id = bus_state['next_stop_id']
            etas, explanations = get_proposed_eta(bus_id, state['current_time'], next_stop_id)
            
            if next_stop_id in etas:
                new_eta = etas[next_stop_id]
                prev_eta = bus_state['last_eta']
                
                # Meaningful ETA change detection
                prev_mins = str_to_minutes(prev_eta)
                new_mins = str_to_minutes(new_eta)
                eta_change = new_mins - prev_mins
                
                if abs(eta_change) >= 2.0:
                    bus_state['last_eta'] = new_eta
                    
                    # Compute explainers
                    planned_etas = get_baseline_eta(bus_state['route_id'])
                    planned_eta = planned_etas.get(next_stop_id, '08:00 AM')
                    
                    # Get student counts for remaining stops
                    rem_stops = [s for s in stops if s['sequence'] >= current_stop['sequence']]
                    stops_present_counts = []
                    for rs in rem_stops:
                        cursor.execute("""
                            SELECT COUNT(*) FROM students s
                            JOIN attendance a ON s.student_id = a.student_id
                            WHERE s.stop_id = ? AND a.status = 'Present';
                        """, (rs['stop_id'],))
                        stops_present_counts.append(cursor.fetchone()[0])
                    
                    explanation_data = explain_eta_difference(
                        planned_eta, new_eta, traffic_level, stops_present_counts,
                        is_gps_unavailable, is_sensor_abnormal
                    )
                    
                    reason_text = explanation_data['summary']
                    
                    # Determine notification alert level
                    alert_type = 'INFO'
                    if eta_change >= 5.0:
                        alert_type = 'CRITICAL' # Delay >= 5 minutes
                        msg = f"🔴 Bus {bus_id} is significantly delayed. ETA to {next_stop['stop_name']} updated to {new_eta} (+{int(eta_change)}m)."
                    elif eta_change >= 2.0:
                        alert_type = 'WARNING' # Delay >= 2 minutes
                        msg = f"🟡 Bus {bus_id} ETA updated to {new_eta} (+{int(eta_change)}m)."
                    else:
                        msg = f"🟢 Bus {bus_id} ETA updated to {new_eta} ({int(eta_change)}m)."
                    
                    log_notification(conn, state, bus_id, msg, alert_type, is_network_unavailable)
                    
                    # Check customer pickup commitment window for next stop
                    cursor.execute("""
                        SELECT committed_pickup_time FROM students WHERE stop_id = ? LIMIT 1;
                    """, (next_stop['stop_id'],))
                    comm_row = cursor.fetchone()
                    if comm_row:
                        committed_time = comm_row[0]
                        comm_diff = str_to_minutes(new_eta) - str_to_minutes(committed_time)
                        if comm_diff > 5:
                            comm_status = 'BREACHED' if comm_diff > 10 else 'AT_RISK'
                            comm_msg = f"⚠️ Customer Commitment Alert: Bus {bus_id} expected arrival at {next_stop['stop_name']} is {new_eta} (Committed: {committed_time} ±5m, Expected Delay: +{int(comm_diff)}m). Status: {comm_status}."
                            log_notification(conn, state, bus_id, comm_msg, 'CRITICAL' if comm_status == 'BREACHED' else 'WARNING', is_network_unavailable)
                    
                    # Log audit history
                    log_audit_history(
                        conn, state, bus_id, bus_state['route_id'], prev_eta, new_eta,
                        eta_change, reason_text, traffic_level, sum(stops_present_counts),
                        (bus_state['dwell_remaining_secs'] / 60.0),
                        'OFFLINE' if is_gps_unavailable else 'ONLINE',
                        'OFFLINE' if is_network_unavailable else 'ONLINE',
                        1, 'AUTO', is_network_unavailable
                    )

    conn.commit()
    conn.close()
    
    # Save the updated state
    save_sim_state(state)
    return state

def log_notification(conn, state, bus_id, message, msg_type, is_network_unavailable):
    """Logs a notification. If network is offline, stores in store_and_forward queue."""
    timestamp = state['current_time']
    if is_network_unavailable:
        # Queue event for later synchronization
        state['store_and_forward_queue'].append({
            'type': 'notification',
            'timestamp': timestamp,
            'bus_id': bus_id,
            'message': message,
            'msg_type': msg_type
        })
    else:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO notifications (timestamp, bus_id, message, type) VALUES (?, ?, ?, ?);",
            (timestamp, bus_id, message, msg_type)
        )

def log_audit_history(conn, state, bus_id, route_id, previous_eta, new_eta, delay_minutes,
                      reason, traffic_level, student_count, dwell_time, gps_status,
                      network_status, notification_sent, source, is_network_unavailable):
    """Logs audit history. If network is offline, stores in store_and_forward queue."""
    timestamp = state['current_time']
    if is_network_unavailable:
        state['store_and_forward_queue'].append({
            'type': 'audit',
            'timestamp': timestamp,
            'bus_id': bus_id,
            'route_id': route_id,
            'previous_eta': previous_eta,
            'new_eta': new_eta,
            'delay_minutes': delay_minutes,
            'reason': reason,
            'traffic_level': traffic_level,
            'student_count': student_count,
            'dwell_time': dwell_time,
            'gps_status': gps_status,
            'network_status': network_status,
            'notification_sent': notification_sent,
            'source': source
        })
    else:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO eta_history (
                timestamp, bus_id, route_id, previous_eta, new_eta, delay_minutes,
                reason, traffic_level, student_count, dwell_time, gps_status,
                network_status, notification_sent, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (timestamp, bus_id, route_id, previous_eta, new_eta, delay_minutes,
              reason, traffic_level, student_count, dwell_time, gps_status,
              network_status, notification_sent, source))

def synchronize_network_queue():
    """Flushes the store-and-forward queue to the SQLite database once network is restored."""
    state = load_sim_state()
    queue = state.get('store_and_forward_queue', [])
    if not queue:
        return 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    count = len(queue)
    for event in queue:
        if event['type'] == 'notification':
            cursor.execute(
                "INSERT INTO notifications (timestamp, bus_id, message, type) VALUES (?, ?, ?, ?);",
                (event['timestamp'], event['bus_id'], event['message'], event['msg_type'])
            )
        elif event['type'] == 'audit':
            cursor.execute("""
                INSERT INTO eta_history (
                    timestamp, bus_id, route_id, previous_eta, new_eta, delay_minutes,
                    reason, traffic_level, student_count, dwell_time, gps_status,
                    network_status, notification_sent, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (event['timestamp'], event['bus_id'], event['route_id'], event['previous_eta'],
                  event['new_eta'], event['delay_minutes'], event['reason'], event['traffic_level'],
                  event['student_count'], event['dwell_time'], event['gps_status'],
                  event['network_status'], event['notification_sent'], event['source']))
            
    conn.commit()
    conn.close()
    
    # Empty queue and save
    state['store_and_forward_queue'] = []
    save_sim_state(state)
    
    return count
