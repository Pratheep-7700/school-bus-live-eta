from database.database import get_db_connection

def get_baseline_eta(route_id):
    """
    Returns the static scheduled baseline arrival times for all stops along a given route.

    Purpose:
        Retrieves the fixed timetable planned arrival times without real-time GPS,
        attendance dwell, or traffic adjustments. Used as the experimental control
        benchmark to quantify accuracy gains (MAE/RMSE) and status enquiry reductions.

    Parameters:
        route_id (str): Unique route identifier (e.g., 'Route 1').

    Returns:
        dict: Mapping of stop_id -> static planned_arrival_time (e.g. {'Stop_A': '08:00 AM'}).

    Fallback Behavior:
        Returns an empty dictionary if the route does not exist or has no defined stops.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query static timetable ordered by route sequence
    cursor.execute(
        "SELECT stop_id, planned_arrival_time FROM stops WHERE route_id = ? ORDER BY sequence ASC;",
        (route_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    baseline_etas = {}
    for row in rows:
        baseline_etas[row['stop_id']] = row['planned_arrival_time']
        
    return baseline_etas

