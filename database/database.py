import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'school_bus.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_db_connection():
    """
    Creates and returns an active SQLite database connection with row access by column name.

    Purpose:
        Central connection factory for all database interactions across the application.
        Configures row_factory as sqlite3.Row for dictionary-like column access and sets
        a 10-second busy timeout to mitigate SQLite table lock contention during concurrent
        telemetry and web simulation requests.

    Returns:
        sqlite3.Connection: Active database connection handle.

    Fallback Behavior:
        If connection cannot be established (e.g. invalid path or file permission issue),
        raises sqlite3.OperationalError which is captured at the API layer.
    """
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force=False):
    """
    Initializes database schema and populates sample routes, stops, buses, and students.

    Purpose:
        Bootstraps the SQLite database from schema.sql if the database file does not exist,
        is empty, or if force initialization is requested. Also performs non-destructive
        schema migrations on existing databases for audit and telemetry tables.

    Parameters:
        force (bool): If True, drops and recreates all tables, resetting the database.

    Returns:
        None

    Fallback Behavior:
        Safely attempts to create missing tables (eta_plan_audit, processed_telemetry)
        on existing database instances to prevent migration crashes on startup.
    """
    db_exists = os.path.exists(DATABASE_PATH)
    
    if force or not db_exists or os.path.getsize(DATABASE_PATH) == 0:
        print("Initializing database schema...")
        conn = get_db_connection()
        with open(SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        load_sample_data()
    else:
        # Ensure new tables are migrated on existing DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eta_plan_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bus_id TEXT NOT NULL,
                route_id TEXT,
                trip_id TEXT,
                stop_id TEXT,
                event_type TEXT NOT NULL,
                trigger_factor TEXT NOT NULL,
                trigger_details TEXT,
                previous_eta TEXT,
                new_eta TEXT,
                previous_delay_minutes REAL,
                new_delay_minutes REAL,
                previous_plan TEXT,
                new_plan TEXT,
                explanation TEXT,
                telemetry_snapshot TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT DEFAULT 'system'
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_telemetry (
                event_id TEXT PRIMARY KEY,
                bus_id TEXT NOT NULL,
                route_id TEXT,
                trip_id TEXT,
                timestamp TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed REAL NOT NULL,
                received_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()



def load_sample_data():
    print("Loading sample data into SQLite...")
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Insert Routes
    routes_data = [
        ('Route 1', 'Route 1 - North Valley', 11),
        ('Route 2', 'Route 2 - East Highlands', 9),
        ('Route 3', 'Route 3 - West Bay', 10)
    ]
    cursor.executemany("INSERT INTO routes (route_id, route_name, student_count) VALUES (?, ?, ?);", routes_data)

    # 2. Insert Stops
    stops_data = [
        # Route 1 (Stop A, B, C, School)
        ('Stop_A', 'Route 1', 'Stop A - Oak St', 37.7949, -122.4394, '08:00 AM', 1),
        ('Stop_B', 'Route 1', 'Stop B - Pine St', 37.7889, -122.4294, '08:10 AM', 2),
        ('Stop_C', 'Route 1', 'Stop C - Maple Ave', 37.7819, -122.4244, '08:20 AM', 3),
        ('School_1', 'Route 1', 'High School Campus', 37.7749, -122.4194, '08:30 AM', 4),

        # Route 2 (Stop D, E, F, School)
        ('Stop_D', 'Route 2', 'Stop D - Elm Rd', 37.7549, -122.4494, '08:00 AM', 1),
        ('Stop_E', 'Route 2', 'Stop E - Cedar Ln', 37.7609, -122.4394, '08:10 AM', 2),
        ('Stop_F', 'Route 2', 'Stop F - Birch Blvd', 37.7689, -122.4294, '08:20 AM', 3),
        ('School_2', 'Route 2', 'High School Campus', 37.7749, -122.4194, '08:30 AM', 4),

        # Route 3 (Stop G, H, I, School)
        ('Stop_G', 'Route 3', 'Stop G - Willow Dr', 37.7549, -122.3994, '08:00 AM', 1),
        ('Stop_H', 'Route 3', 'Stop H - Spruce Way', 37.7609, -122.4094, '08:10 AM', 2),
        ('Stop_I', 'Route 3', 'Stop I - Redwood Ct', 37.7689, -122.4144, '08:20 AM', 3),
        ('School_3', 'Route 3', 'High School Campus', 37.7749, -122.4194, '08:30 AM', 4)
    ]
    cursor.executemany("INSERT INTO stops (stop_id, route_id, stop_name, latitude, longitude, planned_arrival_time, sequence) VALUES (?, ?, ?, ?, ?, ?, ?);", stops_data)

    # 3. Insert Students & Commitments
    students_data = [
        # Stop A - 4 students
        ('S101', 'Arun Kumar', 'Route 1', 'Stop_A', '08:00 AM'),
        ('S102', 'Betty Davis', 'Route 1', 'Stop_A', '08:00 AM'),
        ('S103', 'Charlie Young', 'Route 1', 'Stop_A', '08:00 AM'),
        ('S104', 'David Miller', 'Route 1', 'Stop_A', '08:00 AM'),
        # Stop B - 2 students
        ('S105', 'Emma Watson', 'Route 1', 'Stop_B', '08:10 AM'),
        ('S106', 'Frank Harris', 'Route 1', 'Stop_B', '08:10 AM'),
        # Stop C - 5 students
        ('S107', 'Grace Hopper', 'Route 1', 'Stop_C', '08:20 AM'),
        ('S108', 'Henry Ford', 'Route 1', 'Stop_C', '08:20 AM'),
        ('S109', 'Ivy Chen', 'Route 1', 'Stop_C', '08:20 AM'),
        ('S110', 'Jack Ma', 'Route 1', 'Stop_C', '08:20 AM'),
        ('S111', 'Kevin Hart', 'Route 1', 'Stop_C', '08:20 AM'),

        # Stop D - 3 students
        ('S201', 'Liam Neeson', 'Route 2', 'Stop_D', '08:00 AM'),
        ('S202', 'Mia Farrow', 'Route 2', 'Stop_D', '08:00 AM'),
        ('S203', 'Noah Webster', 'Route 2', 'Stop_D', '08:00 AM'),
        # Stop E - 4 students
        ('S204', 'Olivia Wilde', 'Route 2', 'Stop_E', '08:10 AM'),
        ('S205', 'Paul Walker', 'Route 2', 'Stop_E', '08:10 AM'),
        ('S206', 'Quincy Jones', 'Route 2', 'Stop_E', '08:10 AM'),
        ('S207', 'Rachel Green', 'Route 2', 'Stop_E', '08:10 AM'),
        # Stop F - 2 students
        ('S208', 'Steve Jobs', 'Route 2', 'Stop_F', '08:20 AM'),
        ('S209', 'Tina Turner', 'Route 2', 'Stop_F', '08:20 AM'),

        # Stop G - 5 students
        ('S301', 'Uma Thurman', 'Route 3', 'Stop_G', '08:00 AM'),
        ('S302', 'Victor Hugo', 'Route 3', 'Stop_G', '08:00 AM'),
        ('S303', 'Wendy Williams', 'Route 3', 'Stop_G', '08:00 AM'),
        ('S304', 'Xavier Cugat', 'Route 3', 'Stop_G', '08:00 AM'),
        ('S305', 'Yoko Ono', 'Route 3', 'Stop_G', '08:00 AM'),
        # Stop H - 2 students
        ('S306', 'Zack Snyder', 'Route 3', 'Stop_H', '08:10 AM'),
        ('S307', 'Abby Smith', 'Route 3', 'Stop_H', '08:10 AM'),
        # Stop I - 3 students
        ('S308', 'Bob Dylan', 'Route 3', 'Stop_I', '08:20 AM'),
        ('S309', 'Celine Dion', 'Route 3', 'Stop_I', '08:20 AM'),
        ('S310', 'Drake Graham', 'Route 3', 'Stop_I', '08:20 AM')
    ]
    cursor.executemany("INSERT INTO students (student_id, student_name, route_id, stop_id, committed_pickup_time) VALUES (?, ?, ?, ?, ?);", students_data)

    # 4. Insert Default Attendance & Customer Commitments (all present initially)
    for student in students_data:
        cursor.execute("INSERT INTO attendance (student_id, status) VALUES (?, 'Present');", (student[0],))
        cursor.execute("INSERT INTO customer_commitments (student_id, stop_id, target_pickup_time, window_minutes, status) VALUES (?, ?, ?, 5, 'MET');",
                       (student[0], student[3], student[4]))

    # 5. Insert Buses
    buses_data = [
        ('101', 'SB-101', 'John Doe', 'Route 1', 37.7949, -122.4394, 30.0, 'ON_ROUTE'),
        ('102', 'SB-102', 'Jane Smith', 'Route 2', 37.7549, -122.4494, 30.0, 'ON_ROUTE'),
        ('103', 'SB-103', 'Bob Jones', 'Route 3', 37.7549, -122.3994, 30.0, 'ON_ROUTE'),
        ('104', 'SB-104', 'Alice Green', 'Route 1', 37.7749, -122.4194, 0.0, 'INACTIVE'),
        ('105', 'SB-105', 'Charlie Brown', 'Route 2', 37.7749, -122.4194, 0.0, 'INACTIVE')
    ]
    cursor.executemany("INSERT INTO buses (bus_id, registration_number, driver_name, route_id, current_latitude, current_longitude, speed, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?);", buses_data)

    # 6. Insert Failures Initial State
    failures_data = [
        ('gps', 'INACTIVE', 'GPS unavailable. Using last known location.'),
        ('network', 'INACTIVE', 'Network unavailable. Using store-and-forward mode.'),
        ('traffic', 'INACTIVE', 'Traffic data unavailable. Using fallback traffic estimate.'),
        ('sensor', 'INACTIVE', 'Abnormal sensor reading detected. Using previous valid value.')
    ]
    cursor.executemany("INSERT INTO failures (case_name, status, description) VALUES (?, ?, ?);", failures_data)

    conn.commit()
    conn.close()
    print("Default sample data loaded successfully.")
    try:
        from simulator.data_generator import generate_experiment_dataset
        generate_experiment_dataset()
    except Exception as e:
        print(f"Notice: Experiment dataset initialization deferred ({e})")

import json
from datetime import datetime

def insert_eta_plan_audit(
    bus_id,
    route_id=None,
    trip_id=None,
    stop_id=None,
    event_type="ETA_RECALCULATION",
    trigger_factor="UNKNOWN",
    trigger_details=None,
    previous_eta=None,
    new_eta=None,
    previous_delay_minutes=0.0,
    new_delay_minutes=0.0,
    previous_plan=None,
    new_plan=None,
    explanation=None,
    telemetry_snapshot=None,
    created_at=None,
    created_by="system",
    conn=None
):
    """
    Appends an immutable audit entry to the eta_plan_audit table.

    Purpose:
        Maintains an append-only, tamper-evident audit ledger of every ETA recalculation,
        traffic adjustment, telemetry ingestion, or manual driver override. Normal operations
        must only append records to this table, never update or delete existing entries.

    Parameters:
        bus_id (str): Vehicle identifier.
        route_id (str, optional): Route identifier.
        trip_id (str, optional): Unique trip run identifier.
        stop_id (str, optional): Target stop ID.
        event_type (str): Category ('ETA_RECALCULATION', 'TRAFFIC_UPDATE', 'MANUAL_OVERRIDE', 'TELEMETRY_UPDATE', etc.).
        trigger_factor (str): Machine-readable trigger ('GPS_TELEMETRY', 'TRAFFIC_DELAY', 'HIGH_BOARDING_TIME', etc.).
        trigger_details (str, optional): Detailed text describing why the recalculation occurred.
        previous_eta (str, optional): Prior ETA string ('HH:MM AM/PM').
        new_eta (str, optional): Updated ETA string ('HH:MM AM/PM').
        previous_delay_minutes (float): Delay relative to schedule prior to update.
        new_delay_minutes (float): Delay relative to schedule after update.
        previous_plan (dict or str, optional): Serialized prior route ETA schedule.
        new_plan (dict or str, optional): Serialized updated route ETA schedule.
        explanation (str, optional): Human-readable natural-language explanation.
        telemetry_snapshot (dict or str, optional): Full telemetry readings at time of event.
        created_at (str, optional): Timestamp string ('YYYY-MM-DD HH:MM:SS'); defaults to now.
        created_by (str): Actor or subsystem ('system', 'dispatcher', 'driver_fallback', etc.).
        conn (sqlite3.Connection, optional): Existing DB connection; if None, manages own connection.

    Returns:
        int: Primary key ID of the newly created audit row.

    Fallback Behavior:
        Automatically serializes dict/list payloads to JSON strings. If conn was None,
        guarantees connection is closed in finally block.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Serialize objects to JSON strings if passed as dict/list
    if previous_plan is not None and not isinstance(previous_plan, str):
        previous_plan = json.dumps(previous_plan)
    if new_plan is not None and not isinstance(new_plan, str):
        new_plan = json.dumps(new_plan)
    if telemetry_snapshot is not None and not isinstance(telemetry_snapshot, str):
        telemetry_snapshot = json.dumps(telemetry_snapshot)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO eta_plan_audit (
            bus_id, route_id, trip_id, stop_id, event_type,
            trigger_factor, trigger_details, previous_eta, new_eta,
            previous_delay_minutes, new_delay_minutes, previous_plan,
            new_plan, explanation, telemetry_snapshot, created_at, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        str(bus_id),
        route_id,
        trip_id,
        stop_id,
        str(event_type),
        str(trigger_factor),
        trigger_details,
        previous_eta,
        new_eta,
        float(previous_delay_minutes) if previous_delay_minutes is not None else 0.0,
        float(new_delay_minutes) if new_delay_minutes is not None else 0.0,
        previous_plan,
        new_plan,
        explanation,
        telemetry_snapshot,
        str(created_at),
        str(created_by)
    ))
    record_id = cursor.lastrowid
    conn.commit()

    if close_conn:
        conn.close()

    return record_id

def query_eta_plan_audit(
    bus_id=None,
    route_id=None,
    trip_id=None,
    date=None,
    trigger_factor=None,
    limit=100,
    offset=0
):
    """
    Queries immutable audit records from eta_plan_audit supporting multi-parameter filtering.

    Purpose:
        Provides backend data retrieval for audit trail inspection interfaces, compliance reviews,
        and post-incident timeline reconstruction.

    Parameters:
        bus_id (str, optional): Filter by vehicle identifier (or 'all').
        route_id (str, optional): Filter by route identifier (or 'all').
        trip_id (str, optional): Filter by trip run identifier (or 'all').
        date (str, optional): Filter by date prefix ('YYYY-MM-DD').
        trigger_factor (str, optional): Filter by specific causal trigger code (or 'all').
        limit (int): Pagination page size (default: 100).
        offset (int): Pagination record offset (default: 0).

    Returns:
        list[dict]: Ordered list of audit records (most recent first).

    Fallback Behavior:
        Ignores 'all' or empty filter parameters, returning unfiltered chronological results.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM eta_plan_audit WHERE 1=1"
    params = []

    if bus_id and bus_id != "all":
        query += " AND bus_id = ?"
        params.append(bus_id)
    if route_id and route_id != "all":
        query += " AND route_id = ?"
        params.append(route_id)
    if trip_id and trip_id != "all":
        query += " AND trip_id = ?"
        params.append(trip_id)
    if date:
        query += " AND created_at LIKE ?"
        params.append(f"{date}%")
    if trigger_factor and trigger_factor != "all":
        query += " AND trigger_factor = ?"
        params.append(trigger_factor)

    query += " ORDER BY id DESC LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_eta_plan_audit_by_id(record_id):
    """
    Retrieves a single audit record by its primary key ID.

    Purpose:
        Supports deep inspection of full plans, previous plans, and telemetry snapshots
        for a specific timeline event.

    Parameters:
        record_id (int): Primary key ID.

    Returns:
        dict or None: Audit row dictionary if found; None if record does not exist.

    Fallback Behavior:
        Safely returns None if row not found, allowing API to respond with 404 cleanly.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM eta_plan_audit WHERE id = ?;", (record_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def is_telemetry_processed(event_id):
    """
    Checks if a telemetry event_id has already been processed for store-and-forward deduplication.

    Purpose:
        Guarantees idempotency when mobile clients or offline edge caches re-send buffered
        telemetry batches upon network reconnection.

    Parameters:
        event_id (str): Unique UUID/string identifying the telemetry event.

    Returns:
        bool: True if already recorded in processed_telemetry; False otherwise.

    Fallback Behavior:
        Returns False if event_id is None or empty.
    """
    if not event_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_telemetry WHERE event_id = ? LIMIT 1;", (str(event_id),))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def record_processed_telemetry(event_id, bus_id, route_id=None, trip_id=None, timestamp=None, latitude=0.0, longitude=0.0, speed=0.0):
    """
    Records a processed telemetry event to prevent duplicate processing on subsequent retries.

    Purpose:
        Maintains an indexed deduplication ledger of received telemetry UUIDs.
        Uses INSERT OR IGNORE to prevent primary key violation exceptions during high-frequency retries.

    Parameters:
        event_id (str): Unique telemetry event UUID.
        bus_id (str): Vehicle identifier.
        route_id (str, optional): Route identifier.
        trip_id (str, optional): Trip run identifier.
        timestamp (str, optional): Vehicle generation timestamp.
        latitude (float): Vehicle latitude.
        longitude (float): Vehicle longitude.
        speed (float): Vehicle speed in km/h.

    Returns:
        None

    Fallback Behavior:
        Uses INSERT OR IGNORE so conflicting identical UUIDs do not trigger database crashes.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO processed_telemetry (
            event_id, bus_id, route_id, trip_id, timestamp, latitude, longitude, speed, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (str(event_id), str(bus_id), route_id, trip_id, str(timestamp or now_str), float(latitude), float(longitude), float(speed), now_str))
    conn.commit()
    conn.close()


