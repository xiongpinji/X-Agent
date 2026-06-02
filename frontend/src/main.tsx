import React, { Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// Performance monitoring
if ('PerformanceObserver' in window) {
  // Monitor Core Web Vitals
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      console.log(`${entry.name}: ${entry.duration}ms`)
      // Send to analytics
      if (window.__ANALYTICS__) {
        window.__ANALYTICS__.track('performance', {
          metric: entry.name,
          value: entry.duration,
        })
      }
    }
  })

  // Observe paint timing
  observer.observe({ entryTypes: ['paint', 'largest-contentful-paint', 'first-input', 'layout-shift'] })

  // Monitor long tasks
  if ('PerformanceObserver' in window) {
    try {
      const longTaskObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          console.warn(`Long task detected: ${entry.duration}ms`)
        }
      })
      longTaskObserver.observe({ entryTypes: ['longtask'] })
    } catch (e) {
      // Long task API not supported
    }
  }
}

// Lazy load non-critical resources
const loadNonCriticalResources = () => {
  // Preload fonts
  const link = document.createElement('link')
  link.rel = 'preload'
  link.as = 'font'
  link.href = '/fonts/inter.woff2'
  link.type = 'font/woff2'
  link.crossOrigin = 'anonymous'
  document.head.appendChild(link)

  // Prefetch API endpoints
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      const link = document.createElement('link')
      link.rel = 'prefetch'
      link.href = '/api/health'
      document.head.appendChild(link)
    })
  }
}

// Load non-critical resources after initial render
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadNonCriticalResources)
} else {
  loadNonCriticalResources()
}

// Enable React Strict Mode only in development
const root = ReactDOM.createRoot(document.getElementById('root')!)

if (process.env.NODE_ENV === 'development') {
  root.render(
    <React.StrictMode>
      <Suspense fallback={<div>Loading...</div>}>
        <App />
      </Suspense>
    </React.StrictMode>,
  )
} else {
  root.render(
    <Suspense fallback={<div>Loading...</div>}>
      <App />
    </Suspense>,
  )
}
