/**
 * Mobile Performance Optimization
 */

interface PerformanceMetrics {
  navigationStart: number;
  domContentLoaded: number;
  loadComplete: number;
  firstPaint: number;
  firstContentfulPaint: number;
  largestContentfulPaint: number;
  timeToInteractive: number;
  totalBlockingTime: number;
  cumulativeLayoutShift: number;
}

interface ResourceTiming {
  name: string;
  duration: number;
  size: number;
  type: string;
}

class PerformanceOptimizer {
  private metrics: Partial<PerformanceMetrics> = {};
  private resourceTimings: ResourceTiming[] = [];
  private observers: Map<string, PerformanceObserver> = new Map();
  private listeners: Map<string, Set<(...args: unknown[]) => void>> = new Map();

  constructor() {
    this.initializeListeners();
  }

  private initializeListeners(): void {
    this.listeners.set('metrics-ready', new Set());
    this.listeners.set('slow-resource', new Set());
    this.listeners.set('performance-warning', new Set());
  }

  /**
   * Initialize performance monitoring
   */
  initialize(): void {
    this.measureNavigationTiming();
    this.observePaintTiming();
    this.observeLargestContentfulPaint();
    this.observeLayoutShift();
    this.observeResourceTiming();
    this.observeLongTasks();
  }

