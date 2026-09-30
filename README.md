# Live ETA Communication Service for School-Bus Network

A transparent, resilient, and attendance-aware real-time school bus arrival prediction and parent communication platform designed for school networks serving students with variable attendance.

> **Prototype Specification**: Designed as a college/capstone prototype (SIH model). All vehicle coordinates, route waypoints, traffic conditions, hardware sensor readings, and passenger attendance profiles are generated locally via deterministic simulation without requiring external paid APIs or physical GPS hardware.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Folder Structure](#3-folder-structure)
4. [Installation](#4-installation)
5. [Running Locally](#5-running-locally)
6. [Dashboard](#6-dashboard)
7. [ETA Calculation](#7-eta-calculation)
8. [Failure Handling](#8-failure-handling)
9. [API Documentation](#9-api-documentation)
10. [Database Schema](#10-database-schema)
11. [Unit Testing](#11-unit-testing)
12. [Error Handling](#12-error-handling)
13. [Simulation](#13-simulation)
14. [Experiment Evaluation](#14-experiment-evaluation)
15. [Deployment](#15-deployment)
16. [Troubleshooting](#16-troubleshooting)
17. [Future Improvements](#17-future-improvements)

---

## 1. Project Overview

School bus arrival times fluctuate significantly due to traffic congestion, unforeseen stop delays, and varying daily passenger attendance. Traditional transit tracking systems rely either on fixed timetables or raw GPS distance without considering dwell variations, causing high prediction errors and flooding school administration with anxious parent status enquiries.

The **Live ETA Communication Service** provides:
- **Attendance-Aware Dynamic ETA**: Scales stop dwell time based on confirmed passenger attendance ($30\text{s base} + 20\text{s per present student}$). Absent students eliminate 20 seconds of boarding time per skipped passenger.
- **Explainable Predictions**: Communicates transparent, natural-language explanations (e.g., `Delay +5 min, mainly due to higher-than-average boarding time at the previous stop, with additional delay from slower traffic`).
- **Meaningful Change Thresholding**: Emits parent notifications only when an ETA change is $\ge 2$ minutes (warning) or $\ge 5$ minutes (critical alert), eliminating alert fatigue caused by minor coordinate noise.
- **Parent Commitment Tracking**: Monitors individual pickup commitments ($\pm 5$ min window) and automatically flags commitments as `MET`, `AT_RISK`, or `BREACHED`.
- **Fault-Tolerant Resilience**: Features deterministic safety fallbacks for GPS loss, cellular network dropouts (store-and-forward queue), traffic feed failure, and speed sensor discrepancies.
- **Append-Only Immutable Audit Trail**: Records every plan recalculation, telemetry ingestion, and manual driver override in SQLite (`eta_plan_audit` and `eta_history`).

---

## 2. Architecture

The system utilizes a modular, light-footprint architecture separating the browser interface, web API routing, calculation engine, SQLite storage, and hardware simulation:

```
+-------------------------------------------------------------------------+
|                              Web Browser                                |
|   (Leaflet.js Map, Chart.js Analytics, Bootstrap 5 UI, Live Polling)   |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ HTTP REST / JSON
+-------------------------------------------------------------------------+
|                           Flask API (app.py)                            |
|     (Route Handlers, State Coordination, Payload Validation, Audit)     |
+-------------------------------------------------------------------------+
          │                                 │                    │
          ▼                                 ▼                    ▼
+---------------------+           +------------------+  +-----------------+
|     ETA Engine      |           | Simulation Loop  |  | Offline Queue   |
| (eta_calculator.py, |           | (simulation.py,  |  | Store & Forward |
|  explanation.py,    |           |  failure_sim.py) |  | In-Memory Cache |
|  fallback.py)       |           +------------------+  +-----------------+
+---------------------+                     │                    │
          │                                 │                    │
          └────────────────────────┬────────┘                    │
                                   ▼                             │
+-------------------------------------------------------------------------+
|                         SQLite Database Layer                           |
|       (school_bus.db: 13 Tables, Append-Only Ledger, 10s Timeout)       |
+-------------------------------------------------------------------------+
```

### Component Breakdown
1. **Frontend**: Responsive Bootstrap 5 dashboards, interactive Leaflet.js fleet tracking maps, and Chart.js performance graphs.
2. **API Layer (`app.py`)**: 27 REST endpoints handling bus telemetry, simulation controls, failure injection, attendance updates, and audit queries.
3. **ETA Engine (`eta_engine/`)**: Mathematical implementation of Haversine spherical distance, attendance-based dwell time, categorical traffic adjustments, and causal factor ranking.
4. **Explanation Service (`services/eta_explanation_service.py`)**: Natural-language rule engine attributing delay causes to specific data-backed telemetry factors.
5. **Simulation Core (`simulator/`)**: Discrete-time clock simulator advancing fleet positions, processing stop arrivals, countdown timers, and hardware fault injection.
6. **Storage Layer (`database/`)**: Relational SQLite database with connection pooling, deduplication ledger, and immutable audit logging.

---

## 3. Folder Structure

```
school_bus_eta/
├── app.py                      # Flask application factory, routes & API endpoints
├── requirements.txt            # Python dependencies (Flask, pandas, numpy, pytest, etc.)
├── README.md                   # Complete architectural guide & documentation
├── CONTRIBUTING.md             # Contributor workflows & guidelines
├── LICENSE                     # MIT License
├── .gitignore                  # Git ignore rules for virtual environments & SQLite
│
├── database/                   # Relational database layer
│   ├── database.py             # Connection factory, table migrations & audit helpers
│   ├── schema.sql              # DDL schema definitions for 13 SQLite tables
│   ├── school_bus.db           # SQLite database file
│   ├── seed.py                 # Standalone database initialization script
│   └── simulation_state.json   # Mutable simulation clock & vehicle state store
│
├── eta_engine/                 # Real-time ETA prediction & explanation logic
│   ├── eta_calculator.py       # Haversine distance, speed & dynamic ETA calculation
│   ├── baseline.py             # Static timetable schedule baseline calculator
│   ├── explanation.py          # Delay factor decomposition & summary generator
│   └── fallback.py             # Fallback estimators for GPS, traffic & speed sensors
│
├── services/                   # High-level domain services
│   └── eta_explanation_service.py # Natural-language explanation rule engine
│
├── simulator/                  # Fleet movement & telemetry failure simulation
│   ├── simulation.py           # Simulation clock loop, waypoints & store-and-forward queue
│   ├── failure_simulator.py    # Subsystem failure state toggles (GPS, network, traffic, sensor)
│   └── data_generator.py       # 550+ trip dataset generator & statistical metrics compiler
│
├── experiments/                # Empirical validation & baseline benchmarking
│   ├── run_experiment.py       # Computes MAE, RMSE & enquiry call reduction metrics
│   ├── generate_experiment_data.py # Synthesizes randomized trip variations
│   └── experiment_results.csv  # Computed statistical results
│
├── tests/                      # Automated test suite (pytest / unittest)
│   ├── test_api_integration.py # 15 tests: Endpoints (/api/buses, routes, simulation, etc.)
│   ├── test_audit.py           # 3 tests: Online/offline notification logging & queue sync
│   ├── test_baseline.py        # 3 tests: Static timetable baseline verification
│   ├── test_edge_cases.py      # 19 tests: Boundary inputs, zero/high attendance, API 400s
│   ├── test_eta.py             # 7 tests: Math, dwell formula & threshold rules
│   ├── test_eta_explanation.py # 8 tests: Causal factor decomposition & narrative checks
│   ├── test_eta_plan_audit.py  # 4 tests: Append-only ledger & schema column validation
│   ├── test_failures.py        # 4 tests: GPS, network, traffic & sensor fallbacks
│   └── test_store_and_forward.py # 4 tests: Deduplication ledger & batch synchronization
│
├── documentation/              # Technical deep-dives & architecture documentation
│   ├── UNIT_TESTING.md         # Granular unit test documentation & coverage matrix
│   ├── ERROR_HANDLING.md       # Error boundaries & fault tolerance architecture
│   ├── architecture.md         # Component flow & block diagrams
│   ├── workflow.md             # End-to-end data processing workflow
│   ├── eta_algorithm.md        # Detailed mathematical formula breakdown
│   ├── failure_mode_analysis.md# FMEA failure, detection & recovery matrix
│   ├── experiment_methodology.md# Experimental design & evaluation metrics
│   └── user_validation.md      # Parent validation survey methodology
│
├── templates/                  # Jinja2 HTML5 UI templates
│   ├── base.html               # Shared layout, navigation bar & simulation controls
│   ├── dashboard.html          # Operational overview, metric cards & recent alerts
│   ├── live_tracking.html      # Interactive Leaflet.js fleet tracking map
│   ├── attendance.html         # Student attendance management & commitment matrix
│   ├── routes.html             # Route plans, stop sequences & timetable details
│   ├── eta_history.html        # Immutable audit trail with multi-field filtering
│   ├── failures.html           # Subsystem failure injection & fallback test panel
│   ├── experiment.html         # Empirical baseline vs. proposed comparison view
│   ├── reports.html            # Chart.js analytics & error distribution graphs
│   └── feedback.html           # 5-question Likert survey for parent validation
│
├── static/                     # Web assets
│   ├── css/style.css           # Custom styling, responsive layout & dark sidebar
│   └── js/                     # Client-side JavaScript modules
│       ├── dashboard.js        # Polling & dashboard metric updates
│       ├── map.js              # Leaflet map pins, polylines & vehicle marker motion
│       ├── simulation.js       # Simulation controls & 7-step guided demo sequence
│       ├── charts.js           # Chart.js performance visualizations
│       └── failures.js         # Failure toggles & store-and-forward queue sync
│
├── data/                       # Experimental CSV datasets
│   ├── eta_experiment.csv      # 550-trip simulated evaluation dataset
│   └── sample_data.csv         # Route coordinate seeds
│
└── screenshots/                # Visual user interface documentation
    └── README.md
```

---

## 4. Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.10 through 3.14)
- SQLite 3 (bundled with standard Python distributions)
- Modern web browser (Chrome, Edge, Firefox, Safari)

### Step-by-Step Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/school_bus_eta.git
   cd school_bus_eta
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **Windows (Command Prompt)**:
     ```cmd
     .\venv\Scripts\activate.bat
     ```
   - **macOS / Linux**:
     ```bash
     source venv/bin/activate
     ```

4. **Install required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Initialize the SQLite database and seed initial routes**:
   ```bash
   python database/seed.py
   ```

---

## 5. Running Locally

Start the local Flask development server:
```bash
python app.py
```

The application will start on:
```
http://127.0.0.1:5000/
```

Navigate to `http://127.0.0.1:5000/` in your browser to access the live dashboard.

---

## 6. Dashboard

The Operations Dashboard (`/dashboard`) provides real-time visibility into the entire school transit network:
- **Fleet Summary Cards**: Displays total active buses, on-time count, delayed count, and currently dwelling vehicles.
- **Prediction Accuracy**: Live Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) against ground truth arrival times.
- **Enquiry Call Reduction Metric**: Real-time counter showing estimated call volume reduction achieved by proactive ETA communication.
- **Active Alerts Feed**: Chronological stream of notifications with severity badging (`INFO`, `WARNING`, `CRITICAL`).
- **Interactive Map Preview**: Leaflet map view tracking buses along Route 1, Route 2, and Route 3.
- **Guided 7-Step Demo Runner**: Top navigation bar includes a "Run Demo" button executing an automated walkthrough demonstrating boarding delays, traffic spikes, GPS dropouts, offline queuing, and audit verification.

---

## 7. ETA Calculation

The dynamic ETA engine predicts arrival times using an additive travel time model factoring in distance, attendance dwell, and congestion:

$$\text{ETA} = \text{Current Time} + \sum_{i} \left( \text{Travel Time}_i + \text{Traffic Delay}_i + \text{Dwell Time}_i \right)$$

### 1. Great-Circle Travel Time
Distance between coordinates is computed via the **Haversine Formula**:
$$a = \sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)$$
$$d = 2 \cdot R \cdot \text{atan2}(\sqrt{a}, \sqrt{1-a})$$
$$\text{Travel Time (min)} = \left( \frac{d\text{ (km)}}{\text{Speed (km/h)}} \right) \times 60$$

### 2. Variable Attendance Dwell Time
Unlike static schedules that assume fixed 2-minute stops, dwell time scales dynamically with verified attendance:
$$\text{Dwell Time (seconds)} = 30 + (\text{Present Students} \times 20)$$
- **Base Dwell ($30$s)**: Covers vehicle deceleration, door opening, mirror checking, and door closure.
- **Boarding Time ($20$s/student)**: Covers individual student embarkation, scanning, and seating.
- **Terminal Campus Stop**: Dwell time is set to $0$ (alighting at school is not bounded by intermediate boarding).

### 3. Categorical Traffic Adjustments
Traffic delays are applied to the active route leg:
- `LOW`: $0$ minutes delay (nominal flow)
- `MEDIUM`: $+3$ minutes delay (moderate congestion)
- `HIGH`: $+7$ minutes delay (severe rush hour bottleneck)

### 4. Meaningful Change Filter
- **$\Delta \text{ETA} < 2$ min**: Ignored to prevent parent alert fatigue.
- **$\Delta \text{ETA} \ge 2$ min**: Standard update notification emitted (`WARNING`).
- **$\Delta \text{ETA} \ge 5$ min**: High-priority delay alert emitted (`CRITICAL`).

---

## 8. Failure Handling

The application incorporates graceful degradation across four primary hardware failure modes:

| Failure Mode | Detection Criterion | Fallback Mechanism | Parent / Admin Impact |
| :--- | :--- | :--- | :--- |
| **GPS Signal Loss** | `failures.case_name='gps' == 'ACTIVE'` or null coordinates | Freezes bus marker at last known coordinates (`get_fallback_gps`); computes ETA using remaining waypoint distance | Bus marked `OFFLINE`; ETA includes $+3$ min search buffer note |
| **Network Outage** | `failures.case_name='network' == 'ACTIVE'` or HTTP failure | **Store-and-Forward**: caches notifications and audit logs in `store_and_forward_queue` | Changes queued locally; auto-synced to SQLite upon reconnection |
| **Traffic Feed Loss** | `failures.case_name='traffic' == 'ACTIVE'` or API timeout | Substitutes historical **MEDIUM** congestion estimate ($+3$ min) | System avoids artificial zero-traffic assumptions |
| **Sensor Discrepancy** | `failures.case_name='sensor' == 'ACTIVE'` or speed $\le 0$ while moving | Substitutes calibrated urban transit speed ($30.0$ km/h) | Prevents infinite ETAs or division-by-zero errors |

---

## 9. API Documentation

Every endpoint listed below actually exists in `app.py` and is verified by automated integration tests.

### Fleet & Live Tracking Endpoints

#### `GET /api/buses`
- **Category**: ETA-related / Live Tracking
- **Purpose**: Retrieves all buses enriched with dynamic ETAs, next stop names, delay metrics, and natural-language explanations.
- **Request**: None
- **Response (200 OK)**:
  ```json
  [
    {
      "bus_id": "101",
      "registration_number": "SB-101",
      "driver_name": "John Doe",
      "route_id": "Route 1",
      "current_latitude": 37.7949,
      "current_longitude": -122.4394,
      "speed": 30.0,
      "status": "ON_ROUTE",
      "next_stop_id": "Stop_A",
      "next_stop_name": "Stop A - Oak St",
      "eta": "08:00 AM",
      "delay": 0,
      "delay_minutes": 0.0,
      "eta_status": "ON_TIME",
      "primary_reason": "ON_SCHEDULE",
      "explanation": "Bus is currently on schedule. No significant delay detected.",
      "factors": []
    }
  ]
  ```
- **Status Codes**: 200 (Success), 500 (Internal Server Error)

---

#### `GET /api/routes`
- **Category**: ETA-related / Route Planning
- **Purpose**: Retrieves all routes with nested stop sequences, planned arrival times, and GPS coordinates.
- **Request**: None
- **Response (200 OK)**:
  ```json
  [
    {
      "route_id": "Route 1",
      "route_name": "Route 1 - North Valley",
      "student_count": 11,
      "stops": [
        {
          "stop_id": "Stop_A",
          "route_id": "Route 1",
          "stop_name": "Stop A - Oak St",
          "latitude": 37.7949,
          "longitude": -122.4394,
          "planned_arrival_time": "08:00 AM",
          "sequence": 1
        }
      ]
    }
  ]
  ```
- **Status Codes**: 200 (Success), 500 (Internal Server Error)

---

#### `GET /api/students`
- **Category**: Attendance-related / Commitment Tracking
- **Purpose**: Lists all registered students with attendance status, committed pickup window, expected ETA, and customer commitment status (`MET`, `AT_RISK`, `BREACHED`).
- **Request**: None
- **Response (200 OK)**:
  ```json
  [
    {
      "student_id": "S101",
      "student_name": "Arun Kumar",
      "route_id": "Route 1",
      "stop_id": "Stop_A",
      "stop_name": "Stop A - Oak St",
      "committed_pickup_time": "08:00 AM",
      "attendance_status": "Present",
      "expected_eta": "08:00 AM",
      "expected_delay_mins": 0,
      "commitment_status": "MET"
    }
  ]
  ```
- **Status Codes**: 200 (Success), 500 (Internal Server Error)

---

#### `GET /api/eta/<bus_id>`
- **Category**: ETA-related
- **Purpose**: Returns real-time dynamic ETAs to all remaining stops for a specific bus, along with structured causal factors and natural-language explanation.
- **Request**: URL parameter `bus_id` (e.g. `'101'`).
- **Response (200 OK)**:
  ```json
  {
    "bus_id": "101",
    "next_stop_id": "Stop_A",
    "next_stop_name": "Stop A - Oak St",
    "eta": "08:00 AM",
    "delay_minutes": 0.0,
    "status": "ON_TIME",
    "primary_reason": "ON_SCHEDULE",
    "explanation": "Bus is currently on schedule. No significant delay detected.",
    "factors": [],
    "etas": {
      "Stop_A": "08:00 AM",
      "Stop_B": "08:12 AM",
      "Stop_C": "08:24 AM",
      "School_1": "08:35 AM"
    }
  }
  ```
- **Status Codes**: 200 (Success), 400 (Bus not active / invalid bus_id)

---

### Ingestion & Store-and-Forward Endpoints

#### `POST /api/telemetry`
- **Category**: ETA-related / Telemetry Ingestion
- **Purpose**: Ingests live vehicle GPS telemetry, performs deduplication, updates vehicle position, recalculates ETA, generates natural-language explanation, and appends an immutable audit record.
- **Request Body**:
  ```json
  {
    "event_id": "d9b2d6a4-7c3a-4a8e-9d2a-1b4e6f8c0e2a",
    "bus_id": "101",
    "route_id": "Route 1",
    "trip_id": "TRIP-Route1",
    "timestamp": "08:05 AM",
    "latitude": 37.7949,
    "longitude": -122.4394,
    "speed": 28.5
  }
  ```
- **Validation**: Requires `bus_id`. Latitude and longitude must be valid floating point values.
- **Response (200 OK - First Receipt)**:
  ```json
  {
    "status": "SUCCESS",
    "event_id": "d9b2d6a4-7c3a-4a8e-9d2a-1b4e6f8c0e2a",
    "audit_id": 42,
    "bus_id": "101",
    "eta": "08:05 AM",
    "delay_minutes": 5.0,
    "primary_reason": "HIGH_BOARDING_TIME",
    "explanation": "Delay +5 minutes due to higher-than-average boarding time at the previous stop.",
    "factors": [
      {"factor": "boarding_time", "impact_minutes": 5.0}
    ]
  }
  ```
- **Response (200 OK - Duplicate Receipt)**:
  ```json
  {
    "status": "DUPLICATE",
    "event_id": "d9b2d6a4-7c3a-4a8e-9d2a-1b4e6f8c0e2a",
    "message": "Telemetry event already processed. Skipped duplicate."
  }
  ```
- **Status Codes**: 200 (Success / Duplicate), 400 (Missing bus_id or malformed payload)

---

#### `POST /api/telemetry/sync` (Alias: `POST /api/telemetry/batch`)
- **Category**: Failure-testing-related / Store-and-Forward
- **Purpose**: Synchronizes a batch of buffered telemetry packets from edge storage or client IndexedDB after network restoration, guaranteeing deduplication.
- **Request Body**:
  ```json
  {
    "batch": [
      {
        "event_id": "uuid-1",
        "bus_id": "101",
        "timestamp": "08:06 AM",
        "latitude": 37.7940,
        "longitude": -122.4380,
        "speed": 30.0
      },
      {
        "event_id": "uuid-2",
        "bus_id": "102",
        "timestamp": "08:06 AM",
        "latitude": 37.7550,
        "longitude": -122.4490,
        "speed": 30.0
      }
    ]
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "success": true,
    "processed_count": 2,
    "duplicate_count": 0,
    "error_count": 0,
    "results": [...]
  }
  ```
- **Status Codes**: 200 (Success), 400 (Invalid batch structure)

---

### Audit Trail Endpoints

#### `GET /api/audit/eta`
- **Category**: Audit-related
- **Purpose**: Queries immutable audit records from `eta_plan_audit` with multi-parameter filtering.
- **Query Parameters**:
  - `bus_id` (optional): Filter by vehicle ID (e.g., `'101'`).
  - `route_id` (optional): Filter by route ID (e.g., `'Route 1'`).
  - `trip_id` (optional): Filter by trip ID.
  - `date` (optional): Filter by creation date (`'YYYY-MM-DD'`).
  - `trigger_factor` (optional): Filter by trigger code (`'TRAFFIC_DELAY'`, `'GPS_TELEMETRY'`, etc.).
  - `limit` (optional): Page limit (default: 100).
  - `offset` (optional): Page offset (default: 0).
- **Response (200 OK)**:
  ```json
  [
    {
      "id": 1,
      "bus_id": "101",
      "route_id": "Route 1",
      "trip_id": "TRIP-Route1",
      "stop_id": "Stop_A",
      "event_type": "TELEMETRY_UPDATE",
      "trigger_factor": "GPS_TELEMETRY",
      "trigger_details": "Live GPS telemetry (37.7949, -122.4394) received at 30.0 km/h.",
      "previous_eta": "08:00 AM",
      "new_eta": "08:02 AM",
      "previous_delay_minutes": 0.0,
      "new_delay_minutes": 2.0,
      "explanation": "Bus is currently on schedule.",
      "created_at": "2026-09-30 08:02:00",
      "created_by": "telemetry_service"
    }
  ]
  ```
- **Status Codes**: 200 (Success), 500 (Internal Server Error)

---

#### `GET /api/audit/eta/<int:audit_id>`
- **Category**: Audit-related
- **Purpose**: Retrieves a single immutable audit record by primary key ID, including full serialized plans and raw telemetry snapshots.
- **Request**: URL integer parameter `audit_id`.
- **Response (200 OK)**:
  ```json
  {
    "id": 1,
    "bus_id": "101",
    "route_id": "Route 1",
    "previous_plan": "{\"eta\": \"08:00 AM\", \"stop_id\": \"Stop_A\"}",
    "new_plan": "{\"eta\": \"08:02 AM\", \"stop_id\": \"Stop_A\"}",
    "telemetry_snapshot": "{\"latitude\": 37.7949, \"longitude\": -122.4394, \"speed\": 30.0}",
    "created_at": "2026-09-30 08:02:00"
  }
  ```
- **Status Codes**: 200 (Success), 404 (Audit record not found)

---

### Operations & Control Endpoints

#### `POST /api/attendance`
- **Category**: Attendance-related / Dynamic Dwell
- **Purpose**: Updates student attendance status (`Present` or `Absent`), dynamically adjusting intermediate stop dwell times.
- **Request Body**:
  ```json
  {
    "student_id": "S101",
    "status": "Absent"
  }
  ```
- **Validation**: Requires `student_id`; `status` must be either `'Present'` or `'Absent'`.
- **Response (200 OK)**: `{"success": true}`
- **Status Codes**: 200 (Success), 400 (Invalid arguments)

---

#### `POST /api/traffic`
- **Category**: Traffic-related / ETA Recalculation
- **Purpose**: Modifies route traffic level (`LOW`, `MEDIUM`, `HIGH`), recalculating ETAs for all active buses, appending audit records, and issuing notifications.
- **Request Body**:
  ```json
  {
    "route_id": "Route 1",
    "traffic_level": "HIGH"
  }
  ```
- **Validation**: `traffic_level` must be strictly within `['LOW', 'MEDIUM', 'HIGH']`.
- **Response (200 OK)**: `{"success": true}`
- **Status Codes**: 200 (Success), 400 (Invalid arguments)

---

#### `POST /api/manual-eta`
- **Category**: Failure-testing-related / Driver Fallback
- **Purpose**: Allows drivers or dispatchers to submit a manual ETA override when automated telemetry is interrupted.
- **Request Body**:
  ```json
  {
    "bus_id": "101",
    "manual_eta": "08:15 AM",
    "location_name": "Near Oak St",
    "next_stop_id": "Stop_A"
  }
  ```
- **Validation**: Requires `bus_id`, `manual_eta` (`HH:MM AM/PM`), and `next_stop_id`.
- **Response (200 OK)**: `{"success": true, "message": "Manual ETA update recorded."}`
- **Status Codes**: 200 (Success), 400 (Invalid arguments)

---

#### `GET /api/history/<bus_id>`
- **Category**: Audit-related / ETA History
- **Purpose**: Returns chronological ETA updates from `eta_history`. Supports filtering by bus ID (`'all'` or specific ID) and optional `?reason=` substring query.
- **Status Codes**: 200 (Success)

---

#### `POST /api/simulation/start`, `/stop`, `/reset`, `/tick`, `GET /state`
- **Category**: Simulation-related
- **Purpose**: Controls the simulation clock loop ($07:58\text{ AM}$ initial state, $1$-minute discrete ticks).
- **Status Codes**: 200 (Success)

---

#### `POST /api/failure/gps`, `/network`, `/traffic`, `/sensor`, `GET /api/failures`
- **Category**: Failure-testing-related
- **Purpose**: Toggles hardware fault injection states (`ACTIVE` or `INACTIVE`). Toggling network to inactive automatically triggers store-and-forward queue reconciliation.
- **Request Body**: `{"active": true}`
- **Status Codes**: 200 (Success)

---

#### `GET /api/notifications`
- **Category**: Notification Feed
- **Purpose**: Fetches the 50 most recent operational notifications.
- **Status Codes**: 200 (Success)

---

#### `POST /api/feedback`, `GET /api/feedback/summary`
- **Category**: Feedback-related
- **Purpose**: Ingests and aggregates 5-question Likert survey parent validation feedback.
- **Status Codes**: 200 (Success)

---

#### `GET /api/reports/data`, `GET /api/experiment/results`
- **Category**: Report-related / Analytics
- **Purpose**: Serves computed statistical metrics (MAE, RMSE, enquiry call reduction percentage, delay cause distribution).
- **Status Codes**: 200 (Success), 400 (Dataset not yet generated)

---

## 10. Database Schema

The system uses an embedded SQLite database (`database/school_bus.db`) defined in `database/schema.sql`. It contains **13 structured tables**:

### Entity Relationship Diagram
```
  [routes]
     │
     ├── 1:N ──> [stops]
     │              │
     │              ├── 1:N ──> [students]
     │              │              │
     │              │              ├── 1:1 ──> [attendance]
     │              │              └── 1:1 ──> [customer_commitments]
     │              │
     └── 1:N ──> [buses]
                    │
                    ├── 1:N ──> [eta_history]
                    ├── 1:N ──> [notifications]
                    ├── 1:N ──> [eta_plan_audit]
                    └── 1:N ──> [processed_telemetry]

  Standalone / Control Tables:
  [failures], [feedback], [experiment_results]
```

---

### Table 1: `routes`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `route_id` | TEXT | Unique route identifier (e.g. `'Route 1'`) | Yes | PRIMARY KEY |
| `route_name` | TEXT | Descriptive name of the route corridor | Yes | None |
| `student_count`| INTEGER | Total enrolled students assigned to route | No | Default `0` |

---

### Table 2: `stops`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `stop_id` | TEXT | Unique stop identifier (e.g. `'Stop_A'`) | Yes | PRIMARY KEY |
| `route_id` | TEXT | Associated route identifier | Yes | FOREIGN KEY $\rightarrow$ `routes(route_id)` |
| `stop_name` | TEXT | Human-readable stop landmark | Yes | None |
| `latitude` | REAL | Geographic latitude coordinate | Yes | None |
| `longitude` | REAL | Geographic longitude coordinate | Yes | None |
| `planned_arrival_time` | TEXT | Static scheduled arrival (`'08:00 AM'`) | Yes | None |
| `sequence` | INTEGER | Stop visitation order along the route | Yes | None |

---

### Table 3: `students`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `student_id` | TEXT | Unique student registration ID (`'S101'`) | Yes | PRIMARY KEY |
| `student_name`| TEXT | Full name of the student | Yes | None |
| `route_id` | TEXT | Assigned bus route | Yes | FOREIGN KEY $\rightarrow$ `routes(route_id)` |
| `stop_id` | TEXT | Assigned boarding stop | Yes | FOREIGN KEY $\rightarrow$ `stops(stop_id)` |
| `committed_pickup_time` | TEXT | Service commitment target time | Yes | None |

---

### Table 4: `buses`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `bus_id` | TEXT | Unique vehicle identifier (`'101'`) | Yes | PRIMARY KEY |
| `registration_number` | TEXT | License plate / fleet ID (`'SB-101'`) | Yes | None |
| `driver_name` | TEXT | Assigned driver name | Yes | None |
| `route_id` | TEXT | Currently assigned route | Yes | FOREIGN KEY $\rightarrow$ `routes(route_id)` |
| `current_latitude` | REAL | Last confirmed latitude coordinate | Yes | None |
| `current_longitude`| REAL | Last confirmed longitude coordinate | Yes | None |
| `speed` | REAL | Last reported vehicle speed (km/h) | Yes | None |
| `status` | TEXT | `'ON_ROUTE'`, `'DWELLING'`, `'COMPLETED'`, `'INACTIVE'` | Yes | None |

---

### Table 5: `attendance`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `student_id` | TEXT | Student registration identifier | Yes | PRIMARY KEY, FK $\rightarrow$ `students` |
| `status` | TEXT | Daily attendance status (`'Present'`, `'Absent'`) | Yes | None |

---

### Table 6: `eta_history`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | INTEGER | Auto-incrementing update identifier | Yes | PRIMARY KEY AUTOINCREMENT |
| `timestamp` | TEXT | Clock time of update (`'08:05 AM'`) | Yes | None |
| `bus_id` | TEXT | Vehicle identifier | Yes | None |
| `route_id` | TEXT | Route identifier | Yes | None |
| `previous_eta`| TEXT | Prior ETA before recalculation | No | None |
| `new_eta` | TEXT | Newly computed arrival time | Yes | None |
| `delay_minutes`| REAL | Net delta change in minutes | No | Default `0` |
| `reason` | TEXT | Natural language causal explanation | Yes | None |
| `traffic_level`| TEXT | Congestion level (`'LOW'`, `'MEDIUM'`, `'HIGH'`) | Yes | None |
| `student_count`| INTEGER | Confirmed present students on remaining stops | No | Default `0` |
| `dwell_time` | REAL | Projected dwell time in minutes | No | Default `0` |
| `gps_status` | TEXT | `'ONLINE'` or `'OFFLINE'` | Yes | None |
| `network_status` | TEXT | `'ONLINE'` or `'OFFLINE'` | Yes | None |
| `notification_sent` | INTEGER | Flag: `1` if alert dispatched, `0` otherwise | No | Default `0` |
| `source` | TEXT | Update origin (`'AUTO'`, `'MANUAL'`, `'FALLBACK'`) | Yes | None |

---

### Table 7: `notifications`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | INTEGER | Unique notification identifier | Yes | PRIMARY KEY AUTOINCREMENT |
| `timestamp` | TEXT | Dispatch timestamp | Yes | None |
| `bus_id` | TEXT | Target vehicle or `'ALL'` | Yes | None |
| `message` | TEXT | Full notification message body | Yes | None |
| `type` | TEXT | `'INFO'`, `'WARNING'`, `'ALERT'`, `'CRITICAL'` | Yes | None |

---

### Table 8: `failures`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `case_name` | TEXT | `'gps'`, `'network'`, `'traffic'`, `'sensor'` | Yes | PRIMARY KEY |
| `status` | TEXT | `'ACTIVE'` or `'INACTIVE'` | Yes | Default `'INACTIVE'` |
| `description`| TEXT | Explanatory note of failure mode | No | None |

---

### Table 9: `feedback`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | INTEGER | Unique survey response ID | Yes | PRIMARY KEY AUTOINCREMENT |
| `timestamp` | TEXT | Submission timestamp | Yes | None |
| `q1` to `q5` | INTEGER | 5-point Likert ratings (1=Poor, 5=Excellent) | Yes | None |
| `comments` | TEXT | Optional free-form qualitative comments | No | None |

---

### Table 10: `customer_commitments`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `commitment_id`| INTEGER | Unique commitment record identifier | Yes | PRIMARY KEY AUTOINCREMENT |
| `student_id` | TEXT | Student registration identifier | Yes | FOREIGN KEY $\rightarrow$ `students` |
| `stop_id` | TEXT | Stop identifier | Yes | FOREIGN KEY $\rightarrow$ `stops` |
| `target_pickup_time` | TEXT | Committed pickup time (`'08:00 AM'`) | Yes | None |
| `window_minutes` | INTEGER | Permissible buffer window ($\pm 5$ min) | No | Default `5` |
| `status` | TEXT | Commitment status (`'MET'`, `'AT_RISK'`, `'BREACHED'`) | No | Default `'MET'` |

---

### Table 11: `experiment_results`
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `metric_name` | TEXT | Metric name (e.g. `'MAE'`, `'Status Enquiries'`) | Yes | PRIMARY KEY |
| `baseline_value` | REAL | Static schedule baseline value | Yes | None |
| `proposed_value` | REAL | Dynamic attendance-aware system value | Yes | None |

---

### Table 12: `eta_plan_audit` (Immutable Audit Ledger)
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `id` | INTEGER | Unique audit sequence identifier | Yes | PRIMARY KEY AUTOINCREMENT |
| `bus_id` | TEXT | Vehicle identifier | Yes | None |
| `route_id` | TEXT | Route identifier | No | None |
| `trip_id` | TEXT | Trip run identifier | No | None |
| `stop_id` | TEXT | Target stop ID | No | None |
| `event_type` | TEXT | Category code (`'TELEMETRY_UPDATE'`, `'TRAFFIC_UPDATE'`) | Yes | None |
| `trigger_factor`| TEXT | Causal trigger code (`'GPS_TELEMETRY'`, `'TRAFFIC_DELAY'`) | Yes | None |
| `trigger_details`| TEXT | Detailed context string | No | None |
| `previous_eta` | TEXT | Prior ETA string | No | None |
| `new_eta` | TEXT | Newly computed ETA | No | None |
| `previous_delay_minutes` | REAL | Delay before recalculation | No | None |
| `new_delay_minutes` | REAL | Delay after recalculation | No | None |
| `previous_plan` | TEXT | Serialized JSON prior route plan | No | None |
| `new_plan` | TEXT | Serialized JSON new route plan | No | None |
| `explanation` | TEXT | Natural language explanation | No | None |
| `telemetry_snapshot` | TEXT | Serialized JSON raw telemetry readings | No | None |
| `created_at` | TEXT | Creation timestamp (`'YYYY-MM-DD HH:MM:SS'`) | Yes | None |
| `created_by` | TEXT | Subsystem or actor (`'telemetry_service'`, `'dispatcher'`) | No | Default `'system'` |

---

### Table 13: `processed_telemetry` (Deduplication Ledger)
| Column | Type | Description | Required | Key |
| :--- | :--- | :--- | :--- | :--- |
| `event_id` | TEXT | Unique UUID string for telemetry packet | Yes | PRIMARY KEY |
| `bus_id` | TEXT | Vehicle identifier | Yes | None |
| `route_id` | TEXT | Route identifier | No | None |
| `trip_id` | TEXT | Trip run identifier | No | None |
| `timestamp` | TEXT | Telemetry packet timestamp | Yes | None |
| `latitude` | REAL | Reported latitude | Yes | None |
| `longitude` | REAL | Reported longitude | Yes | None |
| `speed` | REAL | Reported speed (km/h) | Yes | None |
| `received_at` | TEXT | Ingestion timestamp on server | Yes | None |

---

## 11. Unit Testing

The project maintains an automated test suite executed via `pytest`.

### Running All Tests
```bash
python -m pytest
```

### Verbose Mode with Module Breakdown
```bash
python -m pytest -v
```

### Test Suite Summary (67 Tests Active)
- `tests/test_api_integration.py` (15 tests): Verifies all 27 REST routes, HTTP methods, status codes, and JSON response envelopes.
- `tests/test_audit.py` (3 tests): Tests online/offline notification logging and store-and-forward queue flushing.
- `tests/test_baseline.py` (3 tests): Verifies static timetable calculations and immunity to live attendance fluctuations.
- `tests/test_edge_cases.py` (19 tests): Tests boundary inputs, zero attendance, 50-student dwell spikes, malformed times, and API 400 validations.
- `tests/test_eta.py` (7 tests): Tests Haversine formula, dwell time arithmetic, traffic delays, and meaningful change classification.
- `tests/test_eta_explanation.py` (8 tests): Tests causal factor attribution, status classification (`ON_TIME`, `DELAYED`, `EARLY`), and mandatory fallbacks.
- `tests/test_eta_plan_audit.py` (4 tests): Tests schema column validation, append-only timeline preservation, and query filtering.
- `tests/test_failures.py` (4 tests): Tests GPS, network, traffic, and sensor failure toggling and fallback values.
- `tests/test_store_and_forward.py` (4 tests): Tests deduplication ledger, batch synchronization, and duplicate packet rejection.

For comprehensive details on test IDs, expected vs. actual results, and edge case coverage, refer to [documentation/UNIT_TESTING.md](documentation/UNIT_TESTING.md).

---

## 12. Error Handling

Error boundaries are strictly separated across seven architectural layers:
1. **Frontend**: Graceful toast warnings, map pin freezing, client-side offline buffering.
2. **API Routing**: HTTP 400/404/500 code discipline with sanitized JSON error envelopes.
3. **ETA Engine**: Deterministic fallbacks (30 km/h default speed, 08:00 AM default time, base 30s dwell).
4. **Database**: 10-second connection timeout, `INSERT OR IGNORE` deduplication, atomic rollbacks.
5. **Simulation**: Boundary clamps at terminal stops, corrupted state recovery.
6. **Telemetry Ingestion**: Primary key deduplication ledger preventing double-processing.
7. **Offline Sync**: Store-and-forward edge queue caching events during cellular drops.

### Database Behavior Under Failure Conditions
- **Connection Failure**: Caught during `init_db()` or route execution; returns HTTP 500 without leaking file paths.
- **Query Failure**: Parameterized SQL prevents syntax corruption; uncaught query errors trigger transaction abort.
- **Invalid Data Insert**: Type mismatches and invalid enums are caught by API validation guards before SQL execution.
- **Duplicate Record**: `processed_telemetry` uses `INSERT OR IGNORE` to safely discard duplicate telemetry UUIDs without throwing exceptions.
- **Missing Required Value**: API guards reject missing fields with HTTP 400 Bad Request.
- **Database Locked (`BUSY`)**: Mitigated by `sqlite3.connect(..., timeout=10.0)` which automatically waits up to 10 seconds for concurrent write locks to release.
- **Transaction Failure**: Uncommitted multi-statement transactions roll back when connection closes.

For complete fault tree analysis and error boundary details, refer to [documentation/ERROR_HANDLING.md](documentation/ERROR_HANDLING.md).

---

## 13. Simulation

The simulation subsystem allows complete operational evaluation without physical vehicles:
- **Simulation Clock**: Starts at $07:58\text{ AM}$ and advances in $1$-minute discrete ticks (`POST /api/simulation/tick`).
- **Fleet Tracking**: Controls BUS-101 (Route 1), BUS-102 (Route 2), and BUS-103 (Route 3).
- **Stop Transitions**: Simulates motion between stops, stop arrival detection, passenger boarding countdowns, and terminal school arrival.
- **Interactive Toggles**: Dispatchers can toggle traffic conditions (`LOW`, `MEDIUM`, `HIGH`) or trigger hardware failures from the UI.
- **Automated 7-Step Demo Walkthrough**:
  1. *Normal Bus Departure* ($07:58\text{ AM}$)
  2. *Variable Attendance Delay* (Boarding dwell scales at Stop A)
  3. *Traffic Delay Injection* (Route 1 traffic switches to HIGH)
  4. *GPS Failure Injection* (Bus pins to last known location; fallback active)
  5. *Network Drop & Store-and-Forward* (Cellular disconnect; events buffer in memory)
  6. *Network Restoration & Queue Sync* (Cellular reconnects; buffered events flush to SQLite)
  7. *Audit Trail Inspection* (Navigates to ETA History view to inspect immutable log)

---

## 14. Experiment Evaluation

To validate the proposed dynamic system against traditional static schedules, an empirical benchmark across **550 simulated bus trips** was generated into `data/eta_experiment.csv`.

Run the evaluation script:
```bash
python experiments/run_experiment.py
```

### Empirical Results (550 Simulated Trips)

| Metric | Baseline System (Static Schedule) | Proposed Dynamic System | Empirical Improvement |
| :--- | :--- | :--- | :--- |
| **MAE (Mean Absolute Error)** | **6.67 minutes** | **2.19 minutes** | **67.2% reduction in prediction error** |
| **RMSE (Root Mean Squared Error)** | **7.36 minutes** | **2.66 minutes** | **63.9% reduction in prediction error** |
| **ETA Updates Dispatched** | 0 updates | 474 updates | Continuous proactive parent updates |
| **Customer Status Enquiries** | **3,393 calls** | **355 calls** | **89.5% reduction in administrative calls** |

> **Label**: *SIMULATED EXPERIMENT RESULTS*

---

## 15. Deployment

The application is structured for turnkey local deployment or cloud hosting on platforms like **Render**, **Railway**, or **Heroku**.

### Gunicorn Production Execution
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python database/seed.py
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
```

---

## 16. Troubleshooting

### 1. Database Locked Error (`sqlite3.OperationalError: database is locked`)
- **Cause**: High-frequency concurrent simulation ticks while inspecting large queries.
- **Solution**: Connections are configured with `timeout=10.0`. If persisting, ensure previous python instances are terminated.

### 2. Missing Dataset Error (`Dataset not generated`)
- **Cause**: Navigating to `/reports` before seeding data.
- **Solution**: Run `python database/seed.py` or `python experiments/generate_experiment_data.py`.

### 3. Port 5000 Already in Use
- **Windows**:
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process
  ```
- **macOS/Linux**:
  ```bash
  lsof -ti:5000 | xargs kill -9
  ```

---

## 17. Future Improvements

1. **Write-Ahead Logging (WAL)**: Enable `PRAGMA journal_mode=WAL;` in SQLite to support concurrent non-blocking reads during active telemetry writes.
2. **OpenStreetMap Routing Machine (OSRM)**: Integrate open-source road network routing to replace spherical Haversine distances with exact street-turn paths.
3. **Native Mobile Push (WebPush / FCM)**: Add Progressive Web App (PWA) push notifications for real-time mobile delivery to parent smartphones.
4. **RFID / NFC Card Tap Emulation**: Integrate badge scanning hardware simulation for automated, contact-free passenger boarding verification.
5. **Continuous Integration (CI)**: Deploy GitHub Actions workflow to run the 67-test suite automatically across Python 3.10 through 3.14.
