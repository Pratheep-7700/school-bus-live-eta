from database.database import get_db_connection

def set_failure_status(case_name, status_str):
    """Sets the status of a specific failure case (ACTIVE or INACTIVE) in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE failures SET status = ? WHERE case_name = ?;", (status_str.upper(), case_name.lower()))
    conn.commit()
    conn.close()

def get_all_failures():
    """Retrieves all failure cases and their statuses."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM failures;")
    rows = cursor.fetchall()
    conn.close()
    return {row['case_name']: row['status'] for row in rows}

def is_failure_active(case_name):
    """Returns True if the specified failure is ACTIVE, False otherwise."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM failures WHERE case_name = ?;", (case_name.lower(),))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['status'] == 'ACTIVE'
