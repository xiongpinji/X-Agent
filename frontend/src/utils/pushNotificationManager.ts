/**
 * Push Notification Management
 */

interface NotificationOptions {
  title: string;
  body?: string;
  icon?: string;
  badge?: string;
  tag?: string;
  requireInteraction?: boolean;
  actions?: NotificationAction[];
  data?: Record<string, any>;
  vibrate?: number[];
  sound?: string;
}

interface NotificationAction {
  action: string;
  title: string;
  icon?: string;
}

interface PushSubscription {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

class PushNotificationManager {
  private registration: ServiceWorkerRegistration | null = null;
  private subscription: PushSubscription | null = null;
  private listeners: Map<string, Set<(...args: unknown[]) => void>> = new Map();

  constructor() {
    this.initializeListeners();
  }

  private initializeListeners(): void {
    this.listeners.set('subscribe', new Set());
    this.listeners.set('unsubscribe', new Set());
    this.listeners.set('notification', new Set());
    this.listeners.set('error', new Set());
  }

  /**
   * Initialize push notifications
   */
  async initialize(): Promise<void> {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.warn('Push notifications not supported');
      return;
    }

    try {
      this.registration = await navigator.serviceWorker.ready;

      // Listen for push messages
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data.type === 'PUSH_NOTIFICATION') {
          this.emit('notification', event.data.payload);
        }
      });

      // Check existing subscription
      const subscription = await this.registration.pushManager.getSubscription();
      if (subscription) {
        this.subscription = subscription as any;
      }
    } catch (error) {
      console.error('Push notification initialization failed:', error);
      this.emit('error', error);
    }
  }

  /**
   * Request notification permission
   */
  async requestPermission(): Promise<NotificationPermission> {
    if (!('Notification' in window)) {
      console.warn('Notifications not supported');
      return 'denied';
    }

    if (Notification.permission === 'granted') {
      return 'granted';
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      return permission;
    }

    return 'denied';
  }

  /**
   * Subscribe to push notifications
   */
  async subscribe(vapidPublicKey: string): Promise<PushSubscription | null> {
    if (!this.registration) {
      console.error('Service Worker not ready');
      return null;
    }

    try {
      const permission = await this.requestPermission();
      if (permission !== 'granted') {
        console.warn('Notification permission denied');
        return null;
      }

      const subscription = await this.registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: this.urlBase64ToUint8Array(vapidPublicKey),
      });

      this.subscription = subscription as any;
      this.emit('subscribe', subscription);

      // Send subscription to server
      await this.sendSubscriptionToServer(subscription);

      return subscription as any;
    } catch (error) {
      console.error('Push subscription failed:', error);
      this.emit('error', error);
      return null;
    }
  }

  /**
   * Unsubscribe from push notifications
   */
  async unsubscribe(): Promise<boolean> {
    if (!this.subscription) {
      return false;
    }

    try {
      const success = await (this.subscription as any).unsubscribe();
      if (success) {
        this.subscription = null;
        this.emit('unsubscribe');
      }
      return success;
    } catch (error) {
      console.error('Push unsubscription failed:', error);
      this.emit('error', error);
      return false;
    }
  }

  /**
   * Send local notification
   */
  async sendNotification(options: NotificationOptions): Promise<void> {
    if (!('Notification' in window)) {
      console.warn('Notifications not supported');
      return;
    }

    if (Notification.permission !== 'granted') {
      console.warn('Notification permission not granted');
      return;
    }

    try {
      if (this.registration) {
        await this.registration.showNotification(options.title, {
          body: options.body,
          icon: options.icon || '/icons/icon-192x192.png',
          badge: options.badge || '/icons/icon-192x192.png',
          tag: options.tag,
          requireInteraction: options.requireInteraction,
          actions: options.actions,
          data: options.data,
          vibrate: options.vibrate,
        });
      } else {
        new Notification(options.title, {
          body: options.body,
          icon: options.icon,
          badge: options.badge,
          tag: options.tag,
          requireInteraction: options.requireInteraction,
        });
      }

      this.emit('notification', options);
    } catch (error) {
      console.error('Failed to send notification:', error);
      this.emit('error', error);
    }
  }

  /**
   * Get active notifications
   */
  async getNotifications(tag?: string): Promise<Notification[]> {
    if (!this.registration) {
      return [];
    }

    try {
      return await this.registration.getNotifications({ tag });
    } catch (error) {
      console.error('Failed to get notifications:', error);
      return [];
    }
  }

  /**
   * Close notification
   */
  async closeNotification(tag: string): Promise<void> {
    const notifications = await this.getNotifications(tag);
    notifications.forEach((notification) => notification.close());
  }

  /**
   * Send subscription to server
   */
  private async sendSubscriptionToServer(subscription: any): Promise<void> {
    try {
      const response = await fetch('/api/v1/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          subscription: {
            endpoint: subscription.endpoint,
            keys: {
              p256dh: this.arrayBufferToBase64(subscription.getKey('p256dh')),
              auth: this.arrayBufferToBase64(subscription.getKey('auth')),
            },
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to send subscription to server:', error);
    }
  }

  /**
   * Convert VAPID key
   */
  private urlBase64ToUint8Array(base64String: string): Uint8Array {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }

    return outputArray;
  }

  /**
   * Convert ArrayBuffer to Base64
   */
  private arrayBufferToBase64(buffer: ArrayBuffer): string {
    const bytes = new Uint8Array(buffer);
    let binary = '';

    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }

    return window.btoa(binary);
  }

  /**
   * Get subscription
   */
  getSubscription(): PushSubscription | null {
    return this.subscription;
  }

  /**
   * Check if subscribed
   */
  isSubscribed(): boolean {
    return this.subscription !== null;
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
}

// Export singleton instance
export const pushNotificationManager = new PushNotificationManager();

// Auto-initialize on module load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    pushNotificationManager.initialize().catch(console.error);
  });
}

export default PushNotificationManager;
