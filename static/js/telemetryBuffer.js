/**
 * telemetryBuffer.js
 * Browser-ready IndexedDB Store-and-Forward Telemetry Buffer.
 * Database: busTelemetryDB
 * Object Store: telemetry_queue
 */

(function (window) {
    'use strict';

    const DB_NAME = 'busTelemetryDB';
    const DB_VERSION = 1;
    const STORE_NAME = 'telemetry_queue';

    let dbPromise = null;
    let isSyncing = false;

    function initDB() {
        if (dbPromise) return dbPromise;

        dbPromise = new Promise((resolve, reject) => {
            if (!('indexedDB' in window)) {
                console.warn('IndexedDB not supported by this browser.');
                return resolve(null);
            }

            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onupgradeneeded = function (event) {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const store = db.createObjectStore(STORE_NAME, { keyPath: 'event_id' });
                    store.createIndex('status', 'status', { unique: false });
                    store.createIndex('bus_id', 'bus_id', { unique: false });
                    store.createIndex('timestamp', 'timestamp', { unique: false });
                    store.createIndex('created_at', 'created_at', { unique: false });
                }
            };

            request.onsuccess = function (event) {
                resolve(event.target.result);
            };

            request.onerror = function (event) {
                console.error('Failed to open busTelemetryDB:', event.target.error);
                reject(event.target.error);
            };
        });

        return dbPromise;
    }

    function generateUUID() {
        if (typeof crypto !== 'undefined' && crypto.randomUUID) {
            return crypto.randomUUID();
        }
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function enqueueTelemetry(telemetry) {
        return initDB().then(db => {
            if (!db) return null;
            const eventId = telemetry.event_id || generateUUID();
            const record = {
                event_id: eventId,
                bus_id: telemetry.bus_id || '101',
                timestamp: telemetry.timestamp || new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
                latitude: parseFloat(telemetry.latitude) || 37.7949,
                longitude: parseFloat(telemetry.longitude) || -122.4394,
                speed: parseFloat(telemetry.speed) || 30.0,
                route_id: telemetry.route_id || 'Route 1',
                trip_id: telemetry.trip_id || 'TRIP-Route1',
                status: 'PENDING',
                retry_count: 0,
                created_at: new Date().toISOString()
            };

            return new Promise((resolve, reject) => {
                const tx = db.transaction([STORE_NAME], 'readwrite');
                const store = tx.objectStore(STORE_NAME);
                const req = store.put(record);
                req.onsuccess = () => {
                    notifyQueueChanged();
                    resolve(record);
                };
                req.onerror = () => reject(req.error);
            });
        });
    }

    function getPendingQueue() {
        return initDB().then(db => {
            if (!db) return [];
            return new Promise((resolve, reject) => {
                const tx = db.transaction([STORE_NAME], 'readonly');
                const store = tx.objectStore(STORE_NAME);
                const req = store.getAll();
                req.onsuccess = () => {
                    const records = req.result || [];
                    resolve(records.sort((a, b) => a.created_at.localeCompare(b.created_at)));
                };
                req.onerror = () => reject(req.error);
            });
        });
    }

    function getQueueCount() {
        return initDB().then(db => {
            if (!db) return 0;
            return new Promise((resolve, reject) => {
                const tx = db.transaction([STORE_NAME], 'readonly');
                const store = tx.objectStore(STORE_NAME);
                const req = store.count();
                req.onsuccess = () => resolve(req.result);
                req.onerror = () => reject(req.error);
            });
        });
    }

    function removeRecord(eventId) {
        return initDB().then(db => {
            if (!db) return;
            return new Promise((resolve, reject) => {
                const tx = db.transaction([STORE_NAME], 'readwrite');
                const store = tx.objectStore(STORE_NAME);
                const req = store.delete(eventId);
                req.onsuccess = () => {
                    notifyQueueChanged();
                    resolve();
                };
                req.onerror = () => reject(req.error);
            });
        });
    }

    function incrementRetry(eventId, errorMsg) {
        return initDB().then(db => {
            if (!db) return;
            return new Promise((resolve, reject) => {
                const tx = db.transaction([STORE_NAME], 'readwrite');
                const store = tx.objectStore(STORE_NAME);
                const getReq = store.get(eventId);
                getReq.onsuccess = () => {
                    const record = getReq.result;
                    if (record) {
                        record.retry_count = (record.retry_count || 0) + 1;
                        record.last_error = errorMsg;
                        record.status = 'PENDING';
                        store.put(record);
                    }
                    resolve();
                };
                getReq.onerror = () => reject(getReq.error);
            });
        });
    }

    function clearQueue() {
        return initDB().then(db => {
            if (!db) return;
            return new Promise((resolve, reject) => {
                const tx = db.transaction([STORE_NAME], 'readwrite');
                const store = tx.objectStore(STORE_NAME);
                const req = store.clear();
                req.onsuccess = () => {
                    notifyQueueChanged();
                    resolve();
                };
                req.onerror = () => reject(req.error);
            });
        });
    }

    /**
     * Checks if simulator network failure is active.
     */
    function isNetworkFailureActive() {
        return fetch('/api/failures')
            .then(res => res.json())
            .then(failures => failures['network'] === 'ACTIVE')
            .catch(() => false);
    }

    /**
     * Send or buffer telemetry:
     * Attempts direct POST /api/telemetry.
     * If browser is offline, or failure simulation is active, or API call fails,
     * buffers safely to IndexedDB.
     */
    function sendOrBufferTelemetry(telemetry) {
        const eventId = telemetry.event_id || generateUUID();
        const payload = Object.assign({}, telemetry, { event_id: eventId });

        return isNetworkFailureActive().then(isOffline => {
            if (!navigator.onLine || isOffline) {
                console.warn('Network offline. Buffering telemetry into IndexedDB queue:', eventId);
                return enqueueTelemetry(payload).then(queued => ({
                    status: 'BUFFERED',
                    data: queued
                }));
            }

            return fetch('/api/telemetry', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(resData => ({
                status: 'SENT',
                data: resData
            }))
            .catch(err => {
                console.warn('Transmission failed (' + err.message + '). Buffering into IndexedDB:', eventId);
                return enqueueTelemetry(payload).then(queued => ({
                    status: 'BUFFERED',
                    data: queued
                }));
            });
        });
    }

    /**
     * Synchronizes all buffered records from IndexedDB to /api/telemetry/sync.
     */
    function syncQueue() {
        if (isSyncing) return Promise.resolve({ isSyncing: true });

        return isNetworkFailureActive().then(isOffline => {
            if (!navigator.onLine || isOffline) {
                return { success: false, reason: 'NETWORK_OFFLINE' };
            }

            return getPendingQueue().then(pending => {
                if (!pending || pending.length === 0) {
                    return { success: true, count: 0 };
                }

                isSyncing = true;
                notifySyncStatus('SYNCING', pending.length);

                return fetch('/api/telemetry/sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ batch: pending })
                })
                .then(res => {
                    if (!res.ok) throw new Error('Sync failed with HTTP ' + res.status);
                    return res.json();
                })
                .then(result => {
                    const tasks = [];
                    if (result.results && Array.isArray(result.results)) {
                        result.results.forEach(item => {
                            if (item.status === 'SUCCESS' || item.status === 'DUPLICATE') {
                                tasks.push(removeRecord(item.event_id));
                            } else {
                                tasks.push(incrementRetry(item.event_id, item.error || 'Server error'));
                            }
                        });
                    }
                    return Promise.all(tasks).then(() => {
                        isSyncing = false;
                        notifySyncStatus('IDLE', 0);
                        notifyQueueChanged();
                        return result;
                    });
                })
                .catch(err => {
                    console.error('Batch telemetry sync failed:', err);
                    const retryTasks = pending.map(item => incrementRetry(item.event_id, err.message));
                    return Promise.all(retryTasks).then(() => {
                        isSyncing = false;
                        notifySyncStatus('ERROR', pending.length);
                        notifyQueueChanged();
                        return { success: false, error: err.message };
                    });
                });
            });
        });
    }

    function notifyQueueChanged() {
        getQueueCount().then(count => {
            const event = new CustomEvent('telemetryQueueChanged', { detail: { count } });
            window.dispatchEvent(event);
            updateUIBadge(count);
        });
    }

    function notifySyncStatus(status, count) {
        const event = new CustomEvent('telemetrySyncStatus', { detail: { status, count } });
        window.dispatchEvent(event);
    }

    function updateUIBadge(count) {
        const badge = document.getElementById('indexeddb-queue-count');
        if (badge) {
            badge.innerText = count;
            badge.className = count > 0 ? 'badge bg-warning text-dark' : 'badge bg-secondary';
        }
    }

    // Auto-sync listeners
    window.addEventListener('online', function () {
        console.log('Online event detected. Attempting telemetry queue sync...');
        syncQueue();
    });

    setInterval(function () {
        getQueueCount().then(count => {
            if (count > 0 && navigator.onLine) {
                syncQueue();
            }
        });
    }, 5000);

    // Initial check on load
    document.addEventListener('DOMContentLoaded', function () {
        initDB().then(() => notifyQueueChanged());
    });

    // Expose API globally
    window.TelemetryBuffer = {
        initDB: initDB,
        generateUUID: generateUUID,
        enqueue: enqueueTelemetry,
        getPendingQueue: getPendingQueue,
        getQueueCount: getQueueCount,
        remove: removeRecord,
        incrementRetry: incrementRetry,
        clear: clearQueue,
        sendOrBufferTelemetry: sendOrBufferTelemetry,
        syncQueue: syncQueue
    };

})(window);
