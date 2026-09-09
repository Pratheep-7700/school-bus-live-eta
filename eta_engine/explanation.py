from eta_engine.eta_calculator import str_to_minutes, get_traffic_delay_minutes, calculate_dwell_time

def explain_eta_difference(planned_eta_str, proposed_eta_str, traffic_level, stops_present_counts, is_gps_fail, is_sensor_abnormal, is_manual=False):
    """
    Explains the difference between the planned ETA and the proposed ETA.
    Returns a dictionary of factors (in minutes) and a user-friendly text summary.
    """
    if is_manual:
        return {
            'factors': {'Manual Update': round(float(str_to_minutes(proposed_eta_str) - str_to_minutes(planned_eta_str)), 1)},
            'summary': "Manual update recorded by driver/admin."
        }

    planned_mins = str_to_minutes(planned_eta_str)
    proposed_mins = str_to_minutes(proposed_eta_str)
    total_diff_mins = proposed_mins - planned_mins

    # 1. Traffic delay
    traffic_mins = get_traffic_delay_minutes(traffic_level)

    # 2. Dwell time factors
    # Base dwell time is 30s (0.5m) per stop. Boarding time is 20s per student.
    total_dwell_secs = 0
    total_boarding_secs = 0
    
    for count in stops_present_counts:
        if count > 0:
            total_dwell_secs += 30  # Base dwell
            total_boarding_secs += count * 20  # Student boarding time

    base_dwell_mins = total_dwell_secs / 60.0
    student_boarding_mins = total_boarding_secs / 60.0

    # 3. Route travel and GPS delays
    # The remainder of the difference is due to GPS positioning and average travel speeds.
    remaining_diff = total_diff_mins - (traffic_mins + base_dwell_mins + student_boarding_mins)
    
    # Let's attribute positive remaining difference to "Route Delay/GPS Delay", and negative to "Ahead of schedule"
    route_delay_mins = max(0.0, round(remaining_diff, 1))

    factors = {
        'Traffic': round(float(traffic_mins), 1),
        'Student boarding': round(float(student_boarding_mins), 1),
        'Dwell time': round(float(base_dwell_mins), 1),
        'Route delay': round(float(route_delay_mins), 1)
    }

    if is_gps_fail:
        factors['GPS delay'] = 3.0  # Simulated nominal GPS fallback delay
        factors['Route delay'] = round(max(0.0, route_delay_mins - 3.0), 1)
        
    if is_sensor_abnormal:
        factors['Sensor discrepancy'] = 2.0
        factors['Route delay'] = round(max(0.0, route_delay_mins - 2.0), 1)

    # Filter out 0 values for presentation
    active_factors = {k: v for k, v in factors.items() if abs(v) > 0.01}

    # Generate summary string
    reasons = []
    for k, v in active_factors.items():
        reasons.append(f"{k}: +{v} min" if v >= 0 else f"{k}: {v} min")
    
    summary = ", ".join(reasons) if reasons else "On time (no delay factors)"
    
    return {
        'factors': active_factors,
        'summary': summary
    }
