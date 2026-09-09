-- Schema for School Bus ETA Communication system

DROP TABLE IF EXISTS routes;
CREATE TABLE routes (
    route_id TEXT PRIMARY KEY,
    route_name TEXT NOT NULL,
    student_count INTEGER DEFAULT 0
);

DROP TABLE IF EXISTS stops;
CREATE TABLE stops (
    stop_id TEXT PRIMARY KEY,
    route_id TEXT NOT NULL,
    stop_name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    planned_arrival_time TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    FOREIGN KEY (route_id) REFERENCES routes (route_id)
);

DROP TABLE IF EXISTS students;
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    student_name TEXT NOT NULL,
    route_id TEXT NOT NULL,
    stop_id TEXT NOT NULL,
    committed_pickup_time TEXT NOT NULL,
    FOREIGN KEY (route_id) REFERENCES routes (route_id),
    FOREIGN KEY (stop_id) REFERENCES stops (stop_id)
);

DROP TABLE IF EXISTS buses;
CREATE TABLE buses (
    bus_id TEXT PRIMARY KEY,
    registration_number TEXT NOT NULL,
    driver_name TEXT NOT NULL,
    route_id TEXT NOT NULL,
    current_latitude REAL NOT NULL,
    current_longitude REAL NOT NULL,
    speed REAL NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (route_id) REFERENCES routes (route_id)
);

DROP TABLE IF EXISTS attendance;
CREATE TABLE attendance (
    student_id TEXT PRIMARY KEY,
    status TEXT NOT NULL, -- 'Present' or 'Absent'
    FOREIGN KEY (student_id) REFERENCES students (student_id)
);

DROP TABLE IF EXISTS eta_history;
CREATE TABLE eta_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    bus_id TEXT NOT NULL,
    route_id TEXT NOT NULL,
    previous_eta TEXT,
    new_eta TEXT NOT NULL,
    delay_minutes REAL DEFAULT 0,
    reason TEXT NOT NULL,
    traffic_level TEXT NOT NULL,
    student_count INTEGER DEFAULT 0,
    dwell_time REAL DEFAULT 0,
    gps_status TEXT NOT NULL,
    network_status TEXT NOT NULL,
    notification_sent INTEGER DEFAULT 0,
    source TEXT NOT NULL -- 'AUTO' or 'MANUAL'
);

DROP TABLE IF EXISTS notifications;
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    bus_id TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL -- 'INFO', 'WARNING', 'ALERT', 'CRITICAL'
);

DROP TABLE IF EXISTS failures;
CREATE TABLE failures (
    case_name TEXT PRIMARY KEY, -- 'gps', 'network', 'traffic', 'sensor'
    status TEXT NOT NULL DEFAULT 'INACTIVE', -- 'ACTIVE' or 'INACTIVE'
    description TEXT
);

DROP TABLE IF EXISTS feedback;
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    q1 INTEGER NOT NULL,
    q2 INTEGER NOT NULL,
    q3 INTEGER NOT NULL,
    q4 INTEGER NOT NULL,
    q5 INTEGER NOT NULL,
    comments TEXT
);

DROP TABLE IF EXISTS customer_commitments;
CREATE TABLE customer_commitments (
    commitment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    stop_id TEXT NOT NULL,
    target_pickup_time TEXT NOT NULL,
    window_minutes INTEGER DEFAULT 5,
    status TEXT DEFAULT 'MET', -- 'MET', 'AT_RISK', 'BREACHED'
    FOREIGN KEY (student_id) REFERENCES students (student_id),
    FOREIGN KEY (stop_id) REFERENCES stops (stop_id)
);

DROP TABLE IF EXISTS experiment_results;
CREATE TABLE experiment_results (
    metric_name TEXT PRIMARY KEY,
    baseline_value REAL NOT NULL,
    proposed_value REAL NOT NULL
);
