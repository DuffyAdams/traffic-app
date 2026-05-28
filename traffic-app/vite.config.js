import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  optimizeDeps: {
    include: ['lucide-svelte']
  },
  server: {
    host: process.env.VITE_DEV_HOST || '0.0.0.0',
    port: Number(process.env.VITE_DEV_PORT || 5173),
    strictPort: true,
    allowedHosts: ['traffic-app.duffyadams.com'],
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
