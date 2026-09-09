import math
from database.database import get_db_connection

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates the distance between two GPS coordinates in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def str_to_minutes(time_str):
    """Converts a time string in format 'HH:MM AM/PM' to minutes from midnight."""
    try:
        parts = time_str.strip().split()
        if len(parts) != 2:
            return 480  # Default to 08:00 AM on failure
        h_m = parts[0].split(':')
        h = int(h_m[0])
        m = int(h_m[1])
        ampm = parts[1].upper()
        if ampm == 'PM' and h < 12:
            h += 12
        elif ampm == 'AM' and h == 12:
            h = 0
        return h * 60 + m
    except Exception:
        return 480

def minutes_to_str(total_minutes):
    """Converts total minutes from midnight back into a 'HH:MM AM/PM' string."""
    total_minutes = int(round(total_minutes)) % 1440
    h = total_minutes // 60
    m = total_minutes % 60
    ampm = 'AM' if h < 12 else 'PM'
    h_display = h if h > 0 and h <= 12 else (h - 12 if h > 12 else 12)
    return f"{h_display:02d}:{m:02d} {ampm}"

def calculate_dwell_time(student_count):
    """Calculate dwell time in seconds based on student attendance:
       dwell_time = 30 + (present_students * 20) seconds.
    """
    return 30 + (student_count * 20)

def get_traffic_delay_minutes(traffic_level):
    """Retrieve traffic delay in minutes:
       LOW = 0, MEDIUM = 3, HIGH = 7
    """
    level = traffic_level.upper()
    if level == 'LOW':
        return 0
    elif level == 'MEDIUM':
        return 3
    elif level == 'HIGH':
        return 7
    return 0

def get_proposed_eta(bus_id, current_time_str, next_stop_id=None):
    """
    Calculates the dynamic proposed ETAs for a bus to all its upcoming stops on its route.
    Returns a dictionary mapping stop_id -> estimated arrival time string.
    Also returns detailed metrics (travel time, dwell time, traffic delay) for the ETA explanation.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch Bus and Route details
    cursor.execute("SELECT * FROM buses WHERE bus_id = ?;", (bus_id,))
    bus = cursor.fetchone()
    if not bus or bus['status'] == 'INACTIVE':
        conn.close()
        return {}, {}

    route_id = bus['route_id']
    bus_lat = bus['current_latitude']
    bus_lon = bus['current_longitude']
    bus_speed = bus['speed']
    if bus_speed <= 0:
        bus_speed = 30.0  # Fallback to default speed of 30 km/h

    # Check GPS failure
    cursor.execute("SELECT status FROM failures WHERE case_name = 'gps';")
    gps_fail = cursor.fetchone()
    is_gps_unavailable = (gps_fail and gps_fail['status'] == 'ACTIVE')

    # Check Sensor failure (speed is 0 when moving status is set)
    cursor.execute("SELECT status FROM failures WHERE case_name = 'sensor';")
    sensor_fail = cursor.fetchone()
    is_sensor_abnormal = (sensor_fail and sensor_fail['status'] == 'ACTIVE')

    if is_sensor_abnormal and bus['status'] == 'ON_ROUTE' and bus['speed'] <= 0:
        # Use previous valid speed (fallback to 30.0)
        bus_speed = 30.0

    # 2. Fetch traffic level (check traffic failure)
    cursor.execute("SELECT status FROM failures WHERE case_name = 'traffic';")
    traffic_fail = cursor.fetchone()
    is_traffic_unavailable = (traffic_fail and traffic_fail['status'] == 'ACTIVE')

    # Determine traffic level
    traffic_level = 'LOW'
    if is_traffic_unavailable:
        traffic_level = 'MEDIUM'  # Default historical traffic fallback
    else:
        # Get traffic level from most recent history or session parameter
        # In this simple model we'll assume traffic is fetched from a global session or route status.
        # We can query the database's recent history to see what was set last, or default to MEDIUM.
        cursor.execute("SELECT traffic_level FROM eta_history WHERE route_id = ? ORDER BY id DESC LIMIT 1;", (route_id,))
        last_hist = cursor.fetchone()
        if last_hist:
            traffic_level = last_hist['traffic_level']
        else:
            traffic_level = 'LOW'

    traffic_delay = get_traffic_delay_minutes(traffic_level)

    # 3. Fetch all stops for the route ordered by sequence
    cursor.execute("SELECT * FROM stops WHERE route_id = ? ORDER BY sequence ASC;", (route_id,))
    stops = [dict(s) for s in cursor.fetchall()]
    if not stops:
        conn.close()
        return {}, {}

    # 4. Filter remaining stops.
    # If next_stop_id is provided, remaining stops are those with sequence >= next_stop's sequence.
    # Otherwise, find the stop with sequence nearest to bus position or first stop.
    if next_stop_id:
        cursor.execute("SELECT sequence FROM stops WHERE stop_id = ?;", (next_stop_id,))
        next_seq_row = cursor.fetchone()
        next_seq = next_seq_row['sequence'] if next_seq_row else 1
    else:
        # Find next stop index based on sequence
        next_seq = 1
        # For simulation, if we don't know, we default to sequence 1

    remaining_stops = [s for s in stops if s['sequence'] >= next_seq]
    if not remaining_stops:
        conn.close()
        return {}, {}

    current_minutes = str_to_minutes(current_time_str)
    etas = {}
    explanations = {}

    cumulative_minutes = current_minutes
    prev_lat = bus_lat
    prev_lon = bus_lon

    for idx, stop in enumerate(remaining_stops):
        stop_id = stop['stop_id']
        stop_lat = stop['latitude']
        stop_lon = stop['longitude']

        # Calculate distance
        if idx == 0 and is_gps_unavailable:
            # GPS Failure: Use last known GPS position.
            # In our db, current_latitude/longitude will be frozen at last known.
            # So distance is calculated from that location.
            dist = haversine_distance(prev_lat, prev_lon, stop_lat, stop_lon)
        else:
            dist = haversine_distance(prev_lat, prev_lon, stop_lat, stop_lon)

        # Travel time in minutes
        travel_time_mins = (dist / bus_speed) * 60.0

        # Dwell time at the stop (how many students are present?)
        cursor.execute("""
            SELECT COUNT(*) FROM students s
            JOIN attendance a ON s.student_id = a.student_id
            WHERE s.stop_id = ? AND a.status = 'Present';
        """, (stop_id,))
        present_count = cursor.fetchone()[0]
        dwell_secs = calculate_dwell_time(present_count) if 'School' not in stop_name_clean(stop['stop_name']) else 0
        dwell_mins = dwell_secs / 60.0

        # Traffic delay: Apply to the current leg
        # (For simplicity, traffic delay is added to the first remaining leg or shared)
        leg_traffic_delay = traffic_delay if idx == 0 else 0

        # Update cumulative minutes for arrival at this stop
        cumulative_minutes += travel_time_mins + leg_traffic_delay

        etas[stop_id] = minutes_to_str(cumulative_minutes)
        explanations[stop_id] = {
            'travel_time_mins': round(travel_time_mins, 1),
            'dwell_time_mins': round(dwell_mins, 1),
            'traffic_delay_mins': leg_traffic_delay,
            'present_count': present_count,
            'total_delay_added': round(travel_time_mins + leg_traffic_delay + dwell_mins, 1)
        }

        # The bus will dwell at this stop before moving to the next stop
        cumulative_minutes += dwell_mins

        # Set previous position to this stop's location for the next leg
        prev_lat = stop_lat
        prev_lon = stop_lon

    conn.close()
    return etas, explanations

def stop_name_clean(name):
    return name.lower()
