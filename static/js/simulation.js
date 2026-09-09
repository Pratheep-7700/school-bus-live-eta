// Simulation state manager and demo driver
let simInterval = null;

function refreshSimState() {
    fetch('/api/simulation/state')
        .then(res => res.json())
        .then(state => {
            // Update clock
            document.getElementById('sim-clock-time').innerText = state.current_time;
            
            // Update state indicator
            const indicator = document.getElementById('sim-state-indicator');
            if (state.is_running) {
                indicator.className = 'simulation-indicator-badge simulation-active';
                indicator.innerHTML = '<span class="status-indicator status-active"></span>Simulation Active';
                
                // Ensure interval is running locally if active
                if (!simInterval) {
                    simInterval = setInterval(tickSimulation, 1500); // 1.5 seconds real time = 1 min simulation time
                }
            } else {
                indicator.className = 'simulation-indicator-badge simulation-paused';
                indicator.innerHTML = '<span class="status-indicator status-warning"></span>Simulation Paused';
                
                // Clear interval
                if (simInterval) {
                    clearInterval(simInterval);
                    simInterval = null;
                }
            }

            // Sync with page specific reload functions if they exist
            if (window.loadDashboardData) window.loadDashboardData();
            if (window.loadMapData) window.loadMapData();
            
            // Sync failure page offline counts if on that page
            const countSpan = document.getElementById('span-queue-count');
            if (countSpan) {
                countSpan.innerText = (state.store_and_forward_queue || []).length;
            }
        });
}

function startSimulation() {
    fetch('/api/simulation/start', { method: 'POST' })
        .then(res => res.json())
        .then(() => {
            refreshSimState();
        });
}

function pauseSimulation() {
    fetch('/api/simulation/stop', { method: 'POST' })
        .then(res => res.json())
        .then(() => {
            refreshSimState();
        });
}

function tickSimulation() {
    fetch('/api/simulation/tick', { method: 'POST' })
        .then(res => res.json())
        .then(state => {
            document.getElementById('sim-clock-time').innerText = state.current_time;
            refreshSimState();
        });
}

function resetSimulation() {
    if (confirm("Are you sure you want to reset the simulation? All audit logs and active failure triggers will be cleared.")) {
        fetch('/api/simulation/reset', { method: 'POST' })
            .then(res => res.json())
            .then(() => {
                refreshSimState();
                alert("Simulation reset successfully to 07:58 AM.");
                window.location.reload();
            });
    }
}

