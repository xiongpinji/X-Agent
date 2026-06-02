/**
 * Performance Monitoring Utility
 *
 * Tracks Core Web Vitals and sends metrics to analytics
 */

interface PerformanceMetric {
  name: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  timestamp: number;
}

interface PerformanceReport {
  metrics: PerformanceMetric[];
  timestamp: number;
  url: string;
  userAgent: string;
}

class PerformanceMonitor {
  private metrics: Map<string, PerformanceMetric> = new Map();
  private observers: PerformanceObserver[] = [];
  private reportCallback?: (report: PerformanceReport) => void;

  constructor() {
    this.initializeMonitoring();
  }

  private initializeMonitoring() {
    // Monitor paint timing (FCP)
    this.observePaintTiming();

    // Monitor largest contentful paint (LCP)
    this.observeLCP();

    // Monitor cumulative layout shift (CLS)
    this.observeCLS();

    // Monitor first input delay (FID)
    this.observeFID();

    // Monitor time to first byte (TTFB)
    this.observeTTFB();

    // Monitor long tasks
    this.observeLongTasks();

    // Send report on page unload
    window.addEventListener('beforeunload', () => {
      this.sendReport();
    });
  }

  private observePaintTiming() {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === 'first-contentful-paint') {
            this.recordMetric('FCP', entry.startTime, 1000);
          }
        }
      });
      observer.observe({ entryTypes: ['paint'] });
      this.observers.push(observer);
    } catch (e) {
      console.warn('Paint timing not supported');
    }
  }

  private observeLCP() {
    try {
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        this.recordMetric('LCP', lastEntry.renderTime || lastEntry.loadTime, 2500);
      });
      observer.observe({ entryTypes: ['largest-contentful-paint'] });
      this.observers.push(observer);
    } catch (e) {
      console.warn('LCP not supported');
    }
  }

  private observeCLS() {
    try {
      let clsValue = 0;
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value;
            this.recordMetric('CLS', clsValue, 0.1);
          }
        }
      });
      observer.observe({ entryTypes: ['layout-shift'] });
      this.observers.push(observer);
    } catch (e) {
      console.warn('CLS not supported');
    }
  }

  private observeFID() {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          this.recordMetric('FID', (entry as any).processingDuration, 100);
        }
      });
      observer.observe({ entryTypes: ['first-input'] });
      this.observers.push(observer);
    } catch (e) {
      console.warn('FID not supported');
    }
  }

  private observeTTFB() {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === 'document') {
            const ttfb = (entry as PerformanceResourceTiming).responseStart - (entry as PerformanceResourceTiming).fetchStart;
            this.recordMetric('TTFB', ttfb, 600);
          }
        }
      });
      observer.observe({ entryTypes: ['navigation'] });
      this.observers.push(observer);
    } catch (e) {
      console.warn('TTFB not supported');
    }
  }

  private observeLongTasks() {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          console.warn(`Long task detected: ${(entry as any).duration}ms`);
        }
      });
      observer.observe({ entryTypes: ['longtask'] });
      this.observers.push(observer);
    } catch (e) {
      console.warn('Long task API not supported');
    }
  }

  private recordMetric(name: string, value: number, threshold: number) {
    let rating: 'good' | 'needs-improvement' | 'poor' = 'good';

    if (name === 'CLS') {
      rating = value <= 0.1 ? 'good' : value <= 0.25 ? 'needs-improvement' : 'poor';
    } else {
      const poorThreshold = threshold * 1.5;
      const needsImprovementThreshold = threshold * 1.25;

      if (value <= threshold) {
        rating = 'good';
      } else if (value <= needsImprovementThreshold) {
        rating = 'needs-improvement';
      } else {
        rating = 'poor';
      }
    }

    this.metrics.set(name, {
      name,
      value,
      rating,
      timestamp: Date.now(),
    });

    console.log(`${name}: ${value.toFixed(2)}ms (${rating})`);
  }

  public setReportCallback(callback: (report: PerformanceReport) => void) {
    this.reportCallback = callback;
  }

  public getMetrics(): PerformanceMetric[] {
    return Array.from(this.metrics.values());
  }

  public getMetric(name: string): PerformanceMetric | undefined {
    return this.metrics.get(name);
  }

  public sendReport() {
    if (!this.reportCallback) return;

    const report: PerformanceReport = {
      metrics: this.getMetrics(),
      timestamp: Date.now(),
      url: window.location.href,
      userAgent: navigator.userAgent,
    };

    this.reportCallback(report);
  }

  public destroy() {
    this.observers.forEach((observer) => observer.disconnect());
    this.observers = [];
    this.metrics.clear();
  }
}

// Create singleton instance
let monitor: PerformanceMonitor | null = null;

export function initPerformanceMonitoring(
  reportCallback?: (report: PerformanceReport) => void
): PerformanceMonitor {
  if (!monitor) {
    monitor = new PerformanceMonitor();
    if (reportCallback) {
      monitor.setReportCallback(reportCallback);
    }
  }
  return monitor;
}

export function getPerformanceMonitor(): PerformanceMonitor | null {
  return monitor;
}

export type { PerformanceMetric, PerformanceReport };
