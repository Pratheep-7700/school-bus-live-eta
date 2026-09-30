# Unit Testing & Quality Assurance Documentation

**Project Title:** Live ETA Communication Service for School-Bus Network Serving Students with Variable Attendance  
**Repository:** `school_bus_eta`  
**Test Runner:** `pytest` / `unittest`  
**Status:** 67 Automated Tests Active & Passing  

---

## 1. Testing Objective

The primary objective of the testing strategy for the **Live ETA Communication Service** is to guarantee safety, operational transparency, algorithmic accuracy, and fault tolerance across a school transit network. 

Because school bus transportation directly affects student safety, parent peace of mind, and school district logistics, software failures carry high operational costs. Key reasons why comprehensive testing is critical for this system include:

1. **Safety-Critical Timing**: Inaccurate ETAs cause students to wait outside during extreme weather or arrive late for classes. The dynamic model must be deterministically verifiable under all route configurations.
2. **Variable Boarding Dynamics**: Dwell time fluctuates with daily student absenteeism ($30\text{s base} + 20\text{s/student}$). The calculation engine must never return negative dwell times, divide by zero, or overestimate delays when stops are skipped.
3. **Resilience in Hostile Environments**: School buses operate in cellular dead zones, urban canyons (GPS signal dropouts), and with aging vehicle sensors. Testing must prove that hardware dropouts degrade gracefully into calibrated fallbacks rather than crashing the system.
4. **Auditability & Regulatory Trust**: Every ETA alteration must be logged in an append-only ledger (`eta_plan_audit` and `eta_history`). Automated tests verify that audit records are strictly immutable and captures full telemetry snapshots.
5. **Prevention of Alert Fatigue**: Notifications are gated by a $\ge 2$-minute meaningful change filter. Testing ensures parents are alerted to genuine delays without spamming them with trivial sub-minute fluctuations.

---

## 2. Testing Levels

The testing architecture spans five conceptual tiers, from low-level arithmetic functions to complete end-to-end simulation lifecycles:

```
+-------------------------------------------------------------+
|               5. End-to-End (E2E) Testing                   |
|   (Simulated 7-step scenario, browser state validation)     |
+-------------------------------------------------------------+
|               4. Failure & Fallback Testing                 |
|   (GPS loss, network partition, sensor discrepancy)         |
+-------------------------------------------------------------+
|               3. REST API & Integration Testing             |
|   (Flask test client, HTTP routes, database transactions)   |
+-------------------------------------------------------------+
|               2. Subsystem Integration Testing              |
|   (Store-and-forward queue sync, deduplication ledger)      |
+-------------------------------------------------------------+
|               1. Unit Testing (Deterministic Core)          |
|   (Haversine math, dwell formulas, time conversions)        |
+-------------------------------------------------------------+
```

### Current Implementation Status

| Testing Level | Scope | Current Status | Verification Tool |
| :--- | :--- | :--- | :--- |
| **Unit Testing** | Math, time parsing, dwell formulas, factor ranking | **Fully Implemented** | `pytest` (`test_eta.py`, `test_baseline.py`, `test_edge_cases.py`, `test_eta_explanation.py`) |
| **Integration Testing**| DB writes, deduplication, store-and-forward sync | **Fully Implemented** | `pytest` (`test_audit.py`, `test_store_and_forward.py`, `test_eta_plan_audit.py`) |
| **API Testing** | Flask HTTP endpoints, status codes, payload validation | **Fully Implemented** | `pytest` (`test_api_integration.py`, `test_edge_cases.py`) |
| **Failure/Fallback** | Hardware outage injection, fallback speed/traffic | **Fully Implemented** | `pytest` (`test_failures.py`, `test_edge_cases.py`) |
| **End-to-End (E2E)** | Full morning route simulation with browser UI | **Partially Implemented** | Interactive 7-step simulation sequence (`static/js/simulation.js`); automated browser headless E2E is slated for future CI. |

