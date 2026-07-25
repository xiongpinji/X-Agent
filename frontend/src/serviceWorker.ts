/// <reference lib="webworker" />

declare const self: ServiceWorkerGlobalScope;

const CACHE_VERSION = 'v1';
const CACHE_NAMES = {
  static: `${CACHE_VERSION}-static`,
  dynamic: `${CACHE_VERSION}-dynamic`,
  api: `${CACHE_VERSION}-api`,
};

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/app-shell.css',
  '/manifest.json',
];

const _API_CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
const _STALE_WHILE_REVALIDATE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

interface _CacheEntry {
  timestamp: number;
  data: Response;
}

const apiCacheTimestamps = new Map<string, number>();

// Install event - cache static assets
self.addEventListener('install', (event: ExtendedEvent) => {
  event.waitUntil(
    caches.open(CACHE_NAMES.static).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('Failed to cache static assets:', err);
      });
    })
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event: ExtendedEvent) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (!Object.values(CACHE_NAMES).includes(cacheName)) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - implement caching strategies
self.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip chrome extensions and other non-http(s) requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // API requests - Network first with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // Static assets - Cache first with network fallback
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirstStrategy(request));
    return;
  }

  // HTML pages - Network first with cache fallback
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // Default - Network first
  event.respondWith(networkFirstStrategy(request));
});

// Network first strategy
async function networkFirstStrategy(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);

    if (response.ok) {
      // Cache successful responses
      const cacheName = request.url.includes('/api/') ? CACHE_NAMES.api : CACHE_NAMES.dynamic;
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());

      // Update timestamp for API requests
      if (request.url.includes('/api/')) {
        apiCacheTimestamps.set(request.url, Date.now());
      }
    }

    return response;
  } catch (error) {
    // Network failed, try cache
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }

    // Return offline page for HTML requests
    if (request.headers.get('accept')?.includes('text/html')) {
      return caches.match('/offline.html') || new Response('Offline', { status: 503 });
    }

    return new Response('Network error', { status: 503 });
  }
}

// Cache first strategy
async function cacheFirstStrategy(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAMES.static);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    return new Response('Not found', { status: 404 });
  }
}

// Check if URL is a static asset
function isStaticAsset(pathname: string): boolean {
  return /\.(js|css|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot)$/i.test(pathname);
}

// Message handler for cache management
self.addEventListener('message', (event: ExtendedMessageEvent) => {
  const { type, payload } = event.data;

  switch (type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;

    case 'CLEAR_CACHE':
      event.waitUntil(
        caches.keys().then((cacheNames) => {
          return Promise.all(cacheNames.map((name) => caches.delete(name)));
        })
      );
      break;

    case 'CACHE_URLS':
      event.waitUntil(
        caches.open(CACHE_NAMES.dynamic).then((cache) => {
          return cache.addAll(payload.urls);
        })
      );
      break;

    case 'PRECACHE_API':
      event.waitUntil(
        precacheApiEndpoints(payload.endpoints)
      );
      break;
  }
});

// Precache API endpoints
async function precacheApiEndpoints(endpoints: string[]): Promise<void> {
  const cache = await caches.open(CACHE_NAMES.api);

  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint);
      if (response.ok) {
        cache.put(endpoint, response);
        apiCacheTimestamps.set(endpoint, Date.now());
      }
    } catch (error) {
      console.warn(`Failed to precache ${endpoint}:`, error);
    }
  }
}

// Background sync for offline actions
self.addEventListener('sync', (event: any) => {
  if (event.tag === 'sync-offline-queue') {
    event.waitUntil(syncOfflineQueue());
  }
});

async function syncOfflineQueue(): Promise<void> {
  try {
    const db = await openIndexedDB();
    const queue = await getOfflineQueue(db);

    for (const item of queue) {
      try {
        const response = await fetch(item.request);
        if (response.ok) {
          await removeFromQueue(db, item.id);
        }
      } catch (error) {
        console.warn('Failed to sync offline item:', error);
      }
    }
  } catch (error) {
    console.error('Sync failed:', error);
  }
}

// IndexedDB helpers
function openIndexedDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('xagent-offline', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains('offline-queue')) {
        db.createObjectStore('offline-queue', { keyPath: 'id' });
      }
    };
  });
}

function getOfflineQueue(db: IDBDatabase): Promise<any[]> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('offline-queue', 'readonly');
    const store = transaction.objectStore('offline-queue');
    const request = store.getAll();

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

function removeFromQueue(db: IDBDatabase, id: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction('offline-queue', 'readwrite');
    const store = transaction.objectStore('offline-queue');
    const request = store.delete(id);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// Type definitions
interface ExtendedEvent extends Event {
  waitUntil(promise: Promise<any>): void;
}

interface FetchEvent extends Event {
  request: Request;
  respondWith(response: Response | Promise<Response>): void;
}

interface ExtendedMessageEvent extends MessageEvent {
  data: {
    type: string;
    payload?: any;
  };
}

export {};
