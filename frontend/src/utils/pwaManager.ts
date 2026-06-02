/**
 * PWA Service Worker Registration and Management
 */

interface ServiceWorkerRegistration {
  unregister(): Promise<boolean>;
  update(): Promise<void>;
  active?: ServiceWorker;
  waiting?: ServiceWorker;
  installing?: ServiceWorker;
}

interface ServiceWorker extends EventTarget {
  postMessage(message: any): void;
}

class PWAManager {
  private registration: ServiceWorkerRegistration | null = null;
  private updateCheckInterval: number | null = null;
  private listeners: Map<string, Set<Function>> = new Map();

  constructor() {
    this.initializeListeners();
  }

  private initializeListeners(): void {
    this.listeners.set('install', new Set());
    this.listeners.set('update', new Set());
    this.listeners.set('offline', new Set());
    this.listeners.set('online', new Set());
  }

  /**
   * Register Service Worker
   */
  async register(): Promise<void> {
    if (!('serviceWorker' in navigator)) {
      console.warn('Service Workers not supported');
      return;
    }

    try {
      this.registration = await navigator.serviceWorker.register('/serviceWorker.js', {
        scope: '/',
        updateViaCache: 'none',
      });

      console.log('Service Worker registered:', this.registration);

      // Listen for updates
      this.registration.addEventListener('updatefound', () => {
        this.handleUpdateFound();
      });

      // Check for updates periodically
      this.startUpdateCheck();

      // Listen for controller change
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        this.emit('update');
      });

      this.emit('install');
    } catch (error) {
      console.error('Service Worker registration failed:', error);
    }
  }

  /**
   * Handle update found
   */
  private handleUpdateFound(): void {
    if (!this.registration?.installing) return;

    const newWorker = this.registration.installing;

    newWorker.addEventListener('statechange', () => {
      if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
        // New service worker available
        this.emit('update');
        this.notifyUpdate();
      }
    });
  }

  /**
   * Start periodic update check
   */
  private startUpdateCheck(): void {
    // Check for updates every hour
    this.updateCheckInterval = window.setInterval(() => {
      this.registration?.update().catch(console.error);
    }, 60 * 60 * 1000);
  }

  /**
   * Stop update check
   */
  private stopUpdateCheck(): void {
    if (this.updateCheckInterval) {
      clearInterval(this.updateCheckInterval);
      this.updateCheckInterval = null;
    }
  }

  /**
   * Notify user of update
   */
  private notifyUpdate(): void {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('X-Agent Update Available', {
        body: 'A new version is available. Refresh to update.',
        icon: '/icons/icon-192x192.png',
        badge: '/icons/icon-192x192.png',
        tag: 'update-notification',
      });
    }
  }

  /**
   * Skip waiting and activate new service worker
   */
  async skipWaiting(): Promise<void> {
    if (this.registration?.waiting) {
      this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
    }
  }

  /**
   * Clear all caches
   */
  async clearCache(): Promise<void> {
    if (this.registration?.active) {
      this.registration.active.postMessage({ type: 'CLEAR_CACHE' });
    }

    if ('caches' in window) {
      const cacheNames = await caches.keys();
      await Promise.all(cacheNames.map((name) => caches.delete(name)));
    }
  }

  /**
   * Precache URLs
   */
  async precacheUrls(urls: string[]): Promise<void> {
    if (this.registration?.active) {
      this.registration.active.postMessage({
        type: 'CACHE_URLS',
        payload: { urls },
      });
    }
  }

  /**
   * Precache API endpoints
   */
  async precacheApi(endpoints: string[]): Promise<void> {
    if (this.registration?.active) {
      this.registration.active.postMessage({
        type: 'PRECACHE_API',
        payload: { endpoints },
      });
    }
  }

  /**
   * Check if app is installable
   */
  isInstallable(): boolean {
    return 'beforeinstallprompt' in window;
  }

  /**
   * Request install prompt
   */
  async requestInstall(): Promise<boolean> {
    const event = (window as any).deferredPrompt;
    if (!event) return false;

    event.prompt();
    const { outcome } = await event.userChoice;
    return outcome === 'accepted';
  }

  /**
   * Check if running as standalone app
   */
  isStandalone(): boolean {
    return (
      (window.navigator as any).standalone === true ||
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: fullscreen)').matches
    );
  }

  /**
   * Get installation status
   */
  getInstallationStatus(): {
    installed: boolean;
    installable: boolean;
    standalone: boolean;
  } {
    return {
      installed: this.registration !== null,
      installable: this.isInstallable(),
      standalone: this.isStandalone(),
    };
  }

  /**
   * Listen for online/offline events
   */
  setupConnectivityListener(): void {
    window.addEventListener('online', () => {
      this.emit('online');
      this.syncOfflineQueue();
    });

    window.addEventListener('offline', () => {
      this.emit('offline');
    });
  }

  /**
   * Sync offline queue
   */
  async syncOfflineQueue(): Promise<void> {
    if (this.registration?.active) {
      this.registration.active.postMessage({ type: 'SYNC_OFFLINE_QUEUE' });
    }
  }

  /**
   * Request background sync
   */
  async requestBackgroundSync(tag: string): Promise<void> {
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      try {
        const registration = await navigator.serviceWorker.ready;
        await (registration as any).sync.register(tag);
      } catch (error) {
        console.warn('Background sync not supported:', error);
      }
    }
  }

  /**
   * Request periodic background sync
   */
  async requestPeriodicSync(tag: string, minInterval: number): Promise<void> {
    if ('serviceWorker' in navigator && 'PeriodicSyncManager' in window) {
      try {
        const registration = await navigator.serviceWorker.ready;
        await (registration as any).periodicSync.register(tag, { minInterval });
      } catch (error) {
        console.warn('Periodic sync not supported:', error);
      }
    }
  }

  /**
   * Add event listener
   */
  on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)?.add(callback);
  }

  /**
   * Remove event listener
   */
  off(event: string, callback: Function): void {
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
   * Unregister Service Worker
   */
  async unregister(): Promise<void> {
    this.stopUpdateCheck();

    if (this.registration) {
      await this.registration.unregister();
      this.registration = null;
    }
  }

  /**
   * Get registration
   */
  getRegistration(): ServiceWorkerRegistration | null {
    return this.registration;
  }
}

// Export singleton instance
export const pwaManager = new PWAManager();

// Auto-register on module load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    pwaManager.register().catch(console.error);
    pwaManager.setupConnectivityListener();
  });
}

export default PWAManager;
