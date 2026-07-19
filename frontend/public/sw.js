/**
 * Service Worker
 *
 * Handles caching, offline support, and background sync
 */

const CACHE_VERSION = 'v1'
const CACHE_NAMES = {
  static: `${CACHE_VERSION}-static`,
  dynamic: `${CACHE_VERSION}-dynamic`,
  images: `${CACHE_VERSION}-images`,
  api: `${CACHE_VERSION}-api`,
}

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
]

// Install event
self.addEventListener('install', (event: ExtendableEvent) => {
  console.log('Service Worker installing...')

  event.waitUntil(
    (async () => {
      try {
        const cache = await caches.open(CACHE_NAMES.static)
        await cache.addAll(STATIC_ASSETS)
        console.log('Static assets cached')
        await self.skipWaiting()
      } catch (error) {
        console.error('Failed to cache static assets:', error)
      }
    })()
  )
})

// Activate event
self.addEventListener('activate', (event: ExtendableEvent) => {
  console.log('Service Worker activating...')

  event.waitUntil(
    (async () => {
      try {
        const cacheNames = await caches.keys()
        await Promise.all(
          cacheNames
            .filter((name) => !Object.values(CACHE_NAMES).includes(name))
            .map((name) => caches.delete(name))
        )
        console.log('Old caches cleaned up')
        await self.clients.claim()
      } catch (error) {
        console.error('Failed to clean up caches:', error)
      }
    })()
  )
})

// Fetch event
self.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event
  const url = new URL(request.url)

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return
  }

  // Skip chrome extensions
  if (url.protocol === 'chrome-extension:') {
    return
  }

  // API requests - network first
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request))
    return
  }

  // Images - cache first
  if (request.destination === 'image') {
    event.respondWith(cacheFirstStrategy(request))
    return
  }

  // Static assets - cache first
  if (
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'font'
  ) {
    event.respondWith(cacheFirstStrategy(request))
    return
  }

  // HTML - stale while revalidate
  if (request.destination === 'document') {
    event.respondWith(staleWhileRevalidateStrategy(request))
    return
  }

  // Default - network first
  event.respondWith(networkFirstStrategy(request))
})

/**
 * Network first strategy
 */
async function networkFirstStrategy(request: Request): Promise<Response> {
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(CACHE_NAMES.dynamic)
      cache.put(request, response.clone())
    }
    return response
  } catch (error) {
    const cached = await caches.match(request)
    if (cached) {
      return cached
    }
    return new Response('Offline - Resource not available', {
      status: 503,
      statusText: 'Service Unavailable',
    })
  }
}

/**
 * Cache first strategy
 */
async function cacheFirstStrategy(request: Request): Promise<Response> {
  const cached = await caches.match(request)
  if (cached) {
    return cached
  }

  try {
    const response = await fetch(request)
    if (response.ok) {
      const cacheName =
        request.destination === 'image' ? CACHE_NAMES.images : CACHE_NAMES.static
      const cache = await caches.open(cacheName)
      cache.put(request, response.clone())
    }
    return response
  } catch (error) {
    return new Response('Offline - Resource not available', {
      status: 503,
      statusText: 'Service Unavailable',
    })
  }
}

/**
 * Stale while revalidate strategy
 */
async function staleWhileRevalidateStrategy(request: Request): Promise<Response> {
  const cached = await caches.match(request)

  const fetchPromise = fetch(request).then((response) => {
    if (response.ok) {
      const cache = caches.open(CACHE_NAMES.dynamic)
      cache.then((c) => c.put(request, response.clone()))
    }
    return response
  })

  return cached || fetchPromise
}

// Message event for cache management
self.addEventListener('message', (event: ExtendableMessageEvent) => {
  const { type, payload } = event.data

  if (type === 'CLEAR_CACHE') {
    event.waitUntil(
      (async () => {
        const cacheName = payload?.cacheName
        if (cacheName) {
          await caches.delete(cacheName)
        } else {
          const cacheNames = await caches.keys()
          await Promise.all(cacheNames.map((name) => caches.delete(name)))
        }
        event.ports[0].postMessage({ success: true })
      })()
    )
  }

  if (type === 'GET_CACHE_SIZE') {
    event.waitUntil(
      (async () => {
        let totalSize = 0
        const cacheNames = await caches.keys()

        for (const name of cacheNames) {
          const cache = await caches.open(name)
          const keys = await cache.keys()

          for (const request of keys) {
            const response = await cache.match(request)
            if (response) {
              const blob = await response.blob()
              totalSize += blob.size
            }
          }
        }

        event.ports[0].postMessage({ size: totalSize })
      })()
    )
  }
})

// Periodic background sync (if supported)
if ('periodicSync' in self.registration) {
  self.addEventListener('periodicsync', (event: any) => {
    if (event.tag === 'sync-data') {
      event.waitUntil(syncData())
    }
  })
}

async function syncData(): Promise<void> {
  try {
    // Sync pending requests or data
    console.log('Background sync triggered')
  } catch (error) {
    console.error('Background sync failed:', error)
  }
}

// Push notifications (if supported)
self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return

  const data = event.data.json()
  const options: NotificationOptions = {
    body: data.body,
    icon: '/icon-192x192.png',
    badge: '/badge-72x72.png',
    tag: data.tag || 'notification',
    requireInteraction: data.requireInteraction || false,
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Notification', options)
  )
})

// Notification click
self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()

  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === '/' && 'focus' in client) {
          return (client as WindowClient).focus()
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow('/')
      }
    })
  )
})
