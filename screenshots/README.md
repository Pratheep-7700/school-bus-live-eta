# Application Screenshots & Demonstration Previews

This folder contains screenshots and visual previews of the **Live ETA Communication Service for School-Bus Network**.

## Visual Showcase

### 1. Operations Dashboard
- Real-time fleet metrics (Active, On-Time, Delayed buses)
- System telemetry, traffic level selector, and dynamic alert feed
- One-click Simulation Controller (Start, Pause, Reset, 7-Step Demo)

### 2. Live Bus Fleet Tracking
- High-contrast interactive OpenStreetMap rendered via Leaflet.js
- Live bus GPS markers with real-time heading, speed, next stop, and delay indicators
- Dynamic polyline route traces and color-coded stop pins

### 3. Student Attendance & Dwell Time Matrix
- Individual student check-in toggle (Present / Absent)
- Live dwell time adjustment based on present passenger count (`30s + 20s/student`)
- Customer Pickup Commitment tracking (`MET`, `AT_RISK`, `BREACHED`)

### 4. ETA History & Audit Log
- Chronological audit ledger recording every ETA recalculation
- Transparent explanation breakdown (`Traffic`, `Student Boarding`, `Dwell Time`)
- Origin tracking: `AUTOMATIC`, `MANUAL`, or `FALLBACK`

### 5. Failure Injection & Resilience
- Live toggles for GPS, Network, Traffic, and Sensor fault injection
- Resilient store-and-forward offline synchronization demonstration
- Visual alerts and safety fallback fall-throughs

### 6. Simulation Experiment & Evaluation Reports
- Comparative statistical error analytics (Baseline Schedule vs. Proposed Dynamic ETA)
- MAE and RMSE performance reduction charts powered by Chart.js
- Customer status enquiry call-volume reduction visualization (-89.5%)
