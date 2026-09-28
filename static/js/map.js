// Leaflet map integrations
let map;
let busMarkers = {};
let routeLines = {};
let stopCircles = [];

const routeColors = {
    'Route 1': '#2b5c8f', // Blue
    'Route 2': '#2e7d32', // Green
    'Route 3': '#7b1fa2'  // Purple
};

function initMap() {
    // Center of San Francisco (our school coordinate center)
    map = L.map('map').setView([37.7749, -122.4194], 13);
    
    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Fetch and draw static routes & stops
    fetch('/api/routes')
        .then(res => res.json())
        .then(routes => {
            routes.forEach(route => {
                const color = routeColors[route.route_id] || '#868e96';
                const latlns = [];

                route.stops.forEach(stop => {
                    latlns.push([stop.latitude, stop.longitude]);
                    
                    // Draw stop circle
                    const isSchool = stop.stop_name.toLowerCase().includes('school');
                    const circle = L.circle([stop.latitude, stop.longitude], {
                        color: color,
                        fillColor: isSchool ? '#c62828' : '#fff',
                        fillOpacity: 0.8,
                        radius: isSchool ? 100 : 50
                    }).addTo(map);

                    circle.bindPopup(`<strong>Stop: ${stop.stop_name}</strong><br>Route: ${route.route_id}<br>Planned Arrival: ${stop.planned_arrival_time}`);
                    stopCircles.push(circle);
                });

                // Draw route line
                const polyline = L.polyline(latlns, {
                    color: color,
                    weight: 5,
                    opacity: 0.6
                }).addTo(map);
                
                routeLines[route.route_id] = polyline;
            });

            // Trigger initial buses update
            loadMapData();
        });
}

