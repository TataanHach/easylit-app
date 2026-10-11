import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// El proxy /api reenvía las llamadas al Django local en :8000. Así, cuando
// ngrok expone el puerto 5173 (frontend), el backend también queda accesible
// a través del mismo túnel, sin necesidad de exponer dos puertos.
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
    // Permitir que ngrok (y cualquier subdominio suyo) sirva la app. Sin esto,
    // Vite bloquea el dominio del túnel por seguridad ("host not allowed").
    allowedHosts: [".ngrok-free.app", ".ngrok.app", ".ngrok.io"],
    proxy: {
      "/api": { target: destinoApi, changeOrigin: true },
    },
  },
  };
});
