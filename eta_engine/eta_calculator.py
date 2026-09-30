import math
from database.database import get_db_connection

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates great-circle distance between two GPS coordinates using the Haversine formula.

    Purpose:
        Computes the shortest surface distance on Earth between vehicle coordinates
        and target stop waypoints to calculate remaining leg travel time.

    Parameters:
        lat1 (float): Latitude of origin point in degrees.
        lon1 (float): Longitude of origin point in degrees.
        lat2 (float): Latitude of destination point in degrees.
        lon2 (float): Longitude of destination point in degrees.

    Returns:
        float: Distance between the two coordinates in kilometers.

    Fallback Behavior:
        If coordinates are identical or delta is zero, returns 0.0 without division by zero.
    """
    R = 6371.0  # Earth mean radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def str_to_minutes(time_str):
    """
    Converts a standard 12-hour formatted time string ('HH:MM AM/PM') to minutes from midnight.

    Purpose:
        Facilitates arithmetic operations on schedule times (comparisons, delta delays,
        and cumulative arrival increments) by converting clock representations to linear integers.

    Parameters:
        time_str (str): Formatted time string, e.g., '08:00 AM', '12:30 PM'.

    Returns:
        int: Total minutes elapsed from midnight [0, 1439].

    Fallback Behavior:
        Returns 480 (equivalent to 08:00 AM school start baseline) if parsing fails, input
        is null, or format is malformed, preventing unhandled exceptions in ETA pipeline.
    """
    try:
        parts = time_str.strip().split()
        if len(parts) != 2:
            return 480  # Default to 08:00 AM on format mismatch
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
        # Gracefully degrade to standard morning route baseline upon malformed string
        return 480

def minutes_to_str(total_minutes):
    """
    Converts total minutes from midnight into a normalized 12-hour 'HH:MM AM/PM' string.

    Purpose:
        Transforms internal integer minute computations into human-readable time strings
        suitable for student/parent displays and UI presentation.

    Parameters:
        total_minutes (float or int): Minutes elapsed from midnight.

    Returns:
        str: 12-hour formatted time string, e.g., '08:15 AM' or '01:05 PM'.

    Fallback Behavior:
        Applies modulo 1440 to wrap cleanly around midnight boundaries, ensuring continuous
        valid string outputs even during extreme simulated delays.
    """
    total_minutes = int(round(total_minutes)) % 1440
    h = total_minutes // 60
    m = total_minutes % 60
    ampm = 'AM' if h < 12 else 'PM'
    h_display = h if h > 0 and h <= 12 else (h - 12 if h > 12 else 12)
    return f"{h_display:02d}:{m:02d} {ampm}"

def calculate_dwell_time(student_count):
    """
    Calculates estimated bus dwell time in seconds at a designated stop based on confirmed attendance.

    Purpose:
        Implements the core variable-attendance dynamic dwell model:
        dwell_time = base_dwell (30s) + (present_students * 20s).
        Reflects door opening/closing baseline plus individual student boarding and seating time.

    Parameters:
        student_count (int): Number of confirmed present students assigned to the stop.

    Returns:
        int: Calculated dwell duration in seconds.

    Fallback Behavior:
        When student_count is 0 or negative, returns the 30-second fixed deceleration/acceleration
        safety halt baseline before continuing.
    """
    count = max(0, int(student_count)) if student_count is not None else 0
    return 30 + (count * 20)

def get_traffic_delay_minutes(traffic_level):
    """
    Maps discrete categorical traffic states into deterministic delay adjustments in minutes.

    Purpose:
        Translates live route congestion assessments into additive route delay penalties:
        - LOW: Normal uncongested urban traffic flow (+0 min)
        - MEDIUM: Moderate arterial congestion (+3 min)
        - HIGH: Severe rush hour or bottleneck conditions (+7 min)

    Parameters:
        traffic_level (str): Categorical traffic status string ('LOW', 'MEDIUM', 'HIGH').

    Returns:
        int: Additive delay in minutes applied to route travel legs.

    Fallback Behavior:
        Returns 0 minutes if input is unrecognized, None, or empty, avoiding artificial delays.
    """
    if not traffic_level:
        return 0
    level = str(traffic_level).upper()
    if level == 'LOW':
        return 0
    elif level == 'MEDIUM':
        return 3
    elif level == 'HIGH':
        return 7
    return 0

def get_proposed_eta(bus_id, current_time_str, next_stop_id=None):
    """
    Calculates dynamic proposed arrival times (ETAs) for a bus across all remaining route stops.

    Purpose:
        Core ETA engine combining vehicle GPS telemetry, live speed, stop-specific attendance
        dwell times, and traffic condition multipliers. Handles active failure scenarios
        (GPS outages, sensor discrepancies, traffic feed loss) with deterministic fallbacks.

    Parameters:
        bus_id (str): Unique identifier of the bus (e.g., '101').
        current_time_str (str): Current simulation or clock time ('HH:MM AM/PM').
        next_stop_id (str, optional): Target stop ID where the bus is heading. If None,
            evaluation begins from the first stop on the route.

    Returns:
        tuple[dict, dict]:
            - etas (dict): Mapping of stop_id -> formatted arrival time string ('HH:MM AM/PM').
            - explanations (dict): Mapping of stop_id -> factor breakdown dictionary containing
              travel_time_mins, dwell_time_mins, traffic_delay_mins, present_count, total_delay_added.

    Fallback Behavior:
        - If bus is inactive or not found: returns empty dictionaries ({}, {}).
        - If bus speed is <= 0 while moving: falls back to 30.0 km/h nominal urban bus speed.
        - If GPS failure is active: relies on last known coordinates stored in DB.
        - If traffic feed is down: falls back to historical MEDIUM congestion level (+3 min).
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
    # Fallback to default urban transit operating speed (30 km/h) if reported speed is 0 or uncalibrated
    if bus_speed <= 0:
        bus_speed = 30.0

    # Check GPS failure status
    cursor.execute("SELECT status FROM failures WHERE case_name = 'gps';")
    gps_fail = cursor.fetchone()
    is_gps_unavailable = (gps_fail and gps_fail['status'] == 'ACTIVE')

    # Check Speed Sensor failure status (e.g. odometer/tachometer discrepancy reporting 0 when moving)
    cursor.execute("SELECT status FROM failures WHERE case_name = 'sensor';")
    sensor_fail = cursor.fetchone()
    is_sensor_abnormal = (sensor_fail and sensor_fail['status'] == 'ACTIVE')

    if is_sensor_abnormal and bus['status'] == 'ON_ROUTE' and bus['speed'] <= 0:
        # Override corrupted zero-speed reading with last known valid transit speed
        bus_speed = 30.0

    # 2. Fetch traffic level (with fallback if feed is down)
    cursor.execute("SELECT status FROM failures WHERE case_name = 'traffic';")
    traffic_fail = cursor.fetchone()
    is_traffic_unavailable = (traffic_fail and traffic_fail['status'] == 'ACTIVE')

    # Determine traffic level with fallback logic
    traffic_level = 'LOW'
    if is_traffic_unavailable:
        # When traffic telemetry fails, default to historical MEDIUM traffic delay (3m)
        traffic_level = 'MEDIUM'
    else:
        # Retrieve most recently committed traffic status for this route
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

    # 4. Filter remaining stops from current progress point
    if next_stop_id:
        cursor.execute("SELECT sequence FROM stops WHERE stop_id = ?;", (next_stop_id,))
        next_seq_row = cursor.fetchone()
        next_seq = next_seq_row['sequence'] if next_seq_row else 1
    else:
        next_seq = 1

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

        # Calculate distance: if GPS failed, bus coordinates stay pinned at last confirmed location
        dist = haversine_distance(prev_lat, prev_lon, stop_lat, stop_lon)

        # Travel time in minutes based on transit speed
        travel_time_mins = (dist / bus_speed) * 60.0

        # Dynamic Dwell Time: Count confirmed present students at this stop
        cursor.execute("""
            SELECT COUNT(*) FROM students s
            JOIN attendance a ON s.student_id = a.student_id
            WHERE s.stop_id = ? AND a.status = 'Present';
        """, (stop_id,))
        present_count = cursor.fetchone()[0]

        # The terminal school campus stop has zero boarding dwell time (alighting only)
        dwell_secs = calculate_dwell_time(present_count) if 'School' not in stop_name_clean(stop['stop_name']) else 0
        dwell_mins = dwell_secs / 60.0

        # Traffic delay is applied to the active transit leg
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

        # The bus will dwell at this stop before embarking on the subsequent leg
        cumulative_minutes += dwell_mins

        # Advance origin location to current stop for subsequent legs
        prev_lat = stop_lat
        prev_lon = stop_lon

    conn.close()
    return etas, explanations

def stop_name_clean(name):
    """Utility function to normalize stop names for terminal campus identification."""
    return name.lower() if name else ""

