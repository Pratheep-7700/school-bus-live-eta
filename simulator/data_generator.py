import os
import csv
import random
import pandas as pd
import numpy as np
from database.database import get_db_connection

def generate_experiment_dataset():
    """
    Generates 500+ simulated trips comparing the baseline schedule-only ETA
    with the proposed dynamic ETA. Saves the dataset to data/eta_experiment.csv.
    """
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, 'eta_experiment.csv')

    print(f"Generating experiment dataset at {csv_path}...")

    # Set random seed for reproducibility
    np.random.seed(42)
    random.seed(42)

    trips = []
    
    # Let's assume three routes with planned durations
    routes_planned = {
        'Route 1': 30,  # 30 mins planned from start to school
        'Route 2': 30,
        'Route 3': 30
    }
    
    # Baseline ETA (planned schedule) is 08:30 AM (510 minutes)
    planned_minutes = 510 

    for i in range(1, 551):
        bus_id = f"10{random.choice([1, 2, 3])}"
        route_id = f"Route {bus_id[-1]}"
        
        # 1. Simulate environment variables
        traffic_level = random.choices(['LOW', 'MEDIUM', 'HIGH'], weights=[0.5, 0.3, 0.2])[0]
        if traffic_level == 'LOW':
            traffic_delay = 0
        elif traffic_level == 'MEDIUM':
            traffic_delay = 3
        else:
            traffic_delay = 7

        # Attendance: 0 to 11 students present
        student_count = random.randint(0, 11)
        # Dwell time in minutes: 30s base + 20s per student
        dwell_time_mins = (30 + student_count * 20) / 60.0
        
        # Failures
        gps_available = random.choices([True, False], weights=[0.95, 0.05])[0]
        network_available = random.choices([True, False], weights=[0.95, 0.05])[0]

        # 2. Compute Actual Arrival Time
        # The true arrival has the planned base time, traffic delay, dwell time,
        # plus some random route delays (e.g. stoplights, slow speed)
        route_noise = np.random.normal(2.0, 1.5)  # mean 2 mins delay, std dev 1.5
        route_noise = max(0.0, route_noise)
        
        actual_arrival_mins = planned_minutes + traffic_delay + dwell_time_mins + route_noise
        
        # 3. Calculate Predictions
        # Baseline predicted ETA is ALWAYS the planned schedule
        predicted_eta_baseline_mins = planned_minutes

        # Proposed predicted ETA incorporates live inputs
        # If GPS is unavailable, there's a fallback error (e.g. system estimates based on last location, adding error)
        gps_error = 0.0 if gps_available else np.random.normal(4.0, 2.0)
        gps_error = max(0.0, gps_error)
        
        # Proposed ETA uses traffic delay and dwell time directly
        predicted_eta_proposed_mins = planned_minutes + traffic_delay + dwell_time_mins + gps_error
        
        # Add minor random prediction error for proposed (e.g., speed fluctuations)
        prediction_noise = np.random.normal(0.0, 0.8)
        predicted_eta_proposed_mins += prediction_noise
        
        # Ensure it doesn't predict arrival before planned start
        predicted_eta_proposed_mins = max(planned_minutes, predicted_eta_proposed_mins)

        # 4. Customer Commitment
        # Let's say commitment is planned_minutes + 2 (08:32 AM)
        customer_commitment_mins = planned_minutes + 2

        # 5. Format into HH:MM AM/PM strings
        def mins_to_str(m):
            m = int(round(m))
            h = m // 60
            mins = m % 60
            ampm = 'AM' if h < 12 else 'PM'
            h_display = h if h > 0 and h <= 12 else (h - 12 if h > 12 else 12)
            return f"{h_display:02d}:{mins:02d} {ampm}"

        trips.append({
            'trip_id': f"TRIP_{i:04d}",
            'bus_id': bus_id,
            'route_id': route_id,
            'planned_eta': mins_to_str(planned_minutes),
            'predicted_eta_baseline': mins_to_str(predicted_eta_baseline_mins),
            'predicted_eta_proposed': mins_to_str(predicted_eta_proposed_mins),
            'actual_arrival': mins_to_str(actual_arrival_mins),
            'student_count': student_count,
            'dwell_time': round(dwell_time_mins, 2),
            'traffic_level': traffic_level,
            'traffic_delay': traffic_delay,
            'gps_available': 1 if gps_available else 0,
            'network_available': 1 if network_available else 0,
            'customer_commitment': mins_to_str(customer_commitment_mins),
            # Save raw numbers for metric computations
            '_actual_arrival_mins': actual_arrival_mins,
            '_predicted_eta_baseline_mins': predicted_eta_baseline_mins,
            '_predicted_eta_proposed_mins': predicted_eta_proposed_mins
        })

    # Save to CSV
    headers = [
        'trip_id', 'bus_id', 'route_id', 'planned_eta', 
        'predicted_eta_baseline', 'predicted_eta_proposed', 'actual_arrival', 
        'student_count', 'dwell_time', 'traffic_level', 'traffic_delay', 
        'gps_available', 'network_available', 'customer_commitment'
    ]
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for trip in trips:
            # Exclude raw numeric values prefixed with '_'
            row = {k: v for k, v in trip.items() if not k.startswith('_')}
            writer.writerow(row)

    print("Experiment dataset generated.")

    # 6. Compute metrics and populate experiment_results SQLite table
    df = pd.DataFrame(trips)
    
    # Calculate MAE
    baseline_mae = np.mean(np.abs(df['_predicted_eta_baseline_mins'] - df['_actual_arrival_mins']))
    proposed_mae = np.mean(np.abs(df['_predicted_eta_proposed_mins'] - df['_actual_arrival_mins']))

    # Calculate RMSE
    baseline_rmse = np.sqrt(np.mean((df['_predicted_eta_baseline_mins'] - df['_actual_arrival_mins'])**2))
    proposed_rmse = np.sqrt(np.mean((df['_predicted_eta_proposed_mins'] - df['_actual_arrival_mins'])**2))

    # Mean Delay
    mean_delay = np.mean(df['_actual_arrival_mins'] - planned_minutes)

    # Number of ETA Updates
    # In baseline, there are 0 updates because the schedule is static.
    # In proposed, an update occurs whenever the proposed ETA differs by >= 2 minutes.
    baseline_updates = 0
    # For simulation, proposed updates count trips where proposed ETA diff from planned is >= 2
    proposed_updates_count = sum(1 for trip in trips if abs(trip['_predicted_eta_proposed_mins'] - planned_minutes) >= 2.0)

    # Enquiries simulation rule:
    # Baseline enquiries: 12 enquiries per trip if error is large, plus base of 10.
    # Proposed enquiries: 3 enquiries per trip if error is large, plus base of 2 (due to clarity).
    baseline_enquiries = 0
    proposed_enquiries = 0
    for trip in trips:
        base_err = abs(trip['_predicted_eta_baseline_mins'] - trip['_actual_arrival_mins'])
        prop_err = abs(trip['_predicted_eta_proposed_mins'] - trip['_actual_arrival_mins'])
        
        # Enquiries count cannot be negative
        baseline_enquiries += int(max(0, np.random.poisson(base_err * 0.8 + 0.5)))
        proposed_enquiries += int(max(0, np.random.poisson(prop_err * 0.2 + 0.1)))

    print(f"Metrics results computed:")
    print(f"Baseline MAE: {baseline_mae:.2f}, Proposed MAE: {proposed_mae:.2f}")
    print(f"Baseline RMSE: {baseline_rmse:.2f}, Proposed RMSE: {proposed_rmse:.2f}")
    print(f"Baseline Enquiries: {baseline_enquiries}, Proposed Enquiries: {proposed_enquiries}")

    # Write into SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Clean old results
    cursor.execute("DELETE FROM experiment_results;")
    
    results = [
        ('MAE', round(baseline_mae, 2), round(proposed_mae, 2)),
        ('RMSE', round(baseline_rmse, 2), round(proposed_rmse, 2)),
        ('Mean Delay', round(mean_delay, 2), round(mean_delay, 2)), # Mean Delay is property of actuals
        ('ETA Updates', float(baseline_updates), float(proposed_updates_count)),
        ('Status Enquiries', float(baseline_enquiries), float(proposed_enquiries))
    ]
    cursor.executemany("INSERT INTO experiment_results (metric_name, baseline_value, proposed_value) VALUES (?, ?, ?);", results)
    
    conn.commit()
    conn.close()
    print("Database experiment_results table populated.")

