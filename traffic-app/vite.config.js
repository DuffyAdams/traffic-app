import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: '0.0.0.0', // Important for exposure
    port: 5173, // Optional: lock to specific port
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/maps': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  }
});