function loadMapData() {
    if (!map) return;

    fetch('/api/buses')
        .then(res => res.json())
        .then(buses => {
            const listContainer = document.getElementById('tracking-buses-list');
            if (listContainer) listContainer.innerHTML = '';

            // Update GPS failure warning
            fetch('/api/failures')
                .then(r => r.json())
                .then(failures => {
                    const isGpsOffline = failures['gps'] === 'ACTIVE';
                    const badge = document.getElementById('map-connection-badge');
                    if (badge) {
                        if (isGpsOffline) {
                            badge.className = 'badge bg-danger';
                            badge.innerText = 'GPS OFFLINE - Using Last Known Coordinates';
                        } else {
                            badge.className = 'badge bg-secondary';
                            badge.innerText = 'GPS Feed: Online (OpenStreetMap)';
                        }
                    }
                });

            buses.forEach(b => {
                const isActive = b.status !== 'INACTIVE';
                const lat = b.current_latitude;
                const lon = b.current_longitude;
                
                // 1. Update Bus Marker on Leaflet
                if (isActive) {
                    const color = routeColors[b.route_id] || '#868e96';
                    
                    // Custom bus HTML marker
                    const busIcon = L.divIcon({
                        html: `<div style="background-color: ${color}; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 5px rgba(0,0,0,0.3); color: white; font-weight: bold; font-size: 11px;"><i class="fa-solid fa-bus"></i></div>`,
                        className: 'custom-bus-marker',
                        iconSize: [32, 32],
                        iconAnchor: [16, 16]
                    });

                    if (busMarkers[b.bus_id]) {
                        busMarkers[b.bus_id].setLatLng([lat, lon]);
                    } else {
                        busMarkers[b.bus_id] = L.marker([lat, lon], { icon: busIcon }).addTo(map);
                    }

                    // Visual status indicator helper
                    let etaStatus = b.eta_status || (b.delay > 1 ? 'DELAYED' : (b.delay < -1 ? 'EARLY' : 'ON_TIME'));
                    let statusBadge = '';
                    let delayIndicatorText = '';
                    let whyText = b.explanation || '';

                    if (etaStatus === 'ON_TIME' || b.delay <= 1) {
                        statusBadge = '<span class="badge bg-success text-white"><i class="fa-solid fa-circle-check me-1"></i>ON TIME</span>';
                        delayIndicatorText = '<span class="text-success fw-bold">On Schedule</span>';
                        whyText = 'Bus is currently on schedule.';
                    } else if (etaStatus === 'DELAYED' || b.delay > 1) {
                        statusBadge = `<span class="badge bg-danger text-white"><i class="fa-solid fa-clock-rotate-left me-1"></i>+${b.delay} min delayed</span>`;
                        delayIndicatorText = `<span class="text-danger fw-bold">+${b.delay} min delayed</span>`;
                        if (b.primary_reason === 'UNKNOWN_CAUSE' || !whyText) {
                            whyText = 'Delay detected, but the cause could not be determined from available telemetry.';
                        }
                    } else if (etaStatus === 'EARLY') {
                        const earlyM = Math.abs(Math.round(b.delay_minutes || 0));
                        statusBadge = `<span class="badge bg-info text-white"><i class="fa-solid fa-forward me-1"></i>${earlyM}m early</span>`;
                        delayIndicatorText = `<span class="text-info fw-bold">${earlyM} min ahead</span>`;
                        whyText = `Bus is running ${earlyM} minutes ahead of schedule.`;
                    } else {
                        statusBadge = '<span class="badge bg-secondary text-white"><i class="fa-solid fa-circle-question me-1"></i>UNKNOWN</span>';
                        delayIndicatorText = '<span class="text-secondary fw-bold">Unknown</span>';
                        whyText = 'Delay detected, but the cause could not be determined from available telemetry.';
                    }

                    // Factors breakdown HTML
                    let factorsHtml = '';
                    if (b.factors && b.factors.length > 0) {
                        factorsHtml = '<div class="mt-1 d-flex flex-wrap gap-1">';
                        b.factors.forEach(f => {
                            factorsHtml += `<span class="badge bg-white text-dark border small" style="font-size: 10px;">${f.factor}: +${f.impact_minutes}m</span>`;
                        });
                        factorsHtml += '</div>';
                    }

                    // Update popup details
                    const popupHtml = `
                        <div style="font-family: 'Inter', sans-serif; width: 230px;">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <h6 style="margin: 0; font-weight: bold; color: #212529;">Bus ${b.bus_id}</h6>
                                ${statusBadge}
                            </div>
                            <span style="font-size: 11px; color: #6c757d;">Route: ${b.route_id} • Driver: ${b.driver_name}</span>
                            <hr style="margin: 6px 0;">
                            <div style="font-size: 12px; line-height: 1.5;">
                                <div class="d-flex justify-content-between align-items-baseline mb-1">
                                    <span style="font-size: 11px; font-weight: 700; color: #6c757d; text-transform: uppercase;">ETA</span>
                                    <span style="color: #2b5c8f; font-weight: 700; font-size: 15px;">${b.eta}</span>
                                </div>
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span style="font-size: 11px; color: #6c757d;">Delay:</span>
                                    ${delayIndicatorText}
                                </div>
                                <div class="text-muted small"><strong>Next Stop:</strong> ${b.next_stop_name}</div>
                                <div class="text-muted small"><strong>Speed:</strong> ${b.speed.toFixed(1)} km/h</div>
                            </div>
                            <div class="mt-2 pt-2 border-top">
                                <div style="font-size: 11px; font-weight: 700; color: #495057; text-transform: uppercase;">
                                    <i class="fa-solid fa-circle-question text-primary me-1"></i> Why?
                                </div>
                                <div style="font-size: 11.5px; color: #212529; font-style: italic; margin-top: 2px;">
                                    "${whyText}"
                                </div>
                            </div>
                        </div>
                    `;
                    busMarkers[b.bus_id].bindPopup(popupHtml);
                } else {
                    // Remove inactive bus markers
                    if (busMarkers[b.bus_id]) {
                        map.removeLayer(busMarkers[b.bus_id]);
                        delete busMarkers[b.bus_id];
                    }
                }

                // 2. Render Bus Registry sidecard list
                if (listContainer) {
                    let sideHtml = '';
                    if (isActive) {
                        let etaStatus = b.eta_status || (b.delay > 1 ? 'DELAYED' : (b.delay < -1 ? 'EARLY' : 'ON_TIME'));
                        let statusBadge = '';
                        let whyText = b.explanation || '';

                        if (etaStatus === 'ON_TIME' || b.delay <= 1) {
                            statusBadge = '<span class="badge bg-success text-white"><i class="fa-solid fa-circle-check me-1"></i>ON TIME</span>';
                            whyText = 'Bus is currently on schedule.';
                        } else if (etaStatus === 'DELAYED' || b.delay > 1) {
                            statusBadge = `<span class="badge bg-danger text-white"><i class="fa-solid fa-clock-rotate-left me-1"></i>+${b.delay} min delayed</span>`;
                            if (b.primary_reason === 'UNKNOWN_CAUSE' || !whyText) {
                                whyText = 'Delay detected, but the cause could not be determined from available telemetry.';
                            }
                        } else if (etaStatus === 'EARLY') {
                            const earlyM = Math.abs(Math.round(b.delay_minutes || 0));
                            statusBadge = `<span class="badge bg-info text-white"><i class="fa-solid fa-forward me-1"></i>${earlyM}m early</span>`;
                            whyText = `Bus is running ${earlyM} minutes ahead of schedule.`;
                        } else {
                            statusBadge = '<span class="badge bg-secondary text-white"><i class="fa-solid fa-circle-question me-1"></i>UNKNOWN</span>';
                            whyText = 'Delay detected, but the cause could not be determined from available telemetry.';
                        }

                        let factorsHtml = '';
                        if (b.factors && b.factors.length > 0) {
                            factorsHtml = '<div class="mt-1 d-flex flex-wrap gap-1">';
                            b.factors.forEach(f => {
                                factorsHtml += `<span class="badge bg-white text-dark border" style="font-size: 10px;">${f.factor}: +${f.impact_minutes}m</span>`;
                            });
                            factorsHtml += '</div>';
                        }
                        
                        sideHtml = `
                            <div class="list-group-item py-3 border-0 border-bottom">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <div>
                                        <strong class="d-block text-dark"><i class="fa-solid fa-bus text-primary me-1"></i> Bus ${b.bus_id}</strong>
                                        <span class="text-muted small">${b.route_id} • Next: ${b.next_stop_name}</span>
                                    </div>
                                    <div class="text-end">
                                        <span class="text-muted small d-block" style="font-size: 10px; font-weight: 700; text-transform: uppercase;">ETA</span>
                                        <strong class="text-primary d-block fs-5" style="line-height: 1.1;">${b.eta}</strong>
                                        <div class="mt-1">${statusBadge}</div>
                                    </div>
                                </div>
                                <div class="p-2 rounded bg-light border" style="font-size: 12px;">
                                    <div class="fw-bold text-secondary mb-1" style="font-size: 11px;">
                                        <i class="fa-solid fa-circle-question text-primary me-1"></i> Why?
                                    </div>
                                    <div class="text-dark fst-italic">"${whyText}"</div>
                                    ${factorsHtml}
                                </div>
                                <div class="mt-2 text-end">
                                    <button class="btn btn-sm btn-outline-primary py-0 px-2" style="font-size: 11px;" onclick="focusBus('${b.bus_id}', ${lat}, ${lon})">
                                        <i class="fa-solid fa-crosshairs me-1"></i> Focus Map
                                    </button>
                                </div>
                            </div>
                        `;
                    } else {
                        sideHtml = `
                            <div class="list-group-item text-muted py-2 small border-0 border-bottom">
                                <i class="fa-regular fa-circle-dot me-1"></i> Bus ${b.bus_id} (${b.driver_name}) is currently <span class="badge bg-secondary">Inactive</span>
                            </div>
                        `;
                    }
                    listContainer.innerHTML += sideHtml;
                }
            });
        });
}

