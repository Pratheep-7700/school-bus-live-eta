/**
 * telemetryBuffer.ts
 * Client-Side Persistent Store-and-Forward Telemetry Buffer using IndexedDB.
 * Handles offline buffering, unique event deduplication, and automatic resynchronization.
 */

export interface TelemetryRecord {
  event_id: string;
  bus_id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  speed: number;
  route_id?: string;
  trip_id?: string;
  status: 'PENDING' | 'SYNCED' | 'FAILED';
  retry_count: number;
  created_at: string;
  last_error?: string;
}

export interface SyncResult {
  success: boolean;
  synced_count: number;
  duplicate_count: number;
  error_count: number;
  pending_remaining: number;
}

const DB_NAME = 'busTelemetryDB';
const DB_VERSION = 1;
const STORE_NAME = 'telemetry_queue';

class TelemetryBufferService {
  private dbPromise: Promise<IDBDatabase> | null = null;
  private isSyncing = false;

  constructor() {
    if (typeof window !== 'undefined' && 'indexedDB' in window) {
      this.initDB();
      this.setupAutoSync();
    }
  }

  /**
   * Initializes or opens the IndexedDB database.
   */
  public async initDB(): Promise<IDBDatabase> {
    if (this.dbPromise) {
      return this.dbPromise;
    }

    this.dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = (event: IDBVersionChangeEvent) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: 'event_id' });
          store.createIndex('status', 'status', { unique: false });
          store.createIndex('bus_id', 'bus_id', { unique: false });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('created_at', 'created_at', { unique: false });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    return this.dbPromise;
  }

  /**
   * Generates an RFC4122 v4 UUID for unique event identification.
   */
  public generateEventId(): string {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  /**
   * Enqueues a telemetry payload into the persistent IndexedDB store.
   */
  public async enqueue(telemetry: Omit<TelemetryRecord, 'event_id' | 'status' | 'retry_count' | 'created_at'> & { event_id?: string }): Promise<TelemetryRecord> {
    const db = await this.initDB();
    const record: TelemetryRecord = {
      event_id: telemetry.event_id || this.generateEventId(),
      bus_id: telemetry.bus_id,
      timestamp: telemetry.timestamp || new Date().toISOString(),
      latitude: telemetry.latitude,
      longitude: telemetry.longitude,
      speed: telemetry.speed,
      route_id: telemetry.route_id,
      trip_id: telemetry.trip_id,
      status: 'PENDING',
      retry_count: 0,
      created_at: new Date().toISOString()
    };

    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.put(record);

      request.onsuccess = () => {
        this.notifyQueueChanged();
        resolve(record);
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Returns all telemetry events currently queued in IndexedDB.
   */
  public async getPendingQueue(): Promise<TelemetryRecord[]> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => {
        const records: TelemetryRecord[] = request.result || [];
        // Return sorted by creation time
        resolve(records.sort((a, b) => a.created_at.localeCompare(b.created_at)));
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Returns the count of pending items in the queue.
   */
  public async getQueueCount(): Promise<number> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.count();

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Removes a successfully synchronized event from the queue.
   */
  public async remove(eventId: string): Promise<void> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(eventId);

      request.onsuccess = () => {
        this.notifyQueueChanged();
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Increments retry count and updates error status for retryable failures.
   */
  public async incrementRetry(eventId: string, errorMessage: string): Promise<void> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const getReq = store.get(eventId);

      getReq.onsuccess = () => {
        const record = getReq.result as TelemetryRecord;
        if (record) {
          record.retry_count += 1;
          record.last_error = errorMessage;
          record.status = 'PENDING'; // Keep pending for next retry attempt
          store.put(record);
        }
        resolve();
      };
      getReq.onerror = () => reject(getReq.error);
    });
  }

  /**
   * Clears the entire telemetry buffer.
   */
  public async clear(): Promise<void> {
    const db = await this.initDB();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction([STORE_NAME], 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onsuccess = () => {
        this.notifyQueueChanged();
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }

  /**
   * Main store-and-forward telemetry pipeline:
   * Tries to send immediately to backend. If network or server fails,
   * buffers into IndexedDB for automatic later delivery.
   */
  public async sendOrBufferTelemetry(
    telemetry: Omit<TelemetryRecord, 'event_id' | 'status' | 'retry_count' | 'created_at'> & { event_id?: string }
  ): Promise<{ status: 'SENT' | 'BUFFERED'; data: any }> {
    const eventId = telemetry.event_id || this.generateEventId();
    const payload = {
      ...telemetry,
      event_id: eventId
    };

    // If browser is explicitly offline, buffer directly
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      const queued = await this.enqueue(payload);
      return { status: 'BUFFERED', data: queued };
    }

    try {
      const response = await fetch('/api/telemetry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const result = await response.json();
      return { status: 'SENT', data: result };
    } catch (err: any) {
      console.warn('Network transmission failed. Buffering telemetry into IndexedDB:', err.message);
      const queued = await this.enqueue(payload);
      return { status: 'BUFFERED', data: queued };
    }
  }

  /**
   * Synchronizes all buffered records with the backend API.
   * Duplicate detection on server prevents double-processing.
   */
  public async syncQueue(): Promise<SyncResult> {
    if (this.isSyncing) {
      return { success: false, synced_count: 0, duplicate_count: 0, error_count: 0, pending_remaining: await this.getQueueCount() };
    }

    const pending = await this.getPendingQueue();
    if (pending.length === 0) {
      return { success: true, synced_count: 0, duplicate_count: 0, error_count: 0, pending_remaining: 0 };
    }

    this.isSyncing = true;
    let synced = 0;
    let duplicates = 0;
    let errors = 0;

    try {
      const response = await fetch('/api/telemetry/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch: pending })
      });

      if (!response.ok) {
        throw new Error(`Batch sync failed with HTTP ${response.status}`);
      }

      const result = await response.json();
      if (result.results && Array.isArray(result.results)) {
        for (const item of result.results) {
          if (item.status === 'SUCCESS' || item.status === 'DUPLICATE') {
            if (item.status === 'SUCCESS') synced++;
            if (item.status === 'DUPLICATE') duplicates++;
            if (item.event_id) {
              await this.remove(item.event_id);
            }
          } else {
            errors++;
            if (item.event_id) {
              await this.incrementRetry(item.event_id, item.error || 'Server processing error');
            }
          }
        }
      }
    } catch (error: any) {
      console.error('Store-and-forward batch sync failed. Items will be retried:', error);
      errors = pending.length;
      for (const item of pending) {
        await this.incrementRetry(item.event_id, error.message || 'Network unreachable');
      }
    } finally {
      this.isSyncing = false;
      this.notifyQueueChanged();
    }

    const remaining = await this.getQueueCount();
    const syncRes: SyncResult = {
      success: errors === 0,
      synced_count: synced,
      duplicate_count: duplicates,
      error_count: errors,
      pending_remaining: remaining
    };

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('telemetrySyncCompleted', { detail: syncRes }));
    }

    return syncRes;
  }

  private setupAutoSync(): void {
    if (typeof window === 'undefined') return;

    // Sync when network connectivity returns
    window.addEventListener('online', () => {
      console.log('Network restored. Synchronizing offline telemetry buffer...');
      this.syncQueue();
    });

    // Periodic sync attempt every 6 seconds
    setInterval(async () => {
      if (navigator.onLine && (await this.getQueueCount()) > 0) {
        this.syncQueue();
      }
    }, 6000);
  }

  private notifyQueueChanged(): void {
    if (typeof window !== 'undefined') {
      this.getQueueCount().then((count) => {
        window.dispatchEvent(new CustomEvent('telemetryQueueChanged', { detail: { count } }));
      });
    }
  }
}

export const telemetryBuffer = new TelemetryBufferService();
export default telemetryBuffer;