---

## 3. Unit Test Coverage by Module

The table below catalogs project modules, tested functions, inputs, expected outputs, and handled failure modes:

| Module | Functionality Tested | Input | Expected Output | Failure / Boundary Case |
| :--- | :--- | :--- | :--- | :--- |
| `eta_engine.eta_calculator` | `haversine_distance` | Lat/Lon coordinate pairs | Great-circle distance in km ($\approx 1.10$ km for SF test points) | Coordinates identical $\rightarrow$ returns `0.0` km |
| `eta_engine.eta_calculator` | `str_to_minutes` | `"08:00 AM"`, `"12:30 PM"` | Integer minutes from midnight (`480`, `750`) | Malformed string $\rightarrow$ degrades to default `480` (08:00 AM) |
| `eta_engine.eta_calculator` | `minutes_to_str` | Integer minutes `480`, `750`, `1445` | Formatted string `"08:00 AM"`, `"12:30 PM"`, `"12:05 AM"` | Overflow $> 1440 \rightarrow$ wraps cleanly around midnight boundary |
| `eta_engine.eta_calculator` | `calculate_dwell_time` | `student_count = 0`, `3`, `5` | Dwell duration in seconds: `30`, `90`, `130` | `student_count <= 0` or `None` $\rightarrow$ returns minimum base `30`s |
| `eta_engine.eta_calculator` | `get_traffic_delay_minutes` | `"LOW"`, `"MEDIUM"`, `"HIGH"` | Integer delay minutes: `0`, `3`, `7` | Unrecognized string or `None` $\rightarrow$ returns `0` min |
| `eta_engine.eta_calculator` | `get_proposed_eta` | `bus_id = '101'`, `current_time = '08:00 AM'` | Mapping of remaining `stop_id -> ETA` string | Inactive bus $\rightarrow$ returns `({}, {})` |
| `eta_engine.baseline` | `get_baseline_eta` | `route_id = 'Route 1'` | Static planned schedule mapping for all route stops | Route has no stops $\rightarrow$ returns `{}` |
| `eta_engine.explanation` | `explain_eta_difference` | Planned `"08:00 AM"`, Proposed `"08:08 AM"`, Traffic `"HIGH"` | Factor dict with `'Traffic': 7.0` and summary string | Zero delay $\rightarrow$ `'On time (no delay factors)'` |
| `eta_engine.fallback` | `is_failure_active` | `case_name = 'gps'` | Boolean status (`True` if active, `False` if inactive) | Case missing in DB $\rightarrow$ returns `False` |
| `eta_engine.fallback` | `get_fallback_gps` | `bus_id = '101'` | Last known `(latitude, longitude)` tuple | GPS failure inactive $\rightarrow$ returns `None` |
| `eta_engine.fallback` | `get_fallback_traffic` | `route_id = 'Route 1'` | Fallback traffic string `'MEDIUM'` | Traffic failure inactive $\rightarrow$ returns `None` |
| `eta_engine.fallback` | `get_fallback_speed` | `bus_id = '101'` | Fallback transit speed `30.0` km/h | Sensor failure inactive $\rightarrow$ returns `None` |
| `services.eta_explanation_service` | `generate_explanation` | Sched `"08:40 AM"`, Pred `"08:45 AM"`, boarding `195s` | Dict with `status: 'DELAYED'`, `primary_reason: 'HIGH_BOARDING_TIME'` | Unresolvable delay $\rightarrow$ returns `primary_reason: 'UNKNOWN_CAUSE'` |
| `database.database` | `insert_eta_plan_audit` | Audit params with JSON snapshot | Auto-incremented primary key `id` | Connection is closed safely even if error occurs |
| `database.database` | `query_eta_plan_audit` | Filters: `bus_id`, `route_id`, `trigger_factor` | Chronological list of matching audit rows | Filter `'all'` $\rightarrow$ returns unfiltered records |
| `database.database` | `is_telemetry_processed` | `event_id` string | `True` if present in ledger, `False` otherwise | `event_id = None` $\rightarrow$ returns `False` |
| `database.database` | `record_processed_telemetry` | `event_id`, vehicle telemetry | Commits UUID to deduplication ledger | Duplicate UUID $\rightarrow$ `INSERT OR IGNORE` suppresses error |
| `simulator.simulation` | `log_notification` | State, notification message, severity | Writes to SQLite (online) or buffers in queue (offline) | Offline mode $\rightarrow$ buffers in memory without DB lock |
| `simulator.simulation` | `log_audit_history` | State, audit fields, failure flags | Writes to SQLite (online) or buffers in queue (offline) | Offline mode $\rightarrow$ appends to queue without losing fields |
| `simulator.simulation` | `synchronize_network_queue`| State with buffered events | Flushes queue to SQLite and returns count | Empty queue $\rightarrow$ returns `0` without write operations |
| `app.py` | `POST /api/attendance` | `{"student_id": "S101", "status": "Absent"}` | HTTP 200 `{"success": true}` | Invalid status `"Late"` $\rightarrow$ HTTP 400 |
| `app.py` | `POST /api/traffic` | `{"route_id": "Route 1", "traffic_level": "HIGH"}`| HTTP 200 `{"success": true}` | Invalid level `"EXTREME"` $\rightarrow$ HTTP 400 |
| `app.py` | `POST /api/manual-eta` | `{"bus_id": "101", "manual_eta": "08:15 AM", ...}`| HTTP 200 `{"success": true}` | Missing `next_stop_id` $\rightarrow$ HTTP 400 |
| `app.py` | `POST /api/telemetry` | GPS coordinates and `event_id` | HTTP 200 with new ETA and audit record | Missing `bus_id` $\rightarrow$ HTTP 400 with error JSON |
| `app.py` | `POST /api/telemetry/sync` | Batch array of buffered records | HTTP 200 with processed and duplicate counts | Duplicate batch $\rightarrow$ increments duplicate count |

