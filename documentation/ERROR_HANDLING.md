# Error Boundaries & Fault Tolerance Architecture

**Project Title:** Live ETA Communication Service for School-Bus Network Serving Students with Variable Attendance  
**Repository:** `school_bus_eta`  
**Architecture:** Multi-Tier Resilient Edge-to-Cloud System  

---

## 1. System Overview & Error Philosophy

The **Live ETA Communication Service** is designed around the principle of **Graceful Degradation Under Telemetry Loss**. In real-world school bus operations, hardware disruptions, cellular dead zones, sensor dropouts, and database lock contentions are expected daily occurrences rather than rare exceptions.

### Core Architectural Principles:
1. **No Fatal Silent Failures**: Failures are never hidden; they are classified, attributed, and tagged with operational status indicators (`ACTIVE`, `OFFLINE`, `FALLBACK`).
2. **Deterministic Fallbacks**: Every failure mode maps to a predefined, calibrated fallback estimate (e.g., historical traffic or dead-reckoning coordinates) to maintain continuous arrival predictions.
3. **Information Security & Sanitization**: Stack traces, database file paths, and internal exceptions are sanitized at the API layer. Clients receive structured JSON error payloads with actionable status codes.
4. **Append-Only Auditing**: Every fallback transition, manual override, and system error is preserved in the immutable SQLite audit ledger (`eta_plan_audit` and `eta_history`).
5. **Zero Data Loss via Store-and-Forward**: During connectivity dropouts, events are cached locally at the edge and synchronized when the network recovers.

---

## 2. Seven Error Boundaries

The application enforces strict separation of concerns across seven distinct system boundaries:

```
[1. Frontend (Browser / Leaflet UI)]
       │
       ▼ (HTTP / JSON REST)
[2. Flask API Routing Layer]
       │
       ▼ (Python In-Memory Calls)
[3. ETA Calculation Engine]
       │
       ▼ (SQL Queries & Transactions)
[4. Database Layer (SQLite)]
       ▲
       │ (State Management)
[5. Simulation Clock & Fleet Loop]
       ▲
       │ (Ingestion & Normalization)
[6. External / Telemetry Input Data]
       ▲
       │ (IndexedDB / In-Memory Queue)
[7. Network / Offline Store-and-Forward]
```

---

### Boundary 1: Frontend (Browser / Leaflet UI Layer)

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | Network request timeout, JavaScript runtime exception, invalid JSON response from server, missing Map tiles, geolocation permission denied. |
| **How is failure detected?** | JavaScript `fetch().catch()` promise rejections, HTTP status code checks (`if (!response.ok)`), null checks on GeoJSON data. |
| **What fallback is used?** | - Retains previous valid marker coordinates on Leaflet map.<br>- Displays user-friendly Bootstrap alert badge (e.g., `"Network Offline — Changes Queued"`).<br>- Falls back to local offline caching (client-side simulation queue). |
| **User Response** | Non-blocking toast notification or alert banner. Map remains interactive with last-known positions. |
| **Is the error logged?** | Yes, logged to browser `console.warn()` and recorded in client-side operational state. |
| **Does system continue operating?** | **Yes.** Dashboard continues polling or pauses gracefully until network reconnects. |

---

### Boundary 2: Flask API Layer (`app.py`)

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | Malformed JSON request bodies, missing required parameters (`bus_id`, `status`), out-of-bounds enumerations, unhandled route exceptions. |
| **How is failure detected?** | Explicit input validation guards (`if not student_id or status not in ['Present', 'Absent']`), `request.get_json()` safety checks, try/except blocks. |
| **What fallback is used?** | Rejection with standard HTTP error codes (HTTP 400 Bad Request, HTTP 404 Not Found) and descriptive JSON error payload. |
| **User Response** | Clean JSON: `{"error": "Invalid arguments"}` or `{"status": "ERROR", "error": "Missing bus_id"}`. Never raw HTML stack traces. |
| **Is the error logged?** | Yes, logged to server console via Python logging / stdout. |
| **Does system continue operating?** | **Yes.** The worker process handles subsequent requests normally without termination. |

---

### Boundary 3: ETA Calculation Engine (`eta_engine/`)

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | Negative speed readings, distance calculation with identical coordinates, division by zero, invalid time format strings, missing route stops. |
| **How is failure detected?** | Math domain checks, `math.atan2` guards in Haversine formula, time string split validation in `str_to_minutes`, stop sequence validation. |
| **What fallback is used?** | - If bus speed $\le 0$: defaults to standard urban bus transit speed ($30.0$ km/h).<br>- If time string invalid: degrades safely to $480$ minutes ($08:00\text{ AM}$).<br>- If student count $< 0$ or None: clamps to $0$ students ($30$s base dwell).<br>- If bus inactive: returns empty ETA dictionary `({}, {})`. |
| **User Response** | Valid, conservative arrival estimate based on fallback variables. Notification includes explanatory notice if fallback is applied. |
| **Is the error logged?** | Yes, recorded in `eta_plan_audit` with `trigger_factor='GPS_SIGNAL_LOSS'` or `'SENSOR_DISCREPANCY'`. |
| **Does system continue operating?** | **Yes.** ETA calculation completes and updates the route timeline. |

