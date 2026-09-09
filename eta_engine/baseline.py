from database.database import get_db_connection

def get_baseline_eta(route_id):
    """
    Returns the baseline ETAs for all stops on a route.
    Baseline system uses the static planned schedule only.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT stop_id, planned_arrival_time FROM stops WHERE route_id = ? ORDER BY sequence ASC;", (route_id,))
    rows = cursor.fetchall()
    
    conn.close()
    
    baseline_etas = {}
    for row in rows:
        baseline_etas[row['stop_id']] = row['planned_arrival_time']
        
    return baseline_etas