// 7-step Demo Scenario engine
const demoSteps = [
    {
        stepNum: 1,
        title: "Step 1: Bus starts on time",
        desc: "Bus 101 departs on Route 1. Initial ETA matches scheduled plan (08:00 AM at Stop A). All telemetry is nominal.",
        action: function() {
            // Reset and start
            fetch('/api/simulation/reset', { method: 'POST' })
                .then(() => fetch('/api/traffic', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ route_id: 'Route 1', traffic_level: 'LOW' })
                }))
                .then(() => fetch('/api/simulation/start', { method: 'POST' }))
                .then(() => {
                    refreshSimState();
                });
        }
    },
    {
        stepNum: 2,
        title: "Step 2: Traffic delay occurs (+5 to +7 minutes)",
        desc: "Heavy congestion detected on Route 1. Traffic level set to HIGH (+7 min). ETA updates automatically with explanation: Traffic congestion.",
        action: function() {
            fetch('/api/traffic', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ route_id: 'Route 1', traffic_level: 'HIGH' })
            })
            .then(() => fetch('/api/simulation/tick', { method: 'POST' }))
            .then(() => {
                refreshSimState();
            });
        }
    },
    {
        stepNum: 3,
        title: "Step 3: Several students marked absent",
        desc: "Students S102, S103, S104 at Stop A are marked Absent. Boarding time decreases. ETA recalculates earlier with explanation: Reduced student dwell time.",
        action: function() {
            const absentIds = ['S102', 'S103', 'S104'];
            Promise.all(absentIds.map(id => {
                return fetch('/api/attendance', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ student_id: id, status: 'Absent' })
                });
            }))
            .then(() => fetch('/api/simulation/tick', { method: 'POST' }))
            .then(() => {
                refreshSimState();
            });
        }
    },
    {
        stepNum: 4,
        title: "Step 4: Multiple students present at next stop",
        desc: "All students at Stop B and Stop C are confirmed Present. Boarding dwell time increases. ETA updates later with explanation: Student boarding delay.",
        action: function() {
            const presentIds = ['S105', 'S106', 'S107', 'S108', 'S109', 'S110', 'S111'];
            Promise.all(presentIds.map(id => {
                return fetch('/api/attendance', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ student_id: id, status: 'Present' })
                });
            }))
            .then(() => fetch('/api/simulation/tick', { method: 'POST' }))
            .then(() => {
                refreshSimState();
            });
        }
    },
    {
        stepNum: 5,
        title: "Step 5: Customer pickup commitment warning",
        desc: "Due to cumulative delays, estimated arrival at Stop B (08:18 AM) exceeds the customer commitment window (08:10 AM ±5m). System flags Commitment Status: AT_RISK and raises customer alert.",
        action: function() {
            fetch('/api/simulation/tick', { method: 'POST' })
                .then(() => {
                    refreshSimState();
                });
        }
    },
    {
        stepNum: 6,
        title: "Step 6: GPS temporarily fails (Fallback Active)",
        desc: "Bus 101 GPS signal drops. System activates fallback mode: freezes coordinates at last known location, calculates remaining travel using planned route geometry, and displays warning.",
        action: function() {
            fetch('/api/failure/gps', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ active: true })
            })
            .then(() => fetch('/api/simulation/tick', { method: 'POST' }))
            .then(() => {
                refreshSimState();
            });
        }
    },
    {
        stepNum: 7,
        title: "Step 7: Driver submits manual ETA update",
        desc: "Driver manually submits location update near Pine St with updated ETA 08:20 AM. System updates display and logs manual override in audit table (source: MANUAL).",
        action: function() {
            fetch('/api/manual-eta', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    bus_id: '101',
                    location_name: 'Near Pine St Intersection',
                    next_stop_id: 'Stop_B',
                    manual_eta: '08:20 AM'
                })
            })
            .then(() => fetch('/api/simulation/tick', { method: 'POST' }))
            .then(() => {
                refreshSimState();
                const desc = document.getElementById('demo-step-desc');
                if (desc) {
                    desc.innerHTML += ' <a href="/eta_history" class="btn btn-sm btn-outline-info ms-2"><i class="fa-solid fa-history me-1"></i>View in ETA History</a>';
                }
            });
        }
    }
];

let currentDemoIndex = -1;

function startDemoScenario() {
    currentDemoIndex = 0;
    const bar = document.getElementById('demo-scenario-bar');
    bar.classList.remove('d-none');
    runDemoStep();
}

function runDemoStep() {
    if (currentDemoIndex < 0 || currentDemoIndex >= demoSteps.length) {
        closeDemoScenario();
        return;
    }
    const step = demoSteps[currentDemoIndex];
    document.getElementById('demo-step-num').innerText = `Step ${step.stepNum}`;
    document.getElementById('demo-step-title').innerText = step.title;
    document.getElementById('demo-step-desc').innerText = step.desc;
    
    // Execute action
    step.action();
}

function nextDemoStep() {
    currentDemoIndex++;
    if (currentDemoIndex >= demoSteps.length) {
        closeDemoScenario();
    } else {
        runDemoStep();
    }
}

function closeDemoScenario() {
    document.getElementById('demo-scenario-bar').classList.add('d-none');
    currentDemoIndex = -1;
    pauseSimulation();
}

// Bind events on mount
document.addEventListener('DOMContentLoaded', () => {
    refreshSimState();

    document.getElementById('btn-sim-start').addEventListener('click', startSimulation);
    document.getElementById('btn-sim-pause').addEventListener('click', pauseSimulation);
    document.getElementById('btn-sim-tick').addEventListener('click', tickSimulation);
    document.getElementById('btn-sim-reset').addEventListener('click', resetSimulation);
    document.getElementById('btn-run-demo').addEventListener('click', startDemoScenario);
    
    const nextBtn = document.getElementById('btn-demo-next');
    if (nextBtn) nextBtn.addEventListener('click', nextDemoStep);

    const closeBtn = document.getElementById('btn-demo-close');
    if (closeBtn) closeBtn.addEventListener('click', closeDemoScenario);
});
