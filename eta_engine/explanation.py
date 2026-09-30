from eta_engine.eta_calculator import str_to_minutes, get_traffic_delay_minutes, calculate_dwell_time

def explain_eta_difference(planned_eta_str, proposed_eta_str, traffic_level, stops_present_counts, is_gps_fail, is_sensor_abnormal, is_manual=False):
    """
    Decomposes the total deviation between planned timetable and dynamic proposed ETA into explainable factors.

    Purpose:
        Provides understandable, transparent reasons for delays (traffic, boarding time,
        dwell baseline, hardware fallbacks) rather than presenting unexplained ETA numbers.
        Used across notifications, dashboard popups, and audit history.

    Parameters:
        planned_eta_str (str): Scheduled arrival time ('HH:MM AM/PM').
        proposed_eta_str (str): Dynamic arrival time from ETA engine ('HH:MM AM/PM').
        traffic_level (str): Route congestion classification ('LOW', 'MEDIUM', 'HIGH').
        stops_present_counts (list[int]): Confirmed student counts for remaining stops.
        is_gps_fail (bool): Whether GPS signal outage fallback is active.
        is_sensor_abnormal (bool): Whether speed sensor discrepancy fallback is active.
        is_manual (bool, optional): Whether this update is a dispatcher/driver manual override.

    Returns:
        dict:
            - 'factors' (dict[str, float]): Dictionary of non-zero active delay components in minutes.
            - 'summary' (str): Human-readable formatted string summarizing the primary delay factors.

    Fallback Behavior:
        If total delay is zero or within nominal bounds, returns summary 'On time (no delay factors)'.
        If is_manual is True, isolates manual override impact directly without conflicting sensor attribution.
    """
    if is_manual:
        manual_delta = round(float(str_to_minutes(proposed_eta_str) - str_to_minutes(planned_eta_str)), 1)
        return {
            'factors': {'Manual Update': manual_delta},
            'summary': f"Manual update recorded by driver/dispatcher ({manual_delta:+.1f} min)."
        }

    planned_mins = str_to_minutes(planned_eta_str)
    proposed_mins = str_to_minutes(proposed_eta_str)
    total_diff_mins = proposed_mins - planned_mins

    # 1. Traffic factor decomposition
    traffic_mins = get_traffic_delay_minutes(traffic_level)

    # 2. Variable attendance dwell time decomposition
    # Base dwell is 30s (0.5m) per scheduled stop. Boarding time is 20s per student.
    total_dwell_secs = 0
    total_boarding_secs = 0
    
    for count in stops_present_counts:
        if count > 0:
            total_dwell_secs += 30  # Base door cycle and positioning duration
            total_boarding_secs += count * 20  # Passenger embarkation duration

    base_dwell_mins = total_dwell_secs / 60.0
    student_boarding_mins = total_boarding_secs / 60.0

    # 3. Route travel and dead-reckoning residual delay
    # Attributed to road network delays, intersection waits, and lower travel speeds
    remaining_diff = total_diff_mins - (traffic_mins + base_dwell_mins + student_boarding_mins)
    route_delay_mins = max(0.0, round(remaining_diff, 1))

    factors = {
        'Traffic': round(float(traffic_mins), 1),
        'Student boarding': round(float(student_boarding_mins), 1),
        'Dwell time': round(float(base_dwell_mins), 1),
        'Route delay': round(float(route_delay_mins), 1)
    }

    # Attribute hardware fallback impacts when active
    if is_gps_fail:
        # Simulated nominal 3-minute search/dead-reckoning buffering during GPS loss
        factors['GPS delay'] = 3.0
        factors['Route delay'] = round(max(0.0, route_delay_mins - 3.0), 1)
        
    if is_sensor_abnormal:
        # Calibrated 2-minute latency penalty during sensor mismatch substitution
        factors['Sensor discrepancy'] = 2.0
        factors['Route delay'] = round(max(0.0, route_delay_mins - 2.0), 1)

    # Filter out negligible factors for clean parent-facing presentation
    active_factors = {k: v for k, v in factors.items() if abs(v) > 0.01}

    # Assemble human-readable summary string
    reasons = []
    for k, v in active_factors.items():
        reasons.append(f"{k}: +{v} min" if v >= 0 else f"{k}: {v} min")
    
    summary = ", ".join(reasons) if reasons else "On time (no delay factors)"
    
    return {
        'factors': active_factors,
        'summary': summary
    }