---

## 4. Test Cases

Below is the verified test catalog corresponding to all test suites executed in the test runner:

### Core ETA Engine & Time Arithmetic (`test_eta.py`)
- **UT-TIME-001**: Verify standard 12-hour morning and afternoon time conversion to integer minutes.  
  *Input:* `"08:00 AM"`, `"12:00 AM"`, `"12:30 PM"`, `"08:15 PM"`  
  *Expected:* `480`, `0`, `750`, `1215`  
  *Actual Result:* Passed (Executed in `test_eta.py`)  
  *Status:* **Passed**
- **UT-TIME-002**: Verify minutes conversion back to formatted 12-hour string with midnight boundary wraparound.  
  *Input:* `480`, `0`, `750`, `1215`, `1445`  
  *Expected:* `"08:00 AM"`, `"12:00 AM"`, `"12:30 PM"`, `"08:15 PM"`, `"12:05 AM"`  
  *Actual Result:* Passed (Executed in `test_eta.py`)  
  *Status:* **Passed**
- **UT-DWELL-001**: Verify variable student attendance dwell time formula ($30\text{s base} + 20\text{s/student}$).  
  *Input:* `0`, `3`, `5` students  
  *Expected:* `30`, `90`, `130` seconds  
  *Actual Result:* Passed (Executed in `test_eta.py`)  
  *Status:* **Passed**
- **UT-DIST-001**: Verify Haversine spherical distance calculation between SF road coordinates.  
  *Input:* $(37.7949, -122.4394)$ and $(37.7889, -122.4294)$  
  *Expected:* $\approx 1.10 \pm 0.1$ km  
  *Actual Result:* Passed (Executed in `test_eta.py`)  
  *Status:* **Passed**
