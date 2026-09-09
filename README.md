# Live ETA Communication Service for School Bus Network

A simple, transparent, and resilient real-time school bus ETA prediction and communication system designed for school networks serving students with variable attendance.

> **Note**: This is a student/college prototype (SIH model). All GPS locations, traffic feeds, sensor readings, and student attendance datasets are simulated locally without requiring external paid APIs or physical GPS hardware.

---

## Overview

School bus arrival times fluctuate significantly due to traffic congestion, unpredictable student boarding delays, and varying daily student attendance. Traditional static timetables fail to reflect these changes, leaving parents and administrators uncertain. 

This prototype provides an end-to-end web application that dynamically updates arrival times, communicates meaningful changes with human-understandable explanations, preserves an immutable audit trail, handles sensor and network failures via safe fallbacks, and benchmarks its performance against a static schedule baseline.

---

## Problem Statement

1. **Static Timetable Disconnect**: Conventional school transport systems rely on fixed schedules that cannot account for real-time traffic or boarding delays.
2. **Variable Student Attendance**: Missing students cause buses to wait unnecessarily, or skipped stops cause buses to arrive unexpectedly early.
3. **Alert Fatigue & Confusion**: Parents are either bombarded with minor coordinate shifts or receive no explanation when a 10-minute delay occurs.
4. **Hardware & Telemetry Vulnerabilities**: Real-world buses operate across patchy cellular coverage and experience occasional GPS hardware or sensor outages.
5. **High Enquiry Burden**: When buses are late without updates, parents flood school administration with phone calls.

---

## Solution

The **Live ETA Communication Service** provides:
- **Attendance-Aware Dynamic ETA Engine**: Computes travel time using Haversine distance, speed, traffic index, and stop dwell times that dynamically scale with present students ($30\text{s base} + 20\text{s/student}$).
- **Meaningful Change Filtering & Explanation**: Emits notifications only for shifts $\ge 2$ minutes, with transparent factor breakdowns (e.g., `Traffic: +3 min, Boarding: +1.5 min`).
- **Parent Commitment Tracking**: Monitors individual student pickup target times and flags when commitments are `ON_TIME`, `AT_RISK`, or `BREACHED`.
- **Fault-Tolerant Architecture**: Implements safety fallbacks for GPS loss, traffic feed disconnection, sensor discrepancies, and a **Store-and-Forward** queue for network outages.
- **Auditable Ledger**: Records every ETA update with timestamp, bus ID, input parameters, and update source (`AUTOMATIC`, `MANUAL`, `FALLBACK`).
- **Empirical Baseline Comparison**: Benchmarks dynamic ETAs against static schedules across 550+ simulated trips.

---

## Key Features

- **Operations Dashboard**: Fleet overview displaying active, on-time, and delayed buses, average prediction errors, and enquiry call volumes.
- **Interactive Live Fleet Map**: Real-time Leaflet.js map with route polylines, stop pins, and moving vehicle markers with popup telemetry.
- **Attendance Management**: Mark students Present or Absent, automatically recalculating intermediate dwell times.
- **Failure Injection Panel**: One-click toggles to test GPS drop, network outage, traffic feed loss, and abnormal sensor readings.
- **Store-and-Forward Offline Sync**: Queues events locally during network loss and flushes them to SQLite once reconnected.
- **Manual Driver Fallback**: Allows drivers or dispatchers to log manual ETA updates when automated telemetry is unavailable.
- **Automated 7-Step Demo**: Guided walkthrough designed for SIH judges and evaluators.
- **Statistical Analytics & Reports**: Chart.js graphs comparing MAE, RMSE, delay causes, and call volume reductions.
- **Parent Feedback Collection**: 5-question Likert survey storing responses and calculating usability scores.

---

## Architecture

The system follows a clean, modular design without unnecessary microservices or complex distributed frameworks:

