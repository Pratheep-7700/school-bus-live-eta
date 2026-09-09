from database.database import get_db_connection

def is_failure_active(case_name):
    """Checks if a failure scenario is active in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM failures WHERE case_name = ?;", (case_name.lower(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['status'] == 'ACTIVE'

def get_fallback_gps(bus_id):
    """
    If GPS is unavailable, retrieves the last known location from the buses table.
    Otherwise, returns None (meaning active GPS is working).
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
    If traffic data is unavailable, returns 'MEDIUM' as the fallback historical traffic.
    """
    if is_failure_active('traffic'):
        return 'MEDIUM'
    return None

def get_fallback_speed(bus_id):
    """
    If speed sensor is abnormal, returns previous valid speed (e.g. 30 km/h).
    """
    if is_failure_active('sensor'):
        return 30.0
    return None
