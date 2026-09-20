/**
 * Vite Configuration for Frontend
 *
 * Rewritten during T12 (2026-09): the previous file imported packages that
 * were never in package.json (vite-plugin-compression, rollup-plugin-visualizer,
 * @babel/plugin-proposal-decorators, terser, lightningcss), contained a
 * duplicate `rollupOptions` key (the second silently overrode the first) and
 * nested terser options inside the react() plugin config. The build could
 * never run. This version only uses installed tooling; gzip/brotli compression
 * is expected at the reverse-proxy layer in production.
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],

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
      },
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: process.env.NODE_ENV === 'development',
    cssCodeSplit: true,
    reportCompressedSize: true,
    chunkSizeWarningLimit: 400,
    rollupOptions: {
      // index.html is the vanilla-JS console served by the backend; the React
      // app builds from its own entry (see app.html header note).
      input: {
        main: path.resolve(__dirname, 'index.html'),
        app: path.resolve(__dirname, 'app.html'),
      },
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-state': ['zustand', '@tanstack/react-query'],
          'vendor-ui': ['lucide-react', 'recharts'],
          'vendor-utils': ['axios', 'date-fns', 'clsx'],
        },
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const name = assetInfo.name ?? '';
          const ext = name.split('.').pop() ?? '';
          if (/png|jpe?g|gif|svg|webp/.test(ext)) {
            return 'images/[name]-[hash][extname]';
          }
          if (/woff2?|eot|ttf|otf/.test(ext)) {
            return 'fonts/[name]-[hash][extname]';
          }
          if (ext === 'css') {
            return 'css/[name]-[hash][extname]';
          }
          return '[name]-[hash][extname]';
        },
      },
    },
    commonjsOptions: {
      transformMixedEsModules: true,
    },
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
  },
});