```
Browser
   ↓  (HTML5, Leaflet.js, Bootstrap 5, Chart.js, Fetch API)
 Flask Server (app.py)
   ↓  (REST endpoints, state coordination, simulation clock)
ETA Engine (eta_engine/)
   ↓  (Haversine travel time + attendance dwell + traffic delays)
SQLite Database (database/)
   ↓  (Buses, routes, stops, students, attendance, audit history)
Notification Subsystem
   ↓  (Threshold evaluation: >= 2m warning, >= 5m critical alert)
Audit Log (eta_history)
      (Immutable chronological ledger of all ETA changes)
```

See [documentation/architecture.md](documentation/architecture.md) and [documentation/workflow.md](documentation/workflow.md) for detailed diagrams.

---

## Technology Stack

- **Backend**: Python 3, Flask
- **Database**: SQLite
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5
- **Mapping**: Leaflet.js with OpenStreetMap tiles
- **Data Visualization**: Chart.js
- **Data Analysis**: Pandas, NumPy
- **Testing**: pytest

---

## Project Structure

```
school-bus-live-eta/
│
├── app.py                      # Main Flask application & REST endpoints
├── requirements.txt            # Project dependencies
├── README.md                   # Project documentation & run guide
├── LICENSE                     # MIT License
├── CONTRIBUTING.md             # Contribution guidelines
├── .gitignore                  # Git ignore rules
│
├── database/                   # SQLite database management
│   ├── __init__.py
│   ├── database.py             # Connection pooling, init & schema loader
│   ├── schema.sql              # Table definitions (10 tables)
│   └── seed.py                 # Standalone database seeding script
│
├── eta_engine/                 # ETA prediction & explanation logic
│   ├── __init__.py
│   ├── eta_calculator.py       # Haversine distance, speed & dynamic ETA
│   ├── baseline.py             # Static schedule-only baseline calculator
│   ├── explanation.py          # Factor decomposition (traffic, dwell, sensors)
│   └── fallback.py             # Fallback estimators for fault modes
│
├── simulator/                  # Fleet movement & telemetry simulation
│   ├── __init__.py
│   ├── simulation.py           # Clock loop, waypoints & store-and-forward queue
│   ├── data_generator.py       # 550+ trip dataset generator & metrics calculator
│   └── failure_simulator.py    # Failure state registry
│
├── experiments/                # Empirical evaluation scripts & outputs
│   ├── generate_experiment_data.py
│   ├── run_experiment.py       # Computes MAE, RMSE, & enquiry reduction %
│   └── experiment_results.csv  # Computed statistical results
│
├── tests/                      # Automated test suite (pytest)
│   ├── test_eta.py             # Tests ETA calculation, dwell time & explanations
│   ├── test_baseline.py        # Tests static schedule baseline behavior
│   ├── test_audit.py           # Tests immutable audit logging
│   ├── test_failures.py        # Tests GPS, network & sensor fallbacks
│   └── test_api_integration.py # Tests all Flask REST API routes
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Common layout with navigation & simulation controls
│   ├── dashboard.html          # Admin dashboard & live metrics
│   ├── live_tracking.html      # Leaflet live map view
│   ├── attendance.html         # Student attendance & commitment matrix
│   ├── routes.html             # Route plans & stop details
│   ├── eta_history.html        # Immutable audit log with filtering
│   ├── failures.html           # Failure injection & fallback panel
│   ├── experiment.html         # Experiment results comparison view
│   ├── reports.html            # Chart.js analytical charts
│   └── feedback.html           # Parent validation feedback survey
│
├── static/                     # CSS and client-side JavaScript
│   ├── css/
│   │   └── style.css           # Custom styles & dark sidebar theme
│   └── js/
│       ├── dashboard.js        # Dashboard state polling & metric updates
│       ├── map.js              # Leaflet bus markers & route rendering
│       ├── simulation.js       # Simulation controls & 7-step demo sequence
│       ├── charts.js           # Chart.js configuration
│       └── failures.js         # Failure injection & store-and-forward sync
│
├── data/                       # Datasets
│   ├── README.md               # Dataset descriptions & schema
│   ├── sample_data.csv         # Route & stop coordinates
│   └── eta_experiment.csv      # 550-trip experimental dataset
│
├── documentation/              # Technical design & research documentation
│   ├── architecture.md         # Component flow & block diagrams
│   ├── workflow.md             # End-to-end data processing workflow
│   ├── eta_algorithm.md        # Detailed mathematical formula breakdown
│   ├── failure_mode_analysis.md# FMEA failure, detection & recovery matrix
│   ├── experiment_methodology.md# Experimental design & evaluation metrics
│   └── user_validation.md      # Parent validation survey methodology
│
└── screenshots/                # Visual previews
    └── README.md
```

