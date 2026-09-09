# Failure Mode & Effects Analysis (FMEA)

This document analyzes the four failure conditions simulated in the prototype and reviews the system resilience and recovery mechanisms.

## Resilience Matrix

| Failure | Detection | Impact | Fallback | Recovery |
| :--- | :--- | :--- | :--- | :--- |
| **GPS Failure** | Telemetry stream timeout or null coordinate readings | Real-time vehicle coordinates stop updating | System retains and pins to **last known coordinates**; projects remaining travel time using planned stop geometry | Resumes live coordinate tracking once GPS feed reconnects |
| **Network Failure** | HTTP transmission timeout or dropped ping heartbeat | Telemetry and ETA update logs cannot be posted directly to the central database | Activates **Store-and-Forward** mode; queues timestamped events locally in memory/cache | Flushes and synchronizes all queued events to the SQLite audit log once network connection is restored |
| **Traffic Data Failure** | Live congestion index feed disconnects or returns 500 error | Dynamic real-time traffic delay minutes become unavailable | Defaults to historical baseline traffic level (**MEDIUM** traffic = +3 minutes delay) | Switches back to real-time traffic index as soon as traffic feed recovers |
| **Sensor Failure** | Anomaly check detects invalid zero speed while bus status is `ON_ROUTE` (`status == 'ON_ROUTE'` and `speed == 0`) | Inaccurate instantaneous speed would corrupt travel time prediction | Discards erratic reading and applies **last known valid speed** (or nominal 30 km/h) | Restores live sensor readings once valid speed values resume |
