import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Local dev convenience: proxy API calls to a backend on :8000 so the app works
    // without VITE_API_BASE_URL. In production the deployed backend URL is used instead.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/webhooks": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
