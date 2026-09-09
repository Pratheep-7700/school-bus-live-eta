# ETA Prediction Algorithm

This document details the transparent, explainable ETA calculation formula used by the Live School-Bus ETA system.

---

## 1. High-Level Formula

The system predicts the estimated arrival time (ETA) for each upcoming stop on a route using a multi-factor additive equation:

$$\text{ETA} = \text{Current Time} + \text{Remaining Travel Time} + \text{Expected Dwell Time} + \text{Traffic Delay}$$

Where:
- **$\text{Current Time}$**: The current clock time (in minutes from midnight).
- **$\text{Remaining Travel Time}$**: Projected drive time based on real-time distance and vehicle velocity.
- **$\text{Expected Dwell Time}$**: Estimated boarding delay based on student attendance at intermediate stops.
- **$\text{Traffic Delay}$**: Dynamic delay added based on live traffic congestion levels.

---

## 2. Component Calculations

### A. Remaining Travel Time
Travel time between the vehicle's current location and the target stop is determined using geographic distance and average velocity:

$$\text{Distance} = \text{Haversine}(\text{lat}_1, \text{lon}_1, \text{lat}_2, \text{lon}_2) \quad \text{[in km]}$$

$$\text{Travel Time (minutes)} = \left( \frac{\text{Distance}}{\text{Average Speed (km/h)}} \right) \times 60$$

- **Geographic Distance**: Computed using the Haversine formula over the Earth's radius (6,371 km).
- **Sensor Speed Fallback**: If the onboard speed sensor reports an abnormal zero reading while in transit (`status == 'ON_ROUTE'`), the system ignores the reading and substitutes the last valid recorded speed (default 30 km/h).

### B. Expected Dwell Time (Attendance-Aware)
School bus stops experience dwell times that scale with the number of boarding students:

$$\text{Dwell Time (seconds)} = 30 + (\text{Present Students} \times 20)$$

- **Base Dwell Time**: 30 seconds (bus deceleration, door opening, safe pull-away).
- **Student Boarding Time**: 20 seconds per present student.
- **Absent Students**: When students are marked **Absent**, their boarding time is eliminated, saving 20 seconds per absent child and preventing schedule drift.

For multiple intermediate stops along the remaining route:
$$\text{Total Expected Dwell} = \sum_{s \in \text{Remaining Stops}} \frac{\text{Dwell Time}(s)}{60} \quad \text{[in minutes]}$$

### C. Traffic Delay
Traffic conditions are classified into three levels, providing deterministic delay additions:

| Traffic Level | Added Delay (Minutes) | Description |
| :--- | :--- | :--- |
| **LOW** | 0 minutes | Free-flowing traffic, nominal speed limits |
| **MEDIUM** | +3 minutes | Moderate congestion, signal waiting |
| **HIGH** | +7 minutes | Heavy congestion, bumper-to-bumper peak traffic |

*Fallback*: If the live traffic data feed disconnects, the system automatically falls back to **MEDIUM** (+3 min).

---

## 3. Comparison: Proposed Dynamic ETA vs. Static Baseline

| Feature | Static Baseline System | Proposed Dynamic System |
| :--- | :--- | :--- |
| **Formula** | Scheduled Timetable Only | Live Time + Distance/Speed + Attendance Dwell + Traffic |
| **GPS Position** | Ignored | Tracked dynamically in real time |
| **Traffic Congestion** | Ignored (Assumes 0 delay) | Incorporates real-time congestion (+0m, +3m, +7m) |
| **Student Attendance** | Ignored (Fixed duration) | Dynamically scales dwell time (30s + 20s/student) |
| **Sensor Failures** | Cannot detect | Fallback to last known coordinates and valid speed |
| **Auditability** | Static records only | Immutable audit log explaining every significant shift |

---

## 4. Meaningful Change & Notification Rules

To prevent alert fatigue, notifications are only sent for meaningful ETA changes:

- **Change < 2 minutes**: Deemed negligible; no parent/customer notification sent.
- **Change $\ge$ 2 minutes**: Generates standard **ETA Update** notification.
- **Change $\ge$ 5 minutes**: Triggers high-priority **Delay Alert** (`CRITICAL`).
- **Customer Pickup Commitment**: If ETA exceeds the parent's committed pickup time, status transitions from `ON_TIME` to `COMMITMENT AT RISK`.
