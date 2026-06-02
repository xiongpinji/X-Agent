/**
 * Performance Monitoring and Optimization Utilities
 *
 * Tracks Core Web Vitals, memory usage, and component performance
 */

export interface PerformanceMetrics {
  fcp: number | null // First Contentful Paint
  lcp: number | null // Largest Contentful Paint
  cls: number | null // Cumulative Layout Shift
  fid: number | null // First Input Delay
  ttfb: number | null // Time to First Byte
  domContentLoaded: number | null
  loadComplete: number | null
}

export interface ComponentMetrics {
  name: string
  renderTime: number
  timestamp: number
}

class PerformanceMonitor {
  private metrics: PerformanceMetrics = {
    fcp: null,
    lcp: null,
    cls: null,
    fid: null,
    ttfb: null,
    domContentLoaded: null,
    loadComplete: null,
  }

  private componentMetrics: ComponentMetrics[] = []
  private observers: Map<string, PerformanceObserver> = new Map()

  constructor() {
    this.initializeMetrics()
  }

  private initializeMetrics(): void {
    // Measure navigation timing
    if (window.performance && window.performance.timing) {
      const timing = window.performance.timing
      this.metrics.ttfb = timing.responseStart - timing.navigationStart
      this.metrics.domContentLoaded = timing.domContentLoadedEventEnd - timing.navigationStart
      this.metrics.loadComplete = timing.loadEventEnd - timing.navigationStart
    }

    // Observe First Contentful Paint
    this.observeFCP()

    // Observe Largest Contentful Paint
    this.observeLCP()

    // Observe Cumulative Layout Shift
    this.observeCLS()

    // Observe First Input Delay
    this.observeFID()
  }

  private observeFCP(): void {
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const lastEntry = entries[entries.length - 1]
          this.metrics.fcp = lastEntry.startTime
        })
        observer.observe({ entryTypes: ['paint'] })
        this.observers.set('fcp', observer)
      } catch (e) {
        console.warn('FCP observer not supported')
      }
    }
  }

  private observeLCP(): void {
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const lastEntry = entries[entries.length - 1]
          this.metrics.lcp = lastEntry.startTime
        })
        observer.observe({ entryTypes: ['largest-contentful-paint'] })
        this.observers.set('lcp', observer)
      } catch (e) {
        console.warn('LCP observer not supported')
      }
    }
  }

  private observeCLS(): void {
    if ('PerformanceObserver' in window) {
      try {
        let clsValue = 0
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value
              this.metrics.cls = clsValue
            }
          }
        })
        observer.observe({ entryTypes: ['layout-shift'] })
        this.observers.set('cls', observer)
      } catch (e) {
        console.warn('CLS observer not supported')
      }
    }
  }

  private observeFID(): void {
    if ('PerformanceObserver' in window) {
      try {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const firstEntry = entries[0]
          this.metrics.fid = (firstEntry as any).processingDuration
        })
        observer.observe({ entryTypes: ['first-input'] })
        this.observers.set('fid', observer)
      } catch (e) {
        console.warn('FID observer not supported')
      }
    }
  }

  public recordComponentRender(name: string, renderTime: number): void {
    this.componentMetrics.push({
      name,
      renderTime,
      timestamp: Date.now(),
    })

    // Keep only last 100 measurements
    if (this.componentMetrics.length > 100) {
      this.componentMetrics.shift()
    }

    // Log slow renders (> 16ms)
    if (renderTime > 16) {
      console.warn(`Slow render detected: ${name} took ${renderTime.toFixed(2)}ms`)
    }
  }

  public getMetrics(): PerformanceMetrics {
    return { ...this.metrics }
  }

  public getComponentMetrics(): ComponentMetrics[] {
    return [...this.componentMetrics]
  }

  public getAverageComponentRenderTime(name: string): number {
    const metrics = this.componentMetrics.filter((m) => m.name === name)
    if (metrics.length === 0) return 0
    const sum = metrics.reduce((acc, m) => acc + m.renderTime, 0)
    return sum / metrics.length
  }

  public reportMetrics(): void {
    const metrics = this.getMetrics()
    console.table({
      'First Contentful Paint': `${metrics.fcp?.toFixed(2) || 'N/A'}ms`,
      'Largest Contentful Paint': `${metrics.lcp?.toFixed(2) || 'N/A'}ms`,
      'Cumulative Layout Shift': `${metrics.cls?.toFixed(3) || 'N/A'}`,
      'First Input Delay': `${metrics.fid?.toFixed(2) || 'N/A'}ms`,
      'Time to First Byte': `${metrics.ttfb?.toFixed(2) || 'N/A'}ms`,
      'DOM Content Loaded': `${metrics.domContentLoaded?.toFixed(2) || 'N/A'}ms`,
      'Load Complete': `${metrics.loadComplete?.toFixed(2) || 'N/A'}ms`,
    })
  }

  public dispose(): void {
    this.observers.forEach((observer) => observer.disconnect())
    this.observers.clear()
  }
}

export const performanceMonitor = new PerformanceMonitor()

// Measure component render time
export function measureComponentRender(
  componentName: string,
  renderFn: () => void
): void {
  const start = performance.now()
  renderFn()
  const end = performance.now()
  performanceMonitor.recordComponentRender(componentName, end - start)
}

// Measure async operation
export async function measureAsync<T>(
  name: string,
  fn: () => Promise<T>
): Promise<T> {
  const start = performance.now()
  try {
    const result = await fn()
    const end = performance.now()
    console.log(`${name} took ${(end - start).toFixed(2)}ms`)
    return result
  } catch (error) {
    const end = performance.now()
    console.error(`${name} failed after ${(end - start).toFixed(2)}ms`, error)
    throw error
  }
}

// Check if page meets performance targets
export function checkPerformanceTargets(): {
  fcp: boolean
  lcp: boolean
  cls: boolean
  fid: boolean
} {
  const metrics = performanceMonitor.getMetrics()
  return {
    fcp: metrics.fcp !== null && metrics.fcp < 1800, // Good: < 1.8s
    lcp: metrics.lcp !== null && metrics.lcp < 2500, // Good: < 2.5s
    cls: metrics.cls !== null && metrics.cls < 0.1, // Good: < 0.1
    fid: metrics.fid !== null && metrics.fid < 100, // Good: < 100ms
  }
}
