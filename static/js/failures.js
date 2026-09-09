/**
 * failures.js
 * Manages Failure Injection (GPS, Network, Traffic, Sensor)
 * and Store-and-Forward synchronization monitoring.
 */

function checkFailureStatus() {
    fetch('/api/failures')
        .then(res => res.json())
        .then(failures => {
            Object.keys(failures).forEach(key => {
                const isActive = failures[key] === 'ACTIVE';
                const checkbox = document.getElementById(`switch-fail-${key}`);
                const alertEl = document.getElementById(`alert-fail-${key}`);
                
                if (checkbox) checkbox.checked = isActive;
                if (alertEl) {
                    if (isActive) {
                        alertEl.classList.remove('d-none');
                    } else {
                        alertEl.classList.add('d-none');
                    }
                }
            });
        })
        .catch(err => console.error("Error loading failure states:", err));

    fetch('/api/simulation/state')
        .then(res => res.json())
        .then(state => {
            const queue = state.store_and_forward_queue || [];
            const queueEl = document.getElementById('span-queue-count');
            if (queueEl) {
                queueEl.innerText = queue.length;
            }
        })
        .catch(err => console.error("Error loading simulation state:", err));
}

function toggleFailure(caseName, isActive) {
    fetch(`/api/failure/${caseName}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ active: isActive })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            checkFailureStatus();
            if (caseName === 'network' && !isActive && data.synchronized_count > 0) {
                alert(`${data.synchronized_count} events synchronized successfully from store-and-forward queue!`);
            }
            if (window.refreshSimState) {
                window.refreshSimState();
            }
        } else {
            alert("Failed to toggle failure status.");
        }
    })
    .catch(err => {
        console.error("Failed to toggle failure:", err);
        alert("Failed to toggle failure status.");
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const navFailures = document.getElementById('nav-failures');
    if (navFailures) navFailures.classList.add('active');
    
    checkFailureStatus();
    setInterval(checkFailureStatus, 3000);
});
