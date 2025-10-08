import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/bundle': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
      '/blocks': {
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
    },
  },
});

