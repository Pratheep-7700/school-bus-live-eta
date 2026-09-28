"""
ETA Explanation Service
Provides natural language explanations and structured factor decomposition
for real-time school bus arrival estimates.
"""

from typing import Dict, List, Any, Optional
import math

class ETAExplanationService:
    """
    Dedicated rule engine for generating human-readable, data-backed
    explanations of live ETA calculations and delays.
    """

    # Status constants
    STATUS_ON_TIME = "ON_TIME"
    STATUS_DELAYED = "DELAYED"
    STATUS_EARLY = "EARLY"
    STATUS_UNKNOWN = "UNKNOWN"

    # Reason constants
    REASON_ON_SCHEDULE = "ON_SCHEDULE"
    REASON_AHEAD_OF_SCHEDULE = "AHEAD_OF_SCHEDULE"
    REASON_HIGH_BOARDING_TIME = "HIGH_BOARDING_TIME"
    REASON_TRAFFIC_DELAY = "TRAFFIC_DELAY"
    REASON_ROUTE_TRAVEL_DELAY = "ROUTE_TRAVEL_DELAY"
    REASON_SLOW_SPEED = "SLOW_SPEED"
    REASON_GPS_SIGNAL_LOSS = "GPS_SIGNAL_LOSS"
    REASON_SENSOR_DISCREPANCY = "SENSOR_DISCREPANCY"
    REASON_MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    REASON_UNKNOWN_CAUSE = "UNKNOWN_CAUSE"

    @staticmethod
    def parse_time_to_minutes(time_str: str) -> Optional[int]:
        """Converts time string ('HH:MM', 'HH:MM AM/PM') to minutes from midnight."""
        if not time_str or not isinstance(time_str, str):
            return None
        time_str = time_str.strip()
        parts = time_str.split()
        time_part = parts[0]
        ampm = parts[1].upper() if len(parts) > 1 else None

        if ':' not in time_part:
            return None

        h_m = time_part.split(':')
        try:
            h = int(h_m[0])
            m = int(h_m[1])
            if ampm == 'PM' and h < 12:
                h += 12
            elif ampm == 'AM' and h == 12:
                h = 0
            return (h * 60 + m) % 1440
        except ValueError:
            return None

    @classmethod
    def generate_explanation(
        cls,
        scheduled_arrival_time: Optional[str] = None,
        predicted_arrival_time: Optional[str] = None,
        current_delay: Optional[float] = None,
        previous_stop_boarding_time: Optional[float] = None,
        average_boarding_time: float = 45.0,
        traffic_delay: float = 0.0,
        route_delay: float = 0.0,
        distance_remaining: Optional[float] = None,
        current_bus_speed: Optional[float] = None,
        expected_travel_time: Optional[float] = None,
        actual_or_est_travel_time: Optional[float] = None,
        is_gps_fail: bool = False,
        is_sensor_abnormal: bool = False,
        is_manual: bool = False,
        manual_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates and returns structured ETA explanation data.
        Ensures reasons are strictly data-backed and includes mandatory fallback.
        """
        # Calculate delay in minutes
        delay_minutes = current_delay
        if delay_minutes is None and scheduled_arrival_time and predicted_arrival_time:
            sched_mins = cls.parse_time_to_minutes(scheduled_arrival_time)
            pred_mins = cls.parse_time_to_minutes(predicted_arrival_time)
            if sched_mins is not None and pred_mins is not None:
                diff = pred_mins - sched_mins
                # Handle overnight wrap-around if necessary
                if diff < -720:
                    diff += 1440
                elif diff > 720:
                    diff -= 1440
                delay_minutes = float(diff)

        # Fallback if delay cannot be computed
        if delay_minutes is None:
            return {
                "eta": predicted_arrival_time or "N/A",
                "delay_minutes": 0.0,
                "status": cls.STATUS_UNKNOWN,
                "primary_reason": cls.REASON_UNKNOWN_CAUSE,
                "explanation": "Delay detected, but the cause could not be determined from available telemetry.",
                "factors": []
            }

        delay_minutes = round(float(delay_minutes), 1)
        d_int = int(round(delay_minutes))

        # Check ON TIME status (delay <= 1 minute and >= -1 minute)
        if -1.0 <= delay_minutes <= 1.0:
            return {
                "eta": predicted_arrival_time or "N/A",
                "delay_minutes": delay_minutes,
                "status": cls.STATUS_ON_TIME,
                "primary_reason": cls.REASON_ON_SCHEDULE,
                "explanation": "Bus is currently on schedule. No significant delay detected.",
                "factors": []
            }

        # Check EARLY status (running ahead of schedule by > 1 minute)
        if delay_minutes < -1.0:
            abs_early = abs(d_int)
            return {
                "eta": predicted_arrival_time or "N/A",
                "delay_minutes": delay_minutes,
                "status": cls.STATUS_EARLY,
                "primary_reason": cls.REASON_AHEAD_OF_SCHEDULE,
                "explanation": f"Bus is currently running {abs_early} minutes ahead of schedule.",
                "factors": []
            }

        # Bus is DELAYED (delay > 1.0 minute)
        # Evaluate all data-backed factor candidates
        candidates = []

        # 1. Previous stop boarding delay
        if previous_stop_boarding_time is not None and previous_stop_boarding_time > average_boarding_time:
            boarding_diff_secs = previous_stop_boarding_time - average_boarding_time
            impact = round(boarding_diff_secs / 60.0, 1)
            if impact >= 0.5:
                candidates.append({
                    "factor": "boarding_time",
                    "reason_code": cls.REASON_HIGH_BOARDING_TIME,
                    "label": "higher-than-average boarding time at the previous stop",
                    "impact_minutes": min(impact, delay_minutes)
                })

        # 2. Traffic delay
        if traffic_delay > 0:
            traffic_impact = round(float(traffic_delay), 1)
            if traffic_impact >= 0.5:
                candidates.append({
                    "factor": "traffic",
                    "reason_code": cls.REASON_TRAFFIC_DELAY,
                    "label": "slower traffic on the current route",
                    "impact_minutes": min(traffic_impact, delay_minutes)
                })

        # 3. Travel time / Route delay
        if expected_travel_time is not None and actual_or_est_travel_time is not None:
            travel_diff = actual_or_est_travel_time - expected_travel_time
            if travel_diff >= 0.5:
                candidates.append({
                    "factor": "travel_time",
                    "reason_code": cls.REASON_ROUTE_TRAVEL_DELAY,
                    "label": "slower-than-expected travel time",
                    "impact_minutes": min(round(travel_diff, 1), delay_minutes)
                })
        elif route_delay > 0:
            route_impact = round(float(route_delay), 1)
            if route_impact >= 0.5:
                candidates.append({
                    "factor": "travel_time",
                    "reason_code": cls.REASON_ROUTE_TRAVEL_DELAY,
                    "label": "slower-than-expected travel time",
                    "impact_minutes": min(route_impact, delay_minutes)
                })

        # 4. GPS Failure Fallback
        if is_gps_fail:
            candidates.append({
                "factor": "gps_telemetry",
                "reason_code": cls.REASON_GPS_SIGNAL_LOSS,
                "label": "GPS telemetry signal interruption",
                "impact_minutes": min(3.0, delay_minutes)
            })

        # 5. Sensor Abnormality Fallback
        if is_sensor_abnormal:
            candidates.append({
                "factor": "sensor_discrepancy",
                "reason_code": cls.REASON_SENSOR_DISCREPANCY,
                "label": "speed sensor discrepancy",
                "impact_minutes": min(2.0, delay_minutes)
            })

        # 6. Manual Dispatcher Override
        if is_manual:
            note = f" ({manual_note})" if manual_note else ""
            candidates.append({
                "factor": "manual_override",
                "reason_code": cls.REASON_MANUAL_OVERRIDE,
                "label": f"manual dispatcher update{note}",
                "impact_minutes": delay_minutes
            })

        # Sort candidates descending by impact
        candidates.sort(key=lambda x: x["impact_minutes"], reverse=True)

        # Mandatory Fallback when reason cannot be determined from telemetry
        if not candidates or all(c["impact_minutes"] < 0.5 for c in candidates):
            return {
                "eta": predicted_arrival_time or "N/A",
                "delay_minutes": delay_minutes,
                "status": cls.STATUS_DELAYED,
                "primary_reason": cls.REASON_UNKNOWN_CAUSE,
                "explanation": f"Delay +{d_int} minutes. The system could not determine a specific cause from the available telemetry.",
                "factors": []
            }

        # Dominant reason identified
        primary = candidates[0]
        primary_reason = primary["reason_code"]
        primary_label = primary["label"]

        # Check for secondary factor mention
        if len(candidates) > 1 and candidates[1]["impact_minutes"] >= 1.5:
            secondary = candidates[1]
            explanation = f"Delay +{d_int} minutes, mainly due to {primary_label}, with additional delay from {secondary['label']}."
        else:
            explanation = f"Delay +{d_int} minutes due to {primary_label}."

        factors_response = [
            {
                "factor": c["factor"],
                "impact_minutes": c["impact_minutes"]
            }
            for c in candidates
        ]

        return {
            "eta": predicted_arrival_time or "N/A",
            "delay_minutes": delay_minutes,
            "status": cls.STATUS_DELAYED,
            "primary_reason": primary_reason,
            "explanation": explanation,
            "factors": factors_response
        }

# Module-level convenience function
def explain_eta(
    scheduled_arrival_time: Optional[str] = None,
    predicted_arrival_time: Optional[str] = None,
    current_delay: Optional[float] = None,
    previous_stop_boarding_time: Optional[float] = None,
    average_boarding_time: float = 45.0,
    traffic_delay: float = 0.0,
    route_delay: float = 0.0,
    distance_remaining: Optional[float] = None,
    current_bus_speed: Optional[float] = None,
    expected_travel_time: Optional[float] = None,
    actual_or_est_travel_time: Optional[float] = None,
    is_gps_fail: bool = False,
    is_sensor_abnormal: bool = False,
    is_manual: bool = False,
    manual_note: Optional[str] = None
) -> Dict[str, Any]:
    return ETAExplanationService.generate_explanation(
        scheduled_arrival_time=scheduled_arrival_time,
        predicted_arrival_time=predicted_arrival_time,
        current_delay=current_delay,
        previous_stop_boarding_time=previous_stop_boarding_time,
        average_boarding_time=average_boarding_time,
        traffic_delay=traffic_delay,
        route_delay=route_delay,
        distance_remaining=distance_remaining,
        current_bus_speed=current_bus_speed,
        expected_travel_time=expected_travel_time,
        actual_or_est_travel_time=actual_or_est_travel_time,
        is_gps_fail=is_gps_fail,
        is_sensor_abnormal=is_sensor_abnormal,
        is_manual=is_manual,
        manual_note=manual_note
    )

def build_bus_explanation(bus_id: str, next_stop_id: Optional[str], predicted_eta: str, conn) -> Dict[str, Any]:
    """
    Convenience helper to extract relevant telemetry and stop factors from SQLite
    and generate a fully structured natural language ETA explanation.
    """
    cursor = conn.cursor()
    
    # 1. Fetch Stop info
    planned_arrival = None
    stop_sequence = 1
    route_id = None
    if next_stop_id:
        cursor.execute("SELECT planned_arrival_time, sequence, route_id FROM stops WHERE stop_id = ?;", (next_stop_id,))
        stop_row = cursor.fetchone()
        if stop_row:
            planned_arrival = stop_row['planned_arrival_time']
            stop_sequence = stop_row['sequence']
            route_id = stop_row['route_id']

    # 2. Previous stop boarding time
    prev_boarding_time = 45.0
    if route_id and stop_sequence > 1:
        cursor.execute("SELECT stop_id FROM stops WHERE route_id = ? AND sequence = ?;", (route_id, stop_sequence - 1))
        prev_stop_row = cursor.fetchone()
        if prev_stop_row:
            cursor.execute("""
                SELECT COUNT(*) FROM students s
                JOIN attendance a ON s.student_id = a.student_id
                WHERE s.stop_id = ? AND a.status = 'Present';
            """, (prev_stop_row['stop_id'],))
            present_count = cursor.fetchone()[0]
            # Dwell formula: 30 base + 20 per present student
            prev_boarding_time = 30.0 + (present_count * 20.0)

    # 3. Traffic delay
    cursor.execute("SELECT status FROM failures WHERE case_name = 'traffic';")
    tf = cursor.fetchone()
    is_traffic_fail = (tf and tf['status'] == 'ACTIVE')
    traffic_delay = 0.0
    if is_traffic_fail:
        traffic_delay = 3.0 # Fallback MEDIUM
    elif route_id:
        cursor.execute("SELECT traffic_level FROM eta_history WHERE route_id = ? ORDER BY id DESC LIMIT 1;", (route_id,))
        last_hist = cursor.fetchone()
        if last_hist:
            lvl = last_hist['traffic_level'].upper()
            if lvl == 'HIGH':
                traffic_delay = 7.0
            elif lvl == 'MEDIUM':
                traffic_delay = 3.0

    # 4. Failures
    cursor.execute("SELECT case_name, status FROM failures WHERE case_name IN ('gps', 'sensor');")
    fail_dict = {row['case_name']: row['status'] for row in cursor.fetchall()}
    is_gps_fail = (fail_dict.get('gps') == 'ACTIVE')
    is_sensor_abnormal = (fail_dict.get('sensor') == 'ACTIVE')

    # 5. Bus speed
    cursor.execute("SELECT speed FROM buses WHERE bus_id = ?;", (bus_id,))
    bus_row = cursor.fetchone()
    bus_speed = bus_row['speed'] if bus_row else 30.0

    route_delay = 0.0
    if bus_speed < 20.0 and bus_speed > 0:
        route_delay = 2.0

    return explain_eta(
        scheduled_arrival_time=planned_arrival,
        predicted_arrival_time=predicted_eta,
        previous_stop_boarding_time=prev_boarding_time,
        average_boarding_time=45.0,
        traffic_delay=traffic_delay,
        route_delay=route_delay,
        current_bus_speed=bus_speed,
        is_gps_fail=is_gps_fail,
        is_sensor_abnormal=is_sensor_abnormal
    )

