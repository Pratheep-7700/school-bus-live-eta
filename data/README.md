# Simulation Datasets

This directory stores fictional datasets generated for evaluating and demonstrating the Live School Bus ETA prototype.

## Files

1. **`sample_data.csv`**:
   - Contains localized sample coordinates, bus routes, stops, and initial student configurations used for initial seeding.

2. **`eta_experiment.csv`**:
   - Contains 550 simulated bus trips used to empirically evaluate Baseline vs. Proposed Dynamic ETA prediction models.
   - **Schema**:
     - `trip_id`: Unique identifier (e.g., `TRIP_0001` through `TRIP_0550`).
     - `bus_id`: Vehicle identifier (`101`, `102`, `103`).
     - `route_id`: Assigned route (`Route 1`, `Route 2`, `Route 3`).
     - `planned_eta`: Static scheduled arrival time.
     - `predicted_eta_baseline`: Predicted arrival according to static schedule.
     - `predicted_eta_proposed`: Dynamic predicted arrival taking attendance, traffic, and telemetry into account.
     - `actual_arrival`: Simulated ground-truth arrival time.
     - `student_count`: Number of students present at the stop.
     - `dwell_time`: Boarding dwell duration in minutes.
     - `traffic_level`: Traffic congestion index (`LOW`, `MEDIUM`, `HIGH`).
     - `traffic_delay`: Delay added by traffic (0m, 3m, 7m).
     - `gps_available`: Binary flag (1 = active, 0 = sensor failure).
     - `network_available`: Binary flag (1 = online, 0 = store-and-forward mode).
     - `customer_commitment`: Target pickup commitment time for parent notification.