---

### Boundary 4: Database Layer (`database/`)

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | Concurrent table locking (`sqlite3.OperationalError: database is locked`), foreign key constraint violation, duplicate primary key insert, database file disk full. |
| **How is failure detected?** | Caught by SQLite client exceptions (`sqlite3.OperationalError`, `sqlite3.IntegrityError`). |
| **What fallback is used?** | - **Busy Timeout**: Database connections are initialized with `timeout=10.0` seconds to wait for lock release.<br>- **Deduplication**: `INSERT OR IGNORE INTO processed_telemetry` suppresses duplicate primary key errors.<br>- **Explicit Rollback**: Multi-statement operations commit only upon complete execution; rollbacks prevent partial writes.<br>- **Schema Migrations**: `init_db()` runs `CREATE TABLE IF NOT EXISTS` checks on startup. |
| **User Response** | Returns HTTP 500 or HTTP 400 with sanitized message `{"error": "Database operation failed"}`. |
| **Is the error logged?** | Yes, logged to console with error context. |
| **Does system continue operating?** | **Yes.** Subsequent queries establish new connections via `get_db_connection()`. |

---

### Boundary 5: Simulation Layer (`simulator/`)

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | Bus coordinates advancing past terminal stop, missing route waypoints in database, negative dwell time countdowns, corrupted `simulation_state.json`. |
| **How is failure detected?** | Bounds checks on `current_stop_index >= len(stops)`, dwell timer floor checks (`max(0, dwell_remaining_secs)`), JSON parse try/except in `load_sim_state()`. |
| **What fallback is used?** | - If bus reaches final stop: status switches to `'COMPLETED'`, coordinates freeze at school campus, speed set to 0.<br>- If state file corrupted or missing: triggers `reset_simulation()` to restore initial conditions ($07:58\text{ AM}$). |
| **User Response** | Simulator continues advancing clock; vehicles display terminal arrival state without disappearing. |
| **Is the error logged?** | Yes, simulation transitions generate notifications in the notifications feed. |
| **Does system continue operating?** | **Yes.** Simulation continues running clock ticks uninterrupted. |

---

### Boundary 6: External / Telemetry Input Data Layer (`api/telemetry`)

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | GPS coordinates outside geographic territory, duplicate telemetry packet delivery, erratic high speed readings ($> 120$ km/h), missing route identifiers. |
| **How is failure detected?** | UUID lookup in `is_telemetry_processed(event_id)`, route ID query in buses table if omitted from payload. |
| **What fallback is used?** | - Duplicate event: Returns status `'DUPLICATE'` immediately, skipping redundant calculation and audit insertion.<br>- Missing route ID: Fetches assigned `route_id` from the vehicle registry in SQLite. |
| **User Response** | JSON response: `{"status": "DUPLICATE", "message": "Telemetry event already processed. Skipped duplicate."}`. |
| **Is the error logged?** | Yes, duplicate occurrences are logged without polluting the primary audit trail. |
| **Does system continue operating?** | **Yes.** Telemetry ingestion pipeline remains open for incoming packets. |

---

### Boundary 7: Network / Offline Store-and-Forward Synchronization

| Dimension | Details |
| :--- | :--- |
| **What can fail?** | Cellular disconnect during transit, server unreachable during batch synchronization, partial batch failure, duplicate batch retries. |
| **How is failure detected?** | Failure flag `is_failure_active('network')` during simulation, HTTP connection errors on client. |
| **What fallback is used?** | - **Store-and-Forward**: Events are held in `state['store_and_forward_queue']` during offline period.<br>- **Bulk Reconciliation**: On network recovery, `synchronize_network_queue()` iterates over buffered items, committing them in timestamp order.<br>- **Deduplication Safeguard**: Batch sync endpoint `/api/telemetry/sync` counts duplicates and processed items separately. |
| **User Response** | User sees offline indicator; upon reconnection, notification displays count of synchronized events (e.g. `"Network connection restored. 12 stored events synchronized successfully."`). |
| **Is the error logged?** | Yes, synchronized events are tagged in `eta_history` with `network_status='OFFLINE'` and event type `'NETWORK_SYNCHRONIZATION'`. |
| **Does system continue operating?** | **Yes.** The bus continues navigating, accumulating records without loss. |

---

## 3. Deep Dive: Key Failure Scenarios