function focusBus(busId, lat, lon) {
    if (map && busMarkers[busId]) {
        map.setView([lat, lon], 15);
        busMarkers[busId].openPopup();
    }
}


// Bind Manual fallback choices helper
const manualBusSelect = document.getElementById('select-manual-bus');
if (manualBusSelect) {
    manualBusSelect.addEventListener('change', function() {
        const busId = this.value;
        const stopSelect = document.getElementById('select-manual-next-stop');
        stopSelect.innerHTML = '<option value="" disabled selected>Loading stops...</option>';
        
        fetch('/api/routes')
            .then(res => res.json())
            .then(routes => {
                const route = routes.find(r => r.route_id === `Route ${busId.charAt(2)}` || r.route_id === `Route ${busId.slice(-1)}`);
                if (route) {
                    let options = '<option value="" disabled selected>Select next stop...</option>';
                    route.stops.forEach(s => {
                        options += `<option value="${s.stop_id}">${s.stop_name} (Planned: ${s.planned_arrival_time})</option>`;
                    });
                    stopSelect.innerHTML = options;
                }
            });
    });
}

// Manual fallback form submission
const fallbackForm = document.getElementById('form-manual-fallback');
if (fallbackForm) {
    fallbackForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const payload = {
            bus_id: document.getElementById('select-manual-bus').value,
            location_name: document.getElementById('input-manual-location').value,
            next_stop_id: document.getElementById('select-manual-next-stop').value,
            manual_eta: document.getElementById('input-manual-eta').value
        };

        fetch('/api/manual-eta', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Clear fields
                document.getElementById('input-manual-location').value = '';
                document.getElementById('input-manual-eta').value = '';
                document.getElementById('select-manual-bus').value = '';
                document.getElementById('select-manual-next-stop').innerHTML = '<option value="" disabled selected>Select next stop...</option>';

                // Show alert message
                const msg = document.getElementById('manual-fallback-message');
                msg.classList.remove('d-none');
                setTimeout(() => {
                    msg.classList.add('d-none');
                }, 4000);
                
                loadMapData();
            } else {
                alert("Failed to submit manual fallback update.");
            }
        });
    });
}

