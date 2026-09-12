import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// El proxy /api evita problemas de CORS en desarrollo: el front en :5173
// reenvía las llamadas a /api hacia el Django local en :8000.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