- **UT-TRAF-001**: Verify categorical traffic delays mapped to integer minutes.  
  *Input:* `"LOW"`, `"MEDIUM"`, `"HIGH"`, `"UNKNOWN"`  
  *Expected:* `0`, `3`, `7`, `0` minutes  
  *Actual Result:* Passed (Executed in `test_eta.py`)  
  *Status:* **Passed**
- **UT-THRESH-001**: Verify notification threshold classification ($< 2$m none, $\ge 2$m warning, $\ge 5$m critical).  
  *Input:* Delays of `1.0`, `1.9`, `2.0`, `4.5`, `5.0`, `7.0` minutes  
  *Expected:* `'NONE'`, `'NONE'`, `'WARNING'`, `'WARNING'`, `'CRITICAL'`, `'CRITICAL'`  
  *Actual Result:* Passed (Executed in `test_eta.py`)  
  *Status:* **Passed**

### Static Schedule Baseline (`test_baseline.py`)
- **UT-BASE-001**: Verify static timetable lookup for Route 1 stops.  
  *Input:* `'Route 1'`  
  *Expected:* 4 stops with planned timetable (`'Stop_A': '08:00 AM'`, `'School_1': '08:30 AM'`)  
  *Actual Result:* Passed (Executed in `test_baseline.py`)  
  *Status:* **Passed**
- **UT-BASE-002**: Verify baseline ignores live attendance and traffic alterations.  
  *Input:* Route with attendance modified and traffic set to HIGH  
  *Expected:* Baseline ETAs remain strictly equal to static timetable  
  *Actual Result:* Passed (Executed in `test_baseline.py`)  
  *Status:* **Passed**

### Natural Language Explanations (`test_eta_explanation.py`)
- **UT-EXP-001**: Verify ON_TIME status classification when delay $\le 1.0$ minute.  
  *Input:* Sched `"08:40 AM"`, Pred `"08:40 AM"` and `"08:41 AM"`  
  *Expected:* Status `'ON_TIME'`, reason `'ON_SCHEDULE'`, factors empty  
  *Actual Result:* Passed (Executed in `test_eta_explanation.py`)  
  *Status:* **Passed**
- **UT-EXP-002**: Verify EARLY status classification when running ahead of schedule by $> 1.0$ minute.  
  *Input:* Sched `"08:40 AM"`, Pred `"08:37 AM"`  
  *Expected:* Status `'EARLY'`, reason `'AHEAD_OF_SCHEDULE'`  
  *Actual Result:* Passed (Executed in `test_eta_explanation.py`)  
  *Status:* **Passed**
- **UT-EXP-003**: Verify HIGH_BOARDING_TIME identification when boarding time exceeds average.  
  *Input:* Previous stop dwell $195$s vs $45$s average  
  *Expected:* Reason `'HIGH_BOARDING_TIME'`, explanation mentions higher boarding time  
  *Actual Result:* Passed (Executed in `test_eta_explanation.py`)  
  *Status:* **Passed**
- **UT-EXP-004**: Verify dominant TRAFFIC_DELAY identification and impact formatting.  
  *Input:* Traffic delay $8.0$ minutes  
  *Expected:* Reason `'TRAFFIC_DELAY'`, impact $8.0$m  
  *Actual Result:* Passed (Executed in `test_eta_explanation.py`)  
  *Status:* **Passed**
- **UT-EXP-005**: Verify multi-factor combination mentioning dominant and secondary causes.  
  *Input:* Boarding impact $3.4$m, traffic delay $2.0$m  
  *Expected:* Primary boarding time, secondary traffic mentioned in narrative  
  *Actual Result:* Passed (Executed in `test_eta_explanation.py`)  
  *Status:* **Passed**

### Immutable Audit Trail (`test_eta_plan_audit.py`)
- **UT-AUD-001**: Verify schema columns exist in `eta_plan_audit` table.  
  *Input:* PRAGMA table_info inspection  
  *Expected:* All 18 required columns present  
  *Actual Result:* Passed (Executed in `test_eta_plan_audit.py`)  
  *Status:* **Passed**
