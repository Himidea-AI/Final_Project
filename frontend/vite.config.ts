import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    process.env.ANALYZE &&
      visualizer({
        filename: 'dist/stats.html',
        template: 'treemap',
        open: true,
        gzipSize: true,
        brotliSize: true,
      }),
  ].filter(Boolean),
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/vacancy-evaluation': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Phase B 번들 splitting — vendor 분리로 메인 chunk 축소 + 캐시 효율 향상
        // (jspdf/html2canvas/xlsx은 이미 동적 import → 자동 분리됨)
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart-vendor': ['recharts'],
          'motion-vendor': ['framer-motion'],
          'icons-vendor': ['lucide-react'],
        },
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Phase B 번들 splitting — vendor 분리로 메인 chunk 축소 + 캐시 효율 향상
        // (jspdf/html2canvas/xlsx은 이미 동적 import → 자동 분리됨)
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart-vendor': ['recharts'],
          'motion-vendor': ['framer-motion'],
          'icons-vendor': ['lucide-react'],
        },
      },
    },
  },
});
