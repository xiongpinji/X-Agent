import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import compression from 'vite-plugin-compression'
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig({
  plugins: [
    vue({
      // Enable template optimization
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag.startsWith('el-'),
        },
      },
    }),
    // Gzip compression
    compression({
      verbose: true,
      disable: false,
      threshold: 10240,
      algorithm: 'gzip',
      ext: '.gz',
    }),
    // Brotli compression
    compression({
      verbose: true,
      disable: false,
      threshold: 10240,
      algorithm: 'brotli',
      ext: '.br',
    }),
    // Bundle analysis
    visualizer({
      open: false,
      gzipSize: true,
      brotliSize: true,
      filename: 'dist/stats.html',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    strictPort: false,
    open: false,
    headers: {
      'Cache-Control': 'public, max-age=3600',
    },
  },
  build: {
    target: 'esnext',
    minify: 'terser',
    sourcemap: false,
    outDir: '../dist',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
        passes: 2,
      },
      format: {
        comments: false,
      },
      mangle: true,
    },
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router'],
          'vendor-ui': ['element-plus', '@element-plus/icons-vue'],
          'vendor-utils': ['axios', 'pinia'],
        },
        chunkFileNames: 'js/[name]-[hash].js',
        entryFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.')
          const ext = info[info.length - 1]
          if (/png|jpe?g|gif|svg|webp/.test(ext)) {
            return `images/[name]-[hash][extname]`
          } else if (/woff|woff2|eot|ttf|otf/.test(ext)) {
            return `fonts/[name]-[hash][extname]`
          } else if (ext === 'css') {
            return `css/[name]-[hash][extname]`
          }
          return `[name]-[hash][extname]`
        },
      },
    },
    cssCodeSplit: true,
    reportCompressedSize: true,
    chunkSizeWarningLimit: 400,
    commonjsOptions: {
      transformMixedEsModules: true,
    },
  },
  optimizeDeps: {
    include: [
      'vue',
      'vue-router',
      'element-plus',
      '@element-plus/icons-vue',
      'axios',
      'pinia',
    ],
    exclude: ['@vite/client', '@vite/env'],
  },
})

