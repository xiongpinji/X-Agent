/**
 * Offline Data Management with IndexedDB
 */

interface OfflineQueueItem {
  id: string;
  timestamp: number;
  method: string;
  url: string;
  body?: any;
  headers?: Record<string, string>;
  retries: number;
  maxRetries: number;
}

interface SyncStatus {
  syncing: boolean;
  lastSync: number | null;
  pendingItems: number;
  failedItems: number;
}

class OfflineDataManager {
  private db: IDBDatabase | null = null;
  private syncStatus: SyncStatus = {
    syncing: false,
    lastSync: null,
    pendingItems: 0,
    failedItems: 0,
  };
  private listeners: Map<string, Set<(...args: unknown[]) => void>> = new Map();
  private syncInterval: number | null = null;

  constructor() {
    this.initializeListeners();
  }

  private initializeListeners(): void {
    this.listeners.set('sync-start', new Set());
    this.listeners.set('sync-complete', new Set());
    this.listeners.set('sync-error', new Set());
    this.listeners.set('status-change', new Set());
  }

  /**
   * Initialize IndexedDB
   */
  async initialize(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('xagent-offline', 1);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;

        // Create object stores
        if (!db.objectStoreNames.contains('offline-queue')) {
          const queueStore = db.createObjectStore('offline-queue', { keyPath: 'id' });
          queueStore.createIndex('timestamp', 'timestamp', { unique: false });
          queueStore.createIndex('status', 'status', { unique: false });
        }

        if (!db.objectStoreNames.contains('offline-cache')) {
          const cacheStore = db.createObjectStore('offline-cache', { keyPath: 'key' });
          cacheStore.createIndex('timestamp', 'timestamp', { unique: false });
          cacheStore.createIndex('ttl', 'ttl', { unique: false });
        }

        if (!db.objectStoreNames.contains('sync-metadata')) {
          db.createObjectStore('sync-metadata', { keyPath: 'key' });
        }
      };
    });
  }

  /**
   * Add request to offline queue
   */
  async queueRequest(
    method: string,
    url: string,
    body?: any,
    headers?: Record<string, string>
  ): Promise<string> {
    if (!this.db) throw new Error('Database not initialized');

    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const item: OfflineQueueItem = {
      id,
      timestamp: Date.now(),
      method,
      url,
      body,
      headers,
      retries: 0,
      maxRetries: 3,
    };

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-queue', 'readwrite');
      const store = transaction.objectStore('offline-queue');
      const request = store.add(item);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.updateSyncStatus();
        this.emit('status-change', this.syncStatus);
        resolve(id);
      };
    });
  }

  /**
   * Get offline queue
   */
  async getQueue(): Promise<OfflineQueueItem[]> {
    if (!this.db) throw new Error('Database not initialized');

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-queue', 'readonly');
      const store = transaction.objectStore('offline-queue');
      const request = store.getAll();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
    });
  }

  /**
   * Remove item from queue
   */
  async removeFromQueue(id: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-queue', 'readwrite');
      const store = transaction.objectStore('offline-queue');
      const request = store.delete(id);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.updateSyncStatus();
        this.emit('status-change', this.syncStatus);
        resolve();
      };
    });
  }

  /**
   * Update item retry count
   */
  async updateRetryCount(id: string, retries: number): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-queue', 'readwrite');
      const store = transaction.objectStore('offline-queue');
      const getRequest = store.get(id);

      getRequest.onsuccess = () => {
        const item = getRequest.result;
        if (item) {
          item.retries = retries;
          const updateRequest = store.put(item);
          updateRequest.onerror = () => reject(updateRequest.error);
          updateRequest.onsuccess = () => resolve();
        }
      };

      getRequest.onerror = () => reject(getRequest.error);
    });
  }

  /**
   * Sync offline queue
   */
  async syncQueue(): Promise<void> {
    if (this.syncStatus.syncing) return;

    this.syncStatus.syncing = true;
    this.emit('sync-start');

    try {
      const queue = await this.getQueue();

      for (const item of queue) {
        try {
          const response = await fetch(item.url, {
            method: item.method,
            headers: {
              'Content-Type': 'application/json',
              ...item.headers,
            },
            body: item.body ? JSON.stringify(item.body) : undefined,
          });

          if (response.ok) {
            await this.removeFromQueue(item.id);
          } else if (response.status >= 400 && response.status < 500) {
            // Client error - don't retry
            await this.removeFromQueue(item.id);
          } else if (item.retries < item.maxRetries) {
            // Server error - retry
            await this.updateRetryCount(item.id, item.retries + 1);
          } else {
            // Max retries exceeded
            await this.removeFromQueue(item.id);
            this.emit('sync-error', { item, error: 'Max retries exceeded' });
          }
        } catch (error) {
          if (item.retries < item.maxRetries) {
            await this.updateRetryCount(item.id, item.retries + 1);
          } else {
            await this.removeFromQueue(item.id);
            this.emit('sync-error', { item, error });
          }
        }
      }

      this.syncStatus.lastSync = Date.now();
      this.emit('sync-complete', this.syncStatus);
    } catch (error) {
      this.emit('sync-error', error);
    } finally {
      this.syncStatus.syncing = false;
      this.updateSyncStatus();
      this.emit('status-change', this.syncStatus);
    }
  }

  /**
   * Cache data
   */
  async cacheData(key: string, data: any, ttl?: number): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    const cacheEntry = {
      key,
      data,
      timestamp: Date.now(),
      ttl: ttl || 24 * 60 * 60 * 1000, // 24 hours default
    };

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-cache', 'readwrite');
      const store = transaction.objectStore('offline-cache');
      const request = store.put(cacheEntry);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }

  /**
   * Get cached data
   */
  async getCachedData(key: string): Promise<any | null> {
    if (!this.db) throw new Error('Database not initialized');

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-cache', 'readonly');
      const store = transaction.objectStore('offline-cache');
      const request = store.get(key);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const entry = request.result;
        if (!entry) {
          resolve(null);
          return;
        }

        // Check if expired
        if (Date.now() - entry.timestamp > entry.ttl) {
          // Delete expired entry
          const deleteTransaction = this.db!.transaction('offline-cache', 'readwrite');
          const deleteStore = deleteTransaction.objectStore('offline-cache');
          deleteStore.delete(key);
          resolve(null);
        } else {
          resolve(entry.data);
        }
      };
    });
  }

  /**
   * Clear cache
   */
  async clearCache(): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction('offline-cache', 'readwrite');
      const store = transaction.objectStore('offline-cache');
      const request = store.clear();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }

  /**
   * Update sync status
   */
  private async updateSyncStatus(): Promise<void> {
    const queue = await this.getQueue();
    this.syncStatus.pendingItems = queue.length;
    this.syncStatus.failedItems = queue.filter((item) => item.retries > 0).length;
  }

  /**
   * Get sync status
   */
  getSyncStatus(): SyncStatus {
    return { ...this.syncStatus };
  }

  /**
   * Start auto-sync
   */
  startAutoSync(interval: number = 30000): void {
    this.syncInterval = window.setInterval(() => {
      if (navigator.onLine) {
        this.syncQueue().catch(console.error);
      }
    }, interval);
  }

  /**
   * Stop auto-sync
   */
  stopAutoSync(): void {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  /**
   * Add event listener
   */
  on(event: string, callback: (...args: unknown[]) => void): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }

  /**
   * Remove event listener
   */
  off(event: string, callback: (...args: unknown[]) => void): void {
    this.listeners.get(event)?.delete(callback);
  }

  /**
   * Emit event
   */
  private emit(event: string, data?: any): void {
    this.listeners.get(event)?.forEach((callback) => {
      callback(data);
    });
  }

  /**
   * Clear all data
   */
  async clearAll(): Promise<void> {
    if (!this.db) throw new Error('Database not initialized');

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(
        ['offline-queue', 'offline-cache', 'sync-metadata'],
        'readwrite'
      );

      transaction.objectStore('offline-queue').clear();
      transaction.objectStore('offline-cache').clear();
      transaction.objectStore('sync-metadata').clear();

      transaction.onerror = () => reject(transaction.error);
      transaction.oncomplete = () => {
        this.updateSyncStatus();
        resolve();
      };
    });
  }
}

// Export singleton instance
export const offlineDataManager = new OfflineDataManager();

// Auto-initialize on module load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    offlineDataManager.initialize().catch(console.error);
    offlineDataManager.startAutoSync();

    // Listen for online event
    window.addEventListener('online', () => {
      offlineDataManager.syncQueue().catch(console.error);
    });
  });
}

export default OfflineDataManager;