---

## ETA Calculation

The proposed system calculates dynamic ETAs using an additive model:

$$\text{ETA} = \text{Current Time} + \text{Remaining Travel Time} + \text{Expected Dwell Time} + \text{Traffic Delay}$$

1. **Travel Time**: $\left( \frac{\text{Haversine Distance (km)}}{\text{Average Speed (km/h)}} \right) \times 60$ minutes.
2. **Attendance Dwell Time**: $\text{dwell\_time} = 30 + (\text{present\_students} \times 20)$ seconds. Absent students eliminate 20 seconds of boarding time.
3. **Traffic Delay**: $\text{LOW} = 0\text{ min}, \text{MEDIUM} = +3\text{ min}, \text{HIGH} = +7\text{ min}$.
4. **Meaningful Change Filter**:
   - Change $< 2$ min: No customer notification.
   - Change $\ge 2$ min: Standard ETA update notification.
   - Change $\ge 5$ min: High-priority delay alert.

---

## Baseline vs Proposed System

| Feature | Baseline System | Proposed Dynamic System |
| :--- | :--- | :--- |
| **Prediction Basis** | Static scheduled timetable | Real-time GPS + Attendance + Traffic |
| **Attendance Response** | Assumes fixed stop duration | Scales dwell time ($30\text{s} + 20\text{s/student}$) |
| **Traffic Response** | Ignores traffic congestion | Ingests real-time traffic levels (LOW/MED/HIGH) |
| **Failure Recovery** | Fails silently on delay | GPS, Network, Traffic & Sensor fallbacks |
| **Parent Transparency** | No explanations provided | Explains causes (Traffic, Boarding, Dwell) |
| **Auditability** | None | Full immutable SQLite audit trail |

---

## Failure Handling

The prototype implements graceful degradation across four failure modes:

| Failure Mode | Detection | Fallback Mechanism | Recovery |
| :--- | :--- | :--- | :--- |
| **GPS Failure** | Stream timeout / null coords | Retains **last known position**; calculates ETA via planned stop distances | Resumes live tracking when feed restores |
| **Network Outage** | Connection drop / failed POST | **Store-and-Forward**: caches events in local memory queue | Flushes and syncs queue to SQLite once online |
| **Traffic Data Loss** | Disconnected traffic feed | Defaults to historical **MEDIUM** traffic delay (+3 min) | Re-engages real-time feed on reconnect |
| **Sensor Discrepancy**| Zero speed reported while moving | Ignores faulty reading; applies **last valid speed** (30 km/h) | Restores live sensor readings |

---

## Audit History

Every meaningful ETA change generates an immutable record in the `eta_history` table:
- **Timestamp** & **Bus ID**
- **Previous ETA** vs. **New ETA**
- **Net Delay** (minutes)
- **Causal Breakdown** (`Traffic: +3 min, Boarding: +2 min`)
- **Telemetry Context** (GPS status, network status, traffic level, student count)
- **Source Origin**: `AUTOMATIC`, `MANUAL`, or `FALLBACK`

---

## Experiment

The system includes an empirical evaluation pipeline based on **550 simulated bus trips** saved to `data/eta_experiment.csv`. Each trip simulates variable passenger attendance (0–11 students), traffic conditions, random route noise, and occasional telemetry dropouts.

Run the experiment via:
```bash
python experiments/run_experiment.py
```

---

## Metrics