- **UT-AUD-002**: Verify append-only timeline (subsequent records do not overwrite prior records).  
  *Input:* Insert record 1 (ETA 08:40) then record 2 (ETA 08:45)  
  *Expected:* Record 1 retains ETA 08:40; record 2 has ETA 08:45 and new ID  
  *Actual Result:* Passed (Executed in `test_eta_plan_audit.py`)  
  *Status:* **Passed**
- **UT-AUD-003**: Verify query filtering by `bus_id`, `route_id`, and `trigger_factor`.  
  *Input:* Query with `trigger_factor='TEST_TRIGGER_SPECIAL'`  
  *Expected:* Returns only matching audit rows  
  *Actual Result:* Passed (Executed in `test_eta_plan_audit.py`)  
  *Status:* **Passed**

### Failure Modes & Degradation (`test_failures.py`)
- **UT-FAIL-001**: Verify failure flag activation and deactivation in SQLite.  
  *Input:* Toggle `'gps'` ACTIVE then INACTIVE  
  *Expected:* `is_failure_active('gps')` reflects state transitions  
  *Actual Result:* Passed (Executed in `test_failures.py`)  
  *Status:* **Passed**
- **UT-FAIL-002**: Verify GPS fallback returns last confirmed coordinates in SF bounds.  
  *Input:* Activate GPS failure for Bus 101  
  *Expected:* Latitude in $[37.5, 38.0]$, Longitude in $[-122.6, -122.3]$  
  *Actual Result:* Passed (Executed in `test_failures.py`)  
  *Status:* **Passed**
- **UT-FAIL-003**: Verify traffic feed failure triggers historical `'MEDIUM'` fallback.  
  *Input:* Activate traffic failure for Route 1  
  *Expected:* `get_fallback_traffic('Route 1') == 'MEDIUM'`  
  *Actual Result:* Passed (Executed in `test_failures.py`)  
  *Status:* **Passed**
- **UT-FAIL-004**: Verify speed sensor discrepancy triggers $30.0$ km/h fallback.  
  *Input:* Activate sensor failure for Bus 101  
  *Expected:* `get_fallback_speed('101') == 30.0`  
  *Actual Result:* Passed (Executed in `test_failures.py`)  
  *Status:* **Passed**

### Store-and-Forward Offline Queue (`test_store_and_forward.py` & `test_audit.py`)
- **UT-NET-001**: Verify notification directly written to SQLite when online.  
  *Input:* `log_notification` with `is_network_unavailable=False`  
  *Expected:* Record in `notifications` table, queue length 0  
  *Actual Result:* Passed (Executed in `test_audit.py`)  
  *Status:* **Passed**
- **UT-NET-002**: Verify notification queued in memory when offline.  
  *Input:* `log_notification` with `is_network_unavailable=True`  
  *Expected:* 0 rows in `notifications`, 1 item in `store_and_forward_queue`  
  *Actual Result:* Passed (Executed in `test_audit.py`)  
  *Status:* **Passed**
- **UT-NET-003**: Verify offline queue synchronization flushes events to SQLite.  
  *Input:* Call `synchronize_network_queue()` with 2 buffered items  
  *Expected:* Return value 2, SQLite tables populated, queue emptied  
  *Actual Result:* Passed (Executed in `test_audit.py`)  
  *Status:* **Passed**
- **UT-TEL-001**: Verify telemetry ingestion, dynamic ETA recalculation, and deduplication recording.  
  *Input:* `POST /api/telemetry` with UUID `event_id`  
  *Expected:* Status 200 `'SUCCESS'`, `is_telemetry_processed(event_id) == True`  
  *Actual Result:* Passed (Executed in `test_store_and_forward.py`)  
  *Status:* **Passed**
- **UT-TEL-002**: Verify duplicate telemetry rejected with status `'DUPLICATE'`.  
  *Input:* Re-send same `event_id` payload  
  *Expected:* Status 200 with `'DUPLICATE'` message, no double-write  
  *Actual Result:* Passed (Executed in `test_store_and_forward.py`)  
  *Status:* **Passed**
