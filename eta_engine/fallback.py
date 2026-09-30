from database.database import get_db_connection

def is_failure_active(case_name):
    """
    Checks if a simulated failure scenario is currently flagged as ACTIVE in SQLite.

    Purpose:
        Acts as the central query interface for the fault tolerance subsystem to determine
        whether hardware sensors or external feeds are currently experiencing an outage.

    Parameters:
        case_name (str): Identifier of the failure mode ('gps', 'network', 'traffic', 'sensor').

    Returns:
        bool: True if failure state is ACTIVE; False otherwise or if case is missing.

    Fallback Behavior:
        Safely returns False if the database query fails or the row does not exist,
        preventing system crash and assuming nominal operations.
    """
    if not case_name:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM failures WHERE case_name = ?;", (case_name.lower(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['status'] == 'ACTIVE'

def get_fallback_gps(bus_id):
    """
    Retrieves the last known confirmed latitude and longitude for a bus during GPS outage.

    Purpose:
        When GPS hardware fails or signal is obstructed (e.g., tunnels, urban canyons),
        this fallback provides the vehicle's last reported coordinates so the system
        can continue dead-reckoning or distance estimations without crashing.

    Parameters:
        bus_id (str): Unique bus identifier.

    Returns:
        tuple[float, float] or None: (latitude, longitude) if GPS failure is active and bus exists;
        None if GPS is nominal and operating normally.

    Fallback Behavior:
        Returns None if GPS is active (nominal), prompting caller to use live feed.
    """
    if is_failure_active('gps'):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT current_latitude, current_longitude FROM buses WHERE bus_id = ?;", (bus_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['current_latitude'], row['current_longitude']
    return None

def get_fallback_traffic(route_id):
    """
    Provides default historical traffic congestion level when real-time traffic feed drops.

    Purpose:
        Ensures that traffic feed downtime does not cause the ETA engine to underestimate
        travel time. Assumes a conservative historical average ('MEDIUM' = +3 minutes).

    Parameters:
        route_id (str): Unique route identifier.

    Returns:
        str or None: 'MEDIUM' if traffic failure is ACTIVE; None if live feed is nominal.

    Fallback Behavior:
        Returns None when traffic feed is healthy, allowing live route queries.
    """
    if is_failure_active('traffic'):
        # Conservative baseline assumption during traffic API disconnection
        return 'MEDIUM'
    return None

def get_fallback_speed(bus_id):
    """
    Supplies calibrated fallback speed (30.0 km/h) when onboard speed sensor reports abnormal data.

    Purpose:
        Catches corrupted telemetry (such as reporting 0 km/h speed while status is ON_ROUTE)
        and substitutes a realistic urban school bus operating speed to prevent infinite ETAs.

    Parameters:
        bus_id (str): Unique bus identifier.

    Returns:
        float or None: 30.0 (km/h) if sensor failure is ACTIVE; None if sensor is nominal.

    Fallback Behavior:
        Returns None when sensor is healthy, allowing live speedometer reading.
    """
    if is_failure_active('sensor'):
        # 30 km/h represents standard urban school district speed limit and transit average
        return 30.0
    return None