// Store-and-Forward Telemetry Simulation & Buffer handlers
function updateMapBufferCount() {
    if (window.TelemetryBuffer) {
        window.TelemetryBuffer.getQueueCount().then(count => {
            const countEl = document.getElementById('live-buffer-count');
            if (countEl) countEl.innerText = count;
        });
    }
}

window.addEventListener('telemetryQueueChanged', function(e) {
    const countEl = document.getElementById('live-buffer-count');
    if (countEl && e.detail) {
        countEl.innerText = e.detail.count;
    }
});

const btnSendTelemetry = document.getElementById('btn-send-sim-telemetry');
if (btnSendTelemetry) {
    btnSendTelemetry.addEventListener('click', function() {
        if (!window.TelemetryBuffer) return;
        
        const simLat = 37.7949 + (Math.random() - 0.5) * 0.008;
        const simLon = -122.4394 + (Math.random() - 0.5) * 0.008;
        const simSpeed = 25.0 + Math.random() * 10.0;
        
        const telemetry = {
            event_id: window.TelemetryBuffer.generateUUID(),
            bus_id: '101',
            route_id: 'Route 1',
            trip_id: 'TRIP-Route1',
            latitude: simLat,
            longitude: simLon,
            speed: parseFloat(simSpeed.toFixed(1))
        };

        const alertBox = document.getElementById('telemetry-buffer-alert');
        btnSendTelemetry.disabled = true;

        window.TelemetryBuffer.sendOrBufferTelemetry(telemetry)
            .then(res => {
                btnSendTelemetry.disabled = false;
                if (alertBox) {
                    alertBox.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-info');
                    if (res.status === 'SENT') {
                        alertBox.classList.add('alert-success');
                        alertBox.innerHTML = `<strong><i class="fa-solid fa-circle-check me-1"></i> Sent Live:</strong> Bus 101 GPS ingested. New ETA: <strong>${res.data.eta || 'N/A'}</strong>`;
                    } else {
                        alertBox.classList.add('alert-warning');
                        alertBox.innerHTML = `<strong><i class="fa-solid fa-hard-drive me-1"></i> Offline Mode:</strong> Telemetry buffered in IndexedDB (<code>busTelemetryDB</code>). Event ID: <code>${res.data.event_id.slice(0, 8)}...</code>`;
                    }
                    setTimeout(() => alertBox.classList.add('d-none'), 5000);
                }
                updateMapBufferCount();
                loadMapData();
            })
            .catch(err => {
                btnSendTelemetry.disabled = false;
                console.error("Telemetry send error:", err);
            });
    });
}

const btnSyncBuffer = document.getElementById('btn-sync-buffer');
if (btnSyncBuffer) {
    btnSyncBuffer.addEventListener('click', function() {
        if (!window.TelemetryBuffer) return;
        btnSyncBuffer.disabled = true;
        const alertBox = document.getElementById('telemetry-buffer-alert');

        window.TelemetryBuffer.syncQueue()
            .then(res => {
                btnSyncBuffer.disabled = false;
                if (alertBox) {
                    alertBox.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-info');
                    if (res.reason === 'NETWORK_OFFLINE') {
                        alertBox.classList.add('alert-warning');
                        alertBox.innerHTML = '<i class="fa-solid fa-triangle-exclamation me-1"></i> Cannot sync: Network failure state is active.';
                    } else if (res.synced_count > 0 || res.duplicate_count > 0) {
                        alertBox.classList.add('alert-success');
                        alertBox.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> Synchronized <strong>${res.synced_count}</strong> events (${res.duplicate_count} deduplicated).`;
                    } else {
                        alertBox.classList.add('alert-info');
                        alertBox.innerHTML = '<i class="fa-solid fa-circle-info me-1"></i> Queue is empty. No pending telemetry to sync.';
                    }
                    setTimeout(() => alertBox.classList.add('d-none'), 5000);
                }
                updateMapBufferCount();
                loadMapData();
            })
            .catch(err => {
                btnSyncBuffer.disabled = false;
                console.error("Sync error:", err);
            });
    });
}

// Attach load to window
window.loadMapData = loadMapData;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    updateMapBufferCount();
    // Poll map data updates every 4 seconds
    setInterval(loadMapData, 4000);
});