- **UT-TEL-003**: Verify batch synchronization via `/api/telemetry/sync`.  
  *Input:* Batch of 2 items, followed by resend of same batch  
  *Expected:* First run: 2 processed; Second run: 2 duplicates  
  *Actual Result:* Passed (Executed in `test_store_and_forward.py`)  
  *Status:* **Passed**

### Boundary Conditions & Edge Cases (`test_edge_cases.py`)
- **UT-EDGE-001**: Dwell time with zero attendance yields 30s base. (*Passed*)
- **UT-EDGE-002**: Negative student count defaults to 30s base dwell. (*Passed*)
- **UT-EDGE-003**: High attendance (50 students) yields 1030s dwell without overflow. (*Passed*)
- **UT-EDGE-004**: Empty or unrecognized traffic string defaults to 0 min delay. (*Passed*)
- **UT-EDGE-005**: Case-insensitive traffic inputs (`"low"`, `"medium"`, `"High"`) parse correctly. (*Passed*)
- **UT-EDGE-006**: Inactive bus returns empty ETA dicts without exception. (*Passed*)
- **UT-EDGE-007**: Sensor failure active with zero speed returns 30.0 km/h fallback. (*Passed*)
- **UT-EDGE-008**: GPS fallback inactive returns `None`. (*Passed*)
- **UT-EDGE-009**: GPS fallback active returns valid SF coordinates. (*Passed*)
- **UT-EDGE-010**: Clock midnight boundary wraparound (`1440` min $\rightarrow$ `"12:00 AM"`). (*Passed*)
- **UT-EDGE-011**: Malformed time string degrades to `"08:00 AM"` (480) baseline. (*Passed*)
- **UT-EDGE-012**: Empty offline queue synchronization returns 0 without database error. (*Passed*)
- **UT-EDGE-013**: Telemetry deduplication prevents duplicate processing via `INSERT OR IGNORE`. (*Passed*)
- **UT-EDGE-014**: Attendance update with invalid status rejects with HTTP 400. (*Passed*)
- **UT-EDGE-015**: Attendance update missing student_id rejects with HTTP 400. (*Passed*)
- **UT-EDGE-016**: Traffic update with invalid level rejects with HTTP 400. (*Passed*)
- **UT-EDGE-017**: Manual ETA update missing required fields rejects with HTTP 400. (*Passed*)
- **UT-EDGE-018**: Telemetry update missing bus_id rejects with HTTP 400. (*Passed*)
- **UT-EDGE-019**: ETA query for invalid bus ID rejects with HTTP 400. (*Passed*)

---

## 5. Edge Cases & Boundary Handling

The system explicitly tests and guards against 14 specific edge conditions:

