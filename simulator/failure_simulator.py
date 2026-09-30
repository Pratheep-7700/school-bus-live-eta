from database.database import get_db_connection

def set_failure_status(case_name, status_str):
    """
    Updates the operational failure state of a subsystem in the SQLite database.

    Purpose:
        Allows runtime failure injection for simulation and testing of fault tolerance:
        - 'gps': Simulates satellite signal dropout / hardware disconnection.
        - 'network': Simulates cellular dead-zone / transmission outage.
        - 'traffic': Simulates traffic advisory API server failure.
        - 'sensor': Simulates odometer/speedometer sensor malfunction.

    Parameters:
        case_name (str): Identifier of the failure mode ('gps', 'network', 'traffic', 'sensor').
        status_str (str): Target state ('ACTIVE' or 'INACTIVE').

    Returns:
        None

    Fallback Behavior:
        Normalizes inputs to lowercase case_name and uppercase status_str, preventing
        format mismatches.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE failures SET status = ? WHERE case_name = ?;", (status_str.upper(), case_name.lower()))
    conn.commit()
    conn.close()

def get_all_failures():
    """
    Retrieves the status of all four failure injection subsystems.

    Purpose:
        Supplies dashboard status badges and frontend failure toggles with the live
        health of every tracked telemetry subsystem.

    Returns:
        dict: Mapping of case_name -> status string ('ACTIVE' or 'INACTIVE').
        Example: {'gps': 'INACTIVE', 'network': 'INACTIVE', 'traffic': 'INACTIVE', 'sensor': 'INACTIVE'}.

    Fallback Behavior:
        Returns an empty dictionary if the database table cannot be queried.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM failures;")
    rows = cursor.fetchall()
    conn.close()
    return {row['case_name']: row['status'] for row in rows}

def is_failure_active(case_name):
    """
    Checks if a specific failure case is currently flagged as ACTIVE.

    Purpose:
        Lightweight predicate function used by the simulator and ETA engine during
        each clock tick to determine whether to apply fallback logic.

    Parameters:
        case_name (str): Case identifier ('gps', 'network', 'traffic', 'sensor').

    Returns:
        bool: True if failure is ACTIVE, False otherwise.

    Fallback Behavior:
        Safely returns False if case_name is null or not found in the database.
    """
    if not case_name:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM failures WHERE case_name = ?;", (case_name.lower(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['status'] == 'ACTIVE'

