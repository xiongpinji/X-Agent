/**
 * Service Worker Registration and Configuration
 *
 * Handles caching strategies, offline support, and performance optimization
 */

const CACHE_VERSION = 'v1'
const CACHE_NAMES = {
  static: `${CACHE_VERSION}-static`,
  dynamic: `${CACHE_VERSION}-dynamic`,
  images: `${CACHE_VERSION}-images`,
  api: `${CACHE_VERSION}-api`,
}

/**
 * Register Service Worker
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) {
    console.log('Service Workers not supported')
    return null
  }

  try {
    const registration = await navigator.serviceWorker.register('/sw.js', {
      scope: '/',
    })

    console.log('Service Worker registered:', registration)

    // Check for updates periodically
    setInterval(() => {
      registration.update()
    }, 60000) // Check every minute

    return registration
  } catch (error) {
    console.error('Service Worker registration failed:', error)
    return null
  }
}

/**
 * Unregister Service Worker
 */
export async function unregisterServiceWorker(): Promise<void> {
  if (!('serviceWorker' in navigator)) return

  try {
    const registrations = await navigator.serviceWorker.getRegistrations()
    for (const registration of registrations) {
      await registration.unregister()
    }
    console.log('Service Workers unregistered')
  } catch (error) {
    console.error('Failed to unregister Service Workers:', error)
  }
}

/**
 * Clear all caches
 */
export async function clearAllCaches(): Promise<void> {
  if (!('caches' in window)) return

  try {
    const cacheNames = await caches.keys()
    await Promise.all(cacheNames.map((name) => caches.delete(name)))
    console.log('All caches cleared')
  } catch (error) {
    console.error('Failed to clear caches:', error)
  }
}

/**
 * Clear specific cache
 */
export async function clearCache(cacheName: string): Promise<void> {
  if (!('caches' in window)) return

  try {
    await caches.delete(cacheName)
    console.log(`Cache '${cacheName}' cleared`)
  } catch (error) {
    console.error(`Failed to clear cache '${cacheName}':`, error)
  }
}

/**
 * Get cache size
 */
export async function getCacheSize(): Promise<number> {
  if (!('caches' in window)) return 0

  try {
    const cacheNames = await caches.keys()
    let totalSize = 0

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

    return totalSize
  } catch (error) {
    console.error('Failed to get cache size:', error)
    return 0
  }
}

/**
 * Check if online
 */
export function isOnline(): boolean {
  return navigator.onLine
}

/**
 * Listen for online/offline events
 */
export function onOnlineStatusChange(callback: (isOnline: boolean) => void): () => void {
  const handleOnline = () => callback(true)
  const handleOffline = () => callback(false)

  window.addEventListener('online', handleOnline)
  window.addEventListener('offline', handleOffline)

  return () => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
  }
}

/**
 * Prefetch resources
 */
export async function prefetchResources(urls: string[]): Promise<void> {
  if (!('caches' in window)) return

  try {
    const cache = await caches.open(CACHE_NAMES.static)
    await cache.addAll(urls)
    console.log('Resources prefetched:', urls)
  } catch (error) {
    console.error('Failed to prefetch resources:', error)
  }
}

/**
 * Cache API response
 */
export async function cacheApiResponse(
  url: string,
  response: Response,
  cacheName: string = CACHE_NAMES.api
): Promise<void> {
  if (!('caches' in window)) return

  try {
    const cache = await caches.open(cacheName)
    await cache.put(url, response.clone())
  } catch (error) {
    console.error('Failed to cache API response:', error)
  }
}

/**
 * Get cached API response
 */
export async function getCachedApiResponse(
  url: string,
  cacheName: string = CACHE_NAMES.api
): Promise<Response | undefined> {
  if (!('caches' in window)) return undefined

  try {
    const cache = await caches.open(cacheName)
    return await cache.match(url)
  } catch (error) {
    console.error('Failed to get cached API response:', error)
    return undefined
  }
}

/**
 * Stale-while-revalidate strategy
 */
export async function staleWhileRevalidate(
  url: string,
  fetchFn: () => Promise<Response>
): Promise<Response> {
  const cached = await getCachedApiResponse(url)

  if (cached) {
    // Return cached response immediately
    // Fetch fresh data in background
    fetchFn()
      .then((response) => cacheApiResponse(url, response))
      .catch((error) => console.error('Background fetch failed:', error))

    return cached
  }

  // No cache, fetch and cache
  const response = await fetchFn()
  await cacheApiResponse(url, response)
  return response
}

/**
 * Cache-first strategy
 */
export async function cacheFirst(
  url: string,
  fetchFn: () => Promise<Response>
): Promise<Response> {
  const cached = await getCachedApiResponse(url)
  if (cached) return cached

  const response = await fetchFn()
  await cacheApiResponse(url, response)
  return response
}

/**
 * Network-first strategy
 */
export async function networkFirst(
  url: string,
  fetchFn: () => Promise<Response>
): Promise<Response> {
  try {
    const response = await fetchFn()
    await cacheApiResponse(url, response)
    return response
  } catch (error) {
    const cached = await getCachedApiResponse(url)
    if (cached) return cached
    throw error
  }
}