Empirical results from the 550-trip simulated evaluation:

| Metric | Baseline (Static Schedule) | Proposed (Dynamic ETA) | Improvement |
| :--- | :--- | :--- | :--- |
| **MAE (Mean Absolute Error)** | **6.67 min** | **2.19 min** | **67.2% reduction in error** |
| **RMSE (Root Mean Squared Error)**| **7.36 min** | **2.66 min** | **63.9% reduction in error** |
| **Mean Delay** | 6.67 min | 6.67 min | Ground truth reference |
| **ETA Updates Communicated** | 0 updates | 474 updates | Proactive parent notifications |
| **Customer Status Enquiries** | **3,393 calls** | **355 calls** | **89.5% reduction in calls** |

> **Label**: *SIMULATED EXPERIMENT RESULTS*

---

## Installation

Follow these steps to set up the project locally:

### 1. Clone the repository
```bash
git clone https://github.com/your-username/school-bus-live-eta.git
```

### 2. Open project directory
```bash
cd school-bus-live-eta
```

### 3. Create virtual environment
```bash
python -m venv venv
```

### 4. Activate virtual environment
- **Windows (Command Prompt / PowerShell)**:
  ```powershell
  venv\Scripts\activate
  ```
- **macOS / Linux**:
  ```bash
  source venv/bin/activate
  ```

### 5. Install dependencies
```bash
pip install -r requirements.txt
```

### 6. Initialize database
```bash
python database/seed.py
```

---

## Running the Application

Start the Flask local development server:
```bash
python app.py
```

Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Running Tests

Execute the automated test suite using `pytest`:
```bash
python -m pytest
```

To run with verbose output:
```bash
python -m pytest -v
```

All 32 tests across `test_eta.py`, `test_baseline.py`, `test_audit.py`, `test_failures.py`, and `test_api_integration.py` should pass cleanly.

---

## Demo Instructions

For live presentations and SIH evaluation, click the **"Run Demo"** button on the top navigation bar. The automated 7-step sequence will demonstrate:

1. **Step 1: Normal Bus Departure**: BUS-101 departs on Route 1 on schedule.
2. **Step 2: Attendance & Dwell Increase**: Present student count increases at Stop A; boarding dwell time increases, dynamically increasing the ETA with an explanatory note.
3. **Step 3: Traffic Delay**: Traffic switches to HIGH (+7 min); ETA recalculates and issues a warning notification.
4. **Step 4: GPS Failure & Fallback**: GPS is deactivated; the bus pins to its last known location and switches to distance-based fallback estimation.
5. **Step 5: Network Outage & Store-and-Forward**: Cellular network drops; events accumulate in the local offline queue without data loss.
6. **Step 6: Network Restoration**: Network reconnects; cached events flush and synchronize with SQLite.
7. **Step 7: Audit History Inspection**: Page navigates to the ETA History view to inspect the immutable audit log and explainable records.

---

## Screenshots

Visual preview descriptions are provided in [screenshots/README.md](screenshots/README.md).

---

## Limitations

- **Simulated Environment**: Coordinates, traffic feeds, sensor readings, and attendance are generated via software simulation rather than physical OBD-II / GPS hardware.
- **Route Topology**: Uses localized Euclidean/Haversine distance vectors between designated waypoints rather than paid commercial turn-by-turn road snapping APIs.
- **Traffic Discretization**: Traffic conditions are modeled into three discrete levels (`LOW`, `MEDIUM`, `HIGH`) rather than continuous traffic density feeds.

---

## Future Improvements

- Integration with open-source road network routing engines (such as OSRM or OpenRouteService).
- Native mobile push notification client for parents (PWA or Android/iOS).
- Machine learning-based dwell time prediction factoring in historical weather and school calendar events.
- RFID / NFC badge tap simulation for automated student check-in.

---

## Team

- Developed for the **Smart India Hackathon (SIH)** / College Capstone Showcase.
- **Role**: Full-Stack Prototype Development, Telemetry Simulation, and Dynamic ETA Engineering.
