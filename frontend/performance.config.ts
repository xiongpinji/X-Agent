/**
 * Performance Configuration for X-Agent Web Frontend
 *
 * Targets:
 * - FCP (First Contentful Paint): < 1s
 * - LCP (Largest Contentful Paint): < 2.5s
 * - TTI (Time to Interactive): < 3s
 * - Bundle Size: < 500KB
 */

export const performanceConfig = {
  // Image optimization
  images: {
    formats: ['webp', 'avif'],
    sizes: {
      thumbnail: 150,
      small: 300,
      medium: 600,
      large: 1200,
    },
    quality: {
      webp: 80,
      avif: 75,
      jpeg: 85,
    },
  },

  // Font optimization
  fonts: {
    preload: [
      '/fonts/inter-var.woff2',
    ],
    display: 'swap',
    fallback: 'system-ui, -apple-system, sans-serif',
  },

  // Code splitting strategy
  chunks: {
    vendor: {
      test: /[\\/]node_modules[\\/]/,
      name: 'vendor',
      priority: 10,
    },
    react: {
      test: /[\\/]node_modules[\\/](react|react-dom|react-router-dom)[\\/]/,
      name: 'vendor-react',
      priority: 20,
    },
    state: {
      test: /[\\/]node_modules[\\/](zustand|@tanstack\/react-query)[\\/]/,
      name: 'vendor-state',
      priority: 15,
    },
    ui: {
      test: /[\\/]node_modules[\\/](lucide-react|recharts)[\\/]/,
      name: 'vendor-ui',
      priority: 12,
    },
    utils: {
      test: /[\\/]node_modules[\\/](axios|date-fns|clsx)[\\/]/,
      name: 'vendor-utils',
      priority: 11,
    },
  },

  // Lazy loading configuration
  lazyLoad: {
    // Pages to lazy load
    pages: [
      'ChatPage',
      'TasksPage',
      'ToolsPage',
      'MemoryPage',
    ],
    // Components to lazy load
    components: [
      'StreamingOutput',
      'WorkflowVisualizer',
      'AnalyticsDashboard',
    ],
  },

  // Cache strategy
  cache: {
    // Service worker cache
    sw: {
      maxAge: 24 * 60 * 60 * 1000, // 24 hours
      maxSize: 50 * 1024 * 1024, // 50MB
    },
    // HTTP cache headers
    http: {
      static: 'public, max-age=31536000, immutable',
      dynamic: 'public, max-age=3600, must-revalidate',
      api: 'private, max-age=300, must-revalidate',
    },
  },

  // Resource hints
  resourceHints: {
    preconnect: [
      'https://api.example.com',
      'https://cdn.example.com',
    ],
    prefetch: [
      '/api/health',
      '/api/config',
    ],
    preload: [
      '/fonts/inter-var.woff2',
    ],
  },

  // Performance monitoring
  monitoring: {
    enabled: true,
    sampleRate: 0.1, // 10% of users
    metrics: [
      'FCP',
      'LCP',
      'CLS',
      'FID',
      'TTFB',
    ],
    thresholds: {
      FCP: 1000,
      LCP: 2500,
      CLS: 0.1,
      FID: 100,
      TTFB: 600,
    },
  },

  // Build optimization
  build: {
    // Minification
    minify: {
      terser: {
        compress: {
          drop_console: true,
          drop_debugger: true,
          passes: 2,
        },
      },
    },
    // CSS optimization
    cssMinify: 'lightningcss',
    // Rollup options
    rollup: {
      output: {
        // Limit chunk size
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
      },
    },
  },

  // Development optimization
  dev: {
    // Enable compression in dev
    compression: true,
    // Cache busting
    cacheBusting: true,
    // Source maps
    sourceMaps: true,
  },
};

export default performanceConfig;
