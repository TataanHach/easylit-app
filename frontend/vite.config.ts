import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// En desarrollo, el proxy /api reenvía las llamadas al Django local en :8000
// (en Render el frontend llama directo a VITE_API_URL).
export default defineConfig(({ mode }) => {
  // Dónde corre el backend en desarrollo (VITE_PROXY_API en frontend/.env).
  const destinoApi = loadEnv(mode, process.cwd(), "").VITE_PROXY_API || "http://localhost:8000";
  return {
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: destinoApi, changeOrigin: true },
    },
  },
  };
});
