import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig(({ mode }) => {
  const proxyTarget =
    process.env.VITE_PROD_URL ||
    (mode === "proxy"
      ? "https://sandiegotraffic.com"
      : "http://127.0.0.1:5002");

  return {
    plugins: [svelte()],
    build: {
      // MapLibre is already lazy-loaded into its own chunk; its renderer is
      // intentionally larger than Vite's generic warning threshold.
      chunkSizeWarningLimit: 1100,
    },
    optimizeDeps: {
      include: ["lucide-svelte"],
    },
    server: {
      host: process.env.VITE_DEV_HOST || "0.0.0.0",
      port: Number(process.env.VITE_DEV_PORT || 5173),
      strictPort: true,
      allowedHosts: ["traffic-app.duffyadams.com"],
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
        "/maps": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