  /**
   * Measure navigation timing
   */
  private measureNavigationTiming(): void {
    if (!('PerformanceNavigationTiming' in window)) return;

    window.addEventListener('load', () => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;

      this.metrics.navigationStart = navigation.fetchStart;
      this.metrics.domContentLoaded = navigation.domContentLoadedEventEnd - navigation.fetchStart;
      this.metrics.loadComplete = navigation.loadEventEnd - navigation.fetchStart;

      // Check if load time exceeds threshold
      if (this.metrics.loadComplete! > 2000) {
        this.emit('performance-warning', {
          type: 'slow-load',
          duration: this.metrics.loadComplete,
          threshold: 2000,
        });
      }

      this.emit('metrics-ready', this.metrics);
    });
  }

  /**
   * Observe paint timing
   */
  private observePaintTiming(): void {
    if (!('PerformanceObserver' in window)) return;

    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === 'first-paint') {
            this.metrics.firstPaint = entry.startTime;
          } else if (entry.name === 'first-contentful-paint') {
            this.metrics.firstContentfulPaint = entry.startTime;
          }
        }
      });

      observer.observe({ entryTypes: ['paint'] });
      this.observers.set('paint', observer);
    } catch (error) {
      console.warn('Paint timing observer not supported:', error);
    }
  }

  /**
   * Observe largest contentful paint
   */
  private observeLargestContentfulPaint(): void {
    if (!('PerformanceObserver' in window)) return;

    try {
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        this.metrics.largestContentfulPaint = lastEntry.startTime;

        if (lastEntry.startTime > 2500) {
          this.emit('performance-warning', {
            type: 'slow-lcp',
            duration: lastEntry.startTime,
            threshold: 2500,
          });
        }
      });

      observer.observe({ entryTypes: ['largest-contentful-paint'] });
      this.observers.set('lcp', observer);
    } catch (error) {
      console.warn('LCP observer not supported:', error);
    }
  }

  /**
   * Observe layout shift
   */
  private observeLayoutShift(): void {
    if (!('PerformanceObserver' in window)) return;

    try {
      let cls = 0;

      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            cls += (entry as any).value;
            this.metrics.cumulativeLayoutShift = cls;

            if (cls > 0.1) {
              this.emit('performance-warning', {
                type: 'high-cls',
                value: cls,
                threshold: 0.1,
              });
            }
          }
        }
      });

      observer.observe({ entryTypes: ['layout-shift'] });
      this.observers.set('cls', observer);
    } catch (error) {
      console.warn('Layout shift observer not supported:', error);
    }
  }

  /**
   * Observe resource timing
   */
  private observeResourceTiming(): void {
    if (!('PerformanceObserver' in window)) return;

    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const resource: ResourceTiming = {
            name: entry.name,
            duration: entry.duration,
            size: (entry as any).transferSize || 0,
            type: entry.initiatorType,
          };

          this.resourceTimings.push(resource);

          // Warn about slow resources
          if (entry.duration > 1000) {
            this.emit('slow-resource', resource);
          }
        }
      });

      observer.observe({ entryTypes: ['resource'] });
      this.observers.set('resource', observer);
    } catch (error) {
      console.warn('Resource timing observer not supported:', error);
    }
  }

  /**
   * Observe long tasks
   */
  private observeLongTasks(): void {
    if (!('PerformanceObserver' in window)) return;

    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.emit('performance-warning', {
            type: 'long-task',
            duration: entry.duration,
            threshold: 50,
          });
        }
      });

      observer.observe({ entryTypes: ['longtask'] });
      this.observers.set('longtask', observer);
    } catch (error) {
      console.warn('Long task observer not supported:', error);
    }
  }

  /**
   * Measure custom metric
   */
  measureCustom(name: string, startMark: string, endMark: string): number {
    try {
      performance.measure(name, startMark, endMark);
      const measure = performance.getEntriesByName(name)[0];
      return measure.duration;
    } catch (error) {
      console.warn(`Failed to measure ${name}:`, error);
      return 0;
    }
  }

  /**
   * Mark performance point
   */
  mark(name: string): void {
    try {
      performance.mark(name);
    } catch (error) {
      console.warn(`Failed to mark ${name}:`, error);
    }
  }

  /**
   * Get all metrics
   */
  getMetrics(): Partial<PerformanceMetrics> {
    return { ...this.metrics };
  }

  /**
   * Get resource timings
   */
  getResourceTimings(): ResourceTiming[] {
    return [...this.resourceTimings];
  }

  /**
   * Get slow resources
   */
  getSlowResources(threshold: number = 1000): ResourceTiming[] {
    return this.resourceTimings.filter((r) => r.duration > threshold);
  }

  /**
   * Get performance score (0-100)
   */
  getPerformanceScore(): number {
    let score = 100;

    // Deduct for slow load
    if (this.metrics.loadComplete && this.metrics.loadComplete > 2000) {
      score -= Math.min(20, (this.metrics.loadComplete - 2000) / 100);
    }

    // Deduct for slow LCP
    if (this.metrics.largestContentfulPaint && this.metrics.largestContentfulPaint > 2500) {
      score -= Math.min(20, (this.metrics.largestContentfulPaint - 2500) / 100);
    }

    // Deduct for high CLS
    if (this.metrics.cumulativeLayoutShift && this.metrics.cumulativeLayoutShift > 0.1) {
      score -= Math.min(15, (this.metrics.cumulativeLayoutShift - 0.1) * 100);
    }

    // Deduct for slow resources
    const slowResources = this.getSlowResources();
    score -= Math.min(20, slowResources.length * 2);

    return Math.max(0, Math.round(score));
  }

  /**
   * Generate performance report
   */
  generateReport(): string {
    const metrics = this.getMetrics();
    const score = this.getPerformanceScore();
    const slowResources = this.getSlowResources();

    return `
Performance Report
==================

Score: ${score}/100

Metrics:
- Load Time: ${metrics.loadComplete?.toFixed(0)}ms
- DOM Content Loaded: ${metrics.domContentLoaded?.toFixed(0)}ms
- First Paint: ${metrics.firstPaint?.toFixed(0)}ms
- First Contentful Paint: ${metrics.firstContentfulPaint?.toFixed(0)}ms
- Largest Contentful Paint: ${metrics.largestContentfulPaint?.toFixed(0)}ms
- Cumulative Layout Shift: ${metrics.cumulativeLayoutShift?.toFixed(3)}

Slow Resources (>1000ms):
${slowResources.map((r) => `- ${r.name}: ${r.duration.toFixed(0)}ms (${r.size} bytes)`).join('\n')}

Recommendations:
${this.generateRecommendations()}
    `.trim();
  }

  /**
   * Generate recommendations
   */
  private generateRecommendations(): string {
    const recommendations: string[] = [];

    if (this.metrics.loadComplete && this.metrics.loadComplete > 2000) {
      recommendations.push('- Reduce initial load time by optimizing bundle size');
    }

    if (this.metrics.largestContentfulPaint && this.metrics.largestContentfulPaint > 2500) {
      recommendations.push('- Optimize LCP by lazy loading images and deferring non-critical scripts');
    }

    if (this.metrics.cumulativeLayoutShift && this.metrics.cumulativeLayoutShift > 0.1) {
      recommendations.push('- Reduce layout shifts by reserving space for dynamic content');
    }

    const slowResources = this.getSlowResources();
    if (slowResources.length > 0) {
      recommendations.push('- Optimize slow resources or consider lazy loading');
    }

    return recommendations.length > 0 ? recommendations.join('\n') : '- Performance is good!';
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
   * Cleanup
   */
  destroy(): void {
    this.observers.forEach((observer) => observer.disconnect());
    this.observers.clear();
    this.listeners.clear();
  }
}

// Export singleton instance
export const performanceOptimizer = new PerformanceOptimizer();

// Auto-initialize on module load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    performanceOptimizer.initialize();
  });
}

export default PerformanceOptimizer;