### Scenario A: GPS Hardware / Signal Outage
```
[GPS Telemetry Interrupted / Null Coords]
               │
               ▼
[Detect: failures.case_name='gps' == 'ACTIVE' OR missing coords]
               │
               ▼
[Fallback: Retrieve last confirmed position from buses table (get_fallback_gps)]
               │
               ▼
[Freeze Bus Map Marker at Last Known Waypoint]
               │
               ▼
[Calculate Remaining ETA using Dead-Reckoning from Last Known Position]
               │
               ▼
[Attribute +3.0 min Search/Buffering Penalty in Explanation]
               │
               ▼
[Log in Audit Trail: trigger_factor='GPS_SIGNAL_LOSS', gps_status='OFFLINE']
               │
               ▼
[Emit Parent Notification: "⚠️ Bus 101 GPS signal lost. Using last known location."]
```

### Scenario B: Cellular Network Outage & Store-and-Forward Recovery
```
[Cellular Connection Drops (failures.case_name='network' == 'ACTIVE')]
               │
               ▼
[Simulation / Mobile Client Detects Network Unavailability]
               │
               ▼
[Route Traversal Continues: ETAs Recalculate Locally]
               │
               ▼
[Events Diverted: Written to state['store_and_forward_queue'] (No SQLite Lock)]
               │
               ▼
[Network Reconnects: set_failure_status('network', 'INACTIVE')]
               │
               ▼
[synchronize_network_queue() Flushes Queue in FIFO Order]
               │
               ▼
[Events Committed to notifications, eta_history, and eta_plan_audit]
               │
               ▼
[Audit Ledger Records event_type='NETWORK_SYNCHRONIZATION']
               │
               ▼
[Queue Emptied; System Returns to Direct-Write Mode]
```

### Scenario C: Speed Sensor Telemetry Discrepancy
```
[Sensor reports 0 km/h speed, but bus status is 'ON_ROUTE']
               │
               ▼
[Detect: failures.case_name='sensor' == 'ACTIVE' OR (speed <= 0 and status == 'ON_ROUTE')]
               │
               ▼
[Fallback: Substitute Calibrated Transit Operating Speed (30.0 km/h)]
               │
               ▼
[ETA Calculation Proceeds without Division-by-Zero or Infinite Arrival Times]
               │
               ▼
[Explanation Rule Engine Attributes: primary_reason='SENSOR_DISCREPANCY']
               │
               ▼
[Log in Audit Trail: trigger_factor='SENSOR_DISCREPANCY']
```

---

## 4. Database Error Handling & Concurrency Safeguards

SQLite is an in-process, file-based relational database. To ensure robust operation in a concurrent web environment, the system implements specific error mitigations:

| Database Condition | Real System Behavior | Fallback / Safeguard | Future Recommended Improvement |
| :--- | :--- | :--- | :--- |
| **Connection Failure** | `sqlite3.connect()` raises exception if file path or permissions are invalid. | Trapped in `init_db()` or API error handlers; returns HTTP 500 without leaking filesystem paths. | Automate database directory health checks on startup. |
| **Database Locked (`BUSY`)**| Concurrent read/write can trigger `sqlite3.OperationalError: database is locked`. | All connections configured with `timeout=10.0` seconds to queue lock acquisitions automatically. | Enable Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) for concurrent read/write concurrency. |
| **Query Syntax Failure** | Invalid column or table name raises `sqlite3.OperationalError`. | Queries use parameterized placeholders (`?`) preventing syntax injection. | Add automated database linting in test suite. |
| **Duplicate Primary Key** | Inserting an existing `event_id` raises `sqlite3.IntegrityError`. | `record_processed_telemetry` uses `INSERT OR IGNORE` to discard duplicates safely without error. | Expose duplicate metric counter on admin dashboard. |
| **Missing Foreign Key** | Inserting invalid `route_id` or `stop_id`. | Foreign key constraints defined in `schema.sql`. API routes validate IDs before insert. | Enforce `PRAGMA foreign_keys = ON;` on every SQLite connection. |
| **Transaction Failure** | Unhandled exception during multi-table update. | SQLite transactions roll back uncommitted changes when connection closes without `conn.commit()`. | Implement explicit context manager (`with conn:`) for atomic commit/rollback. |

---

## 5. Security & Information Sanitization Rules

To prevent information disclosure and ensure clean API responses:
1. **Never Expose Internal Tracebacks**: Route handlers never pass raw `str(e)` containing database schema names or file paths to the client.
2. **Standardized Error Structures**: All error responses return uniform JSON:
   ```json
   {
     "status": "ERROR",
     "error": "Descriptive user-facing message"
   }
   ```
3. **HTTP Status Code Discipline**:
   - `400 Bad Request`: Client parameter missing, malformed, or invalid enum.
   - `404 Not Found`: Bus ID, Stop ID, or Audit ID not found in database.
   - `500 Internal Server Error`: Unhandled server exception (sanitized in production).
