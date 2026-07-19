/**
 * Vite Configuration for Frontend - Performance Optimized
 *
 * Build configuration with API proxy, environment variables, and advanced optimization.
 * Targets: FCP < 1s, LCP < 2.5s, TTI < 3s, Bundle < 500KB
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [
    react({
      // Enable Fast Refresh for faster HMR
      fastRefresh: true,
    }),
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@services': path.resolve(__dirname, './src/services'),
      '@store': path.resolve(__dirname, './src/store'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@utils': path.resolve(__dirname, './src/utils'),
      '@types': path.resolve(__dirname, './src/types'),
      '@i18n': path.resolve(__dirname, './src/i18n'),
    },
  },

  server: {
    port: 3000,
    strictPort: false,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
    middlewareMode: false,
    // Enable compression in dev
    headers: {
      'Cache-Control': 'public, max-age=3600',
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: process.env.NODE_ENV === 'development',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: process.env.NODE_ENV === 'production',
        drop_debugger: process.env.NODE_ENV === 'production',
        passes: 2,
        pure_funcs: ['console.log', 'console.info'],
      },
      format: {
        comments: false,
      },
      mangle: true,
    },
    // Optimization settings
    cssCodeSplit: true,
    reportCompressedSize: true,
    chunkSizeWarningLimit: 400,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        chat: path.resolve(__dirname, 'chat.html'),
        console: path.resolve(__dirname, 'console.html'),
        startup: path.resolve(__dirname, 'startup.html'),
      },
      output: {
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name?.split('.') ?? [];
          const ext = info[info.length - 1] ?? '';
          if (/png|jpe?g|gif|svg|webp/.test(ext)) {
            return 'images/[name]-[hash][extname]';
          }
          if (/woff|woff2|eot|ttf|otf/.test(ext)) {
            return 'fonts/[name]-[hash][extname]';
          }
          if (ext === 'css') {
            return 'css/[name]-[hash][extname]';
          }
          return '[name]-[hash][extname]';
        },
      },
    },
    // Increase timeout for large builds
    commonjsOptions: {
      transformMixedEsModules: true,
    },
    // Enable minification for CSS
    cssMinify: 'lightningcss',
  },

  define: {
    __DEV__: JSON.stringify(process.env.NODE_ENV === 'development'),
    __VERSION__: JSON.stringify(process.env.npm_package_version),
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },

  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'zustand',
      '@tanstack/react-query',
      'axios',
      'date-fns',
      'clsx',
      'lucide-react',
      'recharts',
    ],
    exclude: ['@vite/client', '@vite/env'],
    // Optimize dependency pre-bundling
    esbuildOptions: {
      target: 'esnext',
      supported: {
        bigint: true,
      },
    },
  },

  // Performance hints
  ssr: {
    noExternal: [],
  },
});
