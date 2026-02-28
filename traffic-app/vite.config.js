import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  optimizeDeps: {
    include: ['lucide-svelte']
  },
  server: {
    host: '0.0.0.0', // Important for exposure
    port: 5173, // Optional: lock to specific port
    proxy: {
      '/api': {
        target: process.env.VITE_PROD_URL || 'http://127.0.0.1:5002',
        changeOrigin: true
      },
      '/maps': {
        target: process.env.VITE_PROD_URL || 'http://127.0.0.1:5002',
        changeOrigin: true
      }
    }
  }
});
