import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: false },
      '/health': { target: BACKEND, changeOrigin: false },
    },
  },
  preview: {
    proxy: {
      '/api': { target: BACKEND },
      '/health': { target: BACKEND },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
    restoreMocks: true,
  },
});
