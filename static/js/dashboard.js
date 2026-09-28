// Dashboard logic loader
function loadDashboardData() {
    // 1. Fetch Buses status
    fetch('/api/buses')
        .then(res => res.json())
        .then(buses => {
            const tbody = document.getElementById('dashboard-buses-table');
            if (buses.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No bus registry.</td></tr>';
                return;
            }

            let activeCount = 0;
            let onTimeCount = 0;
            let delayedCount = 0;
            let totalBuses = buses.length;

            let html = '';
            buses.forEach(b => {
                const isActive = b.status !== 'INACTIVE';
                if (isActive) activeCount++;

                let statusBadge = '';
                if (b.status === 'INACTIVE') {
                    statusBadge = '<span class="badge bg-secondary">Inactive</span>';
                } else if (b.status === 'COMPLETED') {
                    statusBadge = '<span class="badge bg-success">Completed</span>';
                } else if (b.status === 'DWELLING') {
                    statusBadge = '<span class="badge bg-info text-white">Dwelling</span>';
                } else {
                    statusBadge = '<span class="badge bg-primary">On Route</span>';
                }

                let delayText = 'On Time';
                let delayClass = 'text-success';
                let whyExplanation = b.explanation || 'Bus is currently on schedule.';

                if (isActive) {
                    if (b.delay > 1) {
                        delayedCount++;
                        delayText = `+${b.delay} mins`;
                        delayClass = 'text-danger font-weight-bold';
                        if (b.primary_reason === 'UNKNOWN_CAUSE') {
                            whyExplanation = 'Delay detected, but the cause could not be determined from available telemetry.';
                        }
                    } else if (b.delay < -1) {
                        delayText = `${Math.abs(Math.round(b.delay_minutes || 0))}m early`;
                        delayClass = 'text-info font-weight-bold';
                    } else {
                        onTimeCount++;
                        delayText = 'On Time';
                        whyExplanation = 'Bus is currently on schedule.';
                    }
                } else {
                    whyExplanation = 'Inactive bus.';
                }

                html += `
                    <tr>
                        <td><strong>Bus ${b.bus_id}</strong></td>
                        <td>${b.driver_name}</td>
                        <td>${b.route_id}</td>
                        <td><span class="small">${b.next_stop_name}</span></td>
                        <td><strong class="text-primary">${b.eta}</strong></td>
                        <td><span class="${delayClass}">${delayText}</span></td>
                        <td>${statusBadge}</td>
                        <td><span class="small fst-italic text-secondary">${whyExplanation}</span></td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;


            // Set KPIs
            document.getElementById('kpi-total-buses').innerText = totalBuses;
            document.getElementById('kpi-active-buses').innerText = activeCount;
            document.getElementById('kpi-ontime-buses').innerText = onTimeCount;
            document.getElementById('kpi-delayed-buses').innerText = delayedCount;
        });

    // 2. Fetch history for ETA updates counter, enquiries, traffic, failures
    Promise.all([
        fetch('/api/history/all').then(res => res.json()),
        fetch('/api/failures').then(res => res.json()),
        fetch('/api/experiment/results').then(res => res.json())
    ]).then(([history, failures, expResults]) => {
        // ETA Updates KPI
        const updatesCount = history.filter(h => h.source === 'AUTO').length;
        document.getElementById('kpi-eta-updates').innerText = updatesCount;

        // Status Enquiries KPI (derived from experiment metrics or real logs)
        // Let's count matching logs or check experiment results
        let enquiriesCount = 0;
        if (expResults && expResults.metrics) {
            const row = expResults.metrics.find(m => m.metric_name === 'Status Enquiries');
            if (row) enquiriesCount = parseInt(row.proposed_value);
        }
        document.getElementById('kpi-status-enquiries').innerText = enquiriesCount;

        // Traffic Delay KPI (average of last delay log)
        let trafficText = '0 mins';
        if (history.length > 0) {
            const lastLog = history[0];
            if (lastLog.traffic_level === 'HIGH') {
                trafficText = '7 mins';
            } else if (lastLog.traffic_level === 'MEDIUM') {
                trafficText = '3 mins';
            }
        }
        document.getElementById('kpi-traffic-delay').innerText = trafficText;

        // Active Failures KPI
        const activeFailCount = Object.values(failures).filter(v => v === 'ACTIVE').length;
        document.getElementById('kpi-active-failures').innerText = activeFailCount;

        // 3. Render live explanations log
        const logFeed = document.getElementById('dashboard-explanations-feed');
        // Filter out manual overrides, just explain automated changes
        const explanationLogs = history.filter(h => h.reason && h.reason.trim());
        
        if (explanationLogs.length === 0) {
            logFeed.innerHTML = '<div class="text-center text-muted py-4 small">No updates logged. Run simulation steps.</div>';
            return;
        }

        let logsHtml = '';
        explanationLogs.slice(0, 10).forEach(log => {
            let classType = 'INFO';
            if (log.delay_minutes >= 5.0) {
                classType = 'CRITICAL';
            } else if (log.delay_minutes >= 2.0) {
                classType = 'WARNING';
            }

            const prefix = classType === 'CRITICAL' ? '🔴' : (classType === 'WARNING' ? '🟡' : '🟢');

            logsHtml += `
                <div class="notification-item ${classType}">
                    <span class="notification-time font-weight-bold">${log.timestamp} - Bus ${log.bus_id} (${log.route_id})</span>
                    <span class="d-block font-weight-bold">${prefix} ETA changed to ${log.new_eta}</span>
                    <p class="m-0 text-muted small mt-1">Factors: ${log.reason}</p>
                </div>
            `;
        });
        logFeed.innerHTML = logsHtml;
    });
}

// Attach load to window
window.loadDashboardData = loadDashboardData;

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    // Poll updates every 4 seconds
    setInterval(loadDashboardData, 4000);
});