1. **Missing GPS Data**: If live GPS coordinates are null or stream times out, the system locks to the bus's last known database position (`get_fallback_gps`), marks GPS status as `OFFLINE`, and continues ETA calculation without throwing unhandled exceptions.
2. **Invalid GPS Coordinates**: Telemetry with out-of-range latitude/longitude coordinates is safely recorded in the raw snapshot while the vehicle's position is clamped to the route waypoints.
3. **Missing Attendance Record**: If attendance status has not yet been logged for a student, the system treats the student as present by default to ensure conservative arrival predictions.
4. **Zero Attendance at Stop**: When all assigned students are absent, dwell time drops to the 30-second minimum safety stop, correctly eliminating passenger embarkation delays.
5. **Unusually High Attendance**: If extra passengers board (e.g. 50 students on special field trips), dwell scales linearly ($30 + 50 \times 20 = 1030$ seconds) without integer overflow.
6. **Missing Traffic Feed**: If the traffic API is unreachable, the system falls back to historical `'MEDIUM'` congestion (+3 min) rather than assuming zero traffic.
7. **Invalid Traffic Value**: Inputs such as `"SEVERE"` or `""` safely fall back to 0-minute delay without causing string parsing crashes.
8. **Abnormal Sensor Reading**: If speedometer reports $\le 0$ km/h while bus state is `ON_ROUTE`, the sensor fallback substitutes $30.0$ km/h urban average speed.
9. **Network Outage**: When cellular transmission is down, notifications and audit updates are appended to `store_and_forward_queue`, allowing simulation ticks to continue seamlessly.
10. **Empty Offline Queue**: Calling queue synchronization when no offline events exist returns count `0` cleanly without SQL syntax or locking errors.
11. **Duplicate Offline Event**: Re-sending a telemetry batch with already-processed UUIDs results in immediate detection and status `'DUPLICATE'`, preventing double ETA updates.
12. **Synchronization Failure**: If network restoration sync encounters a transient database lock, events remain in the queue for subsequent tick retries.
13. **Invalid API Request**: API requests with malformed JSON, missing IDs, or out-of-bound enumerations are rejected with HTTP 400 and structured error responses.
14. **Database Connection Failure**: The database connection factory sets a 10-second busy timeout (`timeout=10.0`) to resolve concurrent SQLite read/write lock contention.

---

## 6. How to Run Tests

### Running the Entire Test Suite
Execute pytest from the project root:
```bash
python -m pytest
```

### Running with Verbose Output
```bash
python -m pytest -v
```

### Running Specific Test Modules
```bash
# Run ETA calculation tests only
python -m pytest tests/test_eta.py -v

# Run Edge Case boundary tests only
python -m pytest tests/test_edge_cases.py -v

# Run REST API integration tests only
python -m pytest tests/test_api_integration.py -v

# Run Store-and-Forward tests only
python -m pytest tests/test_store_and_forward.py -v
```

### Running via Standard Python `unittest`
```bash
python -m unittest discover tests
```

---

## 7. Test Folder Structure

```
tests/
├── test_api_integration.py    # 15 tests: Endpoints (/api/buses, /api/routes, simulation, failures)
├── test_audit.py              # 3 tests: Online/offline notification logging & store-and-forward sync
├── test_baseline.py           # 3 tests: Static timetable baseline calculation and immunity to live updates
├── test_edge_cases.py         # 19 tests: Boundary inputs, zero/high attendance, malformed times, API 400s
├── test_eta.py                # 7 tests: Haversine distance, str_to_minutes, dwell formula, traffic delays
├── test_eta_explanation.py    # 8 tests: Causal factor decomposition, status classification, fallbacks
├── test_eta_plan_audit.py     # 4 tests: Schema validation, append-only timeline, query filter endpoints
├── test_failures.py           # 4 tests: GPS, network, traffic, and sensor failure state fallbacks
└── test_store_and_forward.py  # 4 tests: Deduplication ledger, batch sync, duplicate rejection
```

---

## 8. Future Testing Improvements

To elevate testing maturity from student prototype to commercial production grade, the following enhancements are planned:

1. **Automated Coverage Measurement (`pytest-cov`)**: Integrate test coverage reporting to target $> 95\%$ statement and branch coverage across `eta_engine/` and `database/`.
2. **Continuous Integration (CI) Pipeline**: Configure GitHub Actions to execute the full test matrix on every pull request across Python 3.10, 3.11, 3.12, and 3.14.
3. **Automated Regression Testing**: Establish golden-master regression datasets of historical bus trips to verify that ETA algorithm optimizations do not increase baseline error metrics.
4. **Property-Based Testing (`hypothesis`)**: Implement fuzz testing with random GPS trajectories, randomized attendance lists, and corrupted telemetry payloads to uncover edge-case arithmetic bounds.
5. **Headless Browser UI Testing (Selenium / Playwright)**: Automate visual dashboard validation, Leaflet map bus marker movement verification, and failure toggle UI responsiveness.
