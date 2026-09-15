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
    react(),
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
    port: 3001,
    strictPort: false,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      },
      // /health 必须显式代理：否则命中 SPA fallback 返回 200+index.html，
      // 前端健康检查解析不出 status（chat.html 设置页曾误报"异常"）
      '/health': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
    middlewareMode: false,
    // 注意：不设全局 Cache-Control——vite dev 的 HTR/HMR 依赖协商缓存，
    // 全局 max-age 会缓存旧模块与 SPA fallback（曾致 /health 返回 index.html）
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