def generate_sample_routes_csv():
    """Generates the data/sample_data.csv containing sample stops data."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, 'sample_data.csv')
    
    stops_data = [
        {"route_id": "Route 1", "stop_name": "Stop A - Oak St", "planned_arrival": "08:00 AM", "lat": 37.7949, "lon": -122.4394},
        {"route_id": "Route 1", "stop_name": "Stop B - Pine St", "planned_arrival": "08:10 AM", "lat": 37.7889, "lon": -122.4294},
        {"route_id": "Route 1", "stop_name": "Stop C - Maple Ave", "planned_arrival": "08:20 AM", "lat": 37.7819, "lon": -122.4244},
        {"route_id": "Route 2", "stop_name": "Stop D - Elm Rd", "planned_arrival": "08:00 AM", "lat": 37.7549, "lon": -122.4494},
        {"route_id": "Route 2", "stop_name": "Stop E - Cedar Ln", "planned_arrival": "08:10 AM", "lat": 37.7609, "lon": -122.4394},
        {"route_id": "Route 2", "stop_name": "Stop F - Birch Blvd", "planned_arrival": "08:20 AM", "lat": 37.7689, "lon": -122.4294},
        {"route_id": "Route 3", "stop_name": "Stop G - Willow Dr", "planned_arrival": "08:00 AM", "lat": 37.7549, "lon": -122.3994},
        {"route_id": "Route 3", "stop_name": "Stop H - Spruce Way", "planned_arrival": "08:10 AM", "lat": 37.7609, "lon": -122.4094},
        {"route_id": "Route 3", "stop_name": "Stop I - Redwood Ct", "planned_arrival": "08:20 AM", "lat": 37.7689, "lon": -122.4144}
    ]
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["route_id", "stop_name", "planned_arrival", "lat", "lon"])
        writer.writeheader()
        writer.writerows(stops_data)

if __name__ == '__main__':
    generate_experiment_dataset()
    generate_sample_routes_csv()
