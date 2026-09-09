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

                    // Update popup details
                    const popupHtml = `
                        <div style="font-family: 'Inter', sans-serif; width: 200px;">
                            <h6 style="margin: 0 0 5px 0; font-weight: bold; color: #212529;">Bus ${b.bus_id}</h6>
                            <span style="font-size: 12px; color: #6c757d;">Driver: ${b.driver_name}</span>
                            <hr style="margin: 5px 0;">
                            <div style="font-size: 12px; line-height: 1.5;">
                                <strong>Route:</strong> ${b.route_id}<br>
                                <strong>Speed:</strong> ${b.speed.toFixed(1)} km/h<br>
                                <strong>Next Stop:</strong> ${b.next_stop_name}<br>
                                <strong>ETA:</strong> <span style="color: #2b5c8f; font-weight: bold;">${b.eta}</span><br>
                                <strong>Delay:</strong> <span style="color: ${b.delay > 0 ? '#c62828' : '#2e7d32'}; font-weight: bold;">${b.delay > 0 ? '+' + b.delay + ' min' : '0 min'}</span><br>
                                <strong>Status:</strong> ${b.status}
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
                        const delayBadge = b.delay > 0 ? 
                            `<span class="badge bg-danger ms-2">+${b.delay}m</span>` : 
                            `<span class="badge bg-success ms-2">On Time</span>`;
                        
                        sideHtml = `
                            <a href="#" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center py-3 border-0 border-bottom" onclick="focusBus('${b.bus_id}', ${lat}, ${lon})">
                                <div>
                                    <strong class="d-block text-dark"><i class="fa-solid fa-bus text-muted me-1"></i> Bus ${b.bus_id}</strong>
                                    <span class="text-muted small">Heading to: ${b.next_stop_name}</span>
                                </div>
                                <div class="text-end">
                                    <strong class="text-primary d-block">${b.eta}</strong>
                                    ${delayBadge}
                                </div>
                            </a>
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

// Attach load to window
window.loadMapData = loadMapData;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    // Poll map data updates every 4 seconds
    setInterval(loadMapData, 4000);
});
