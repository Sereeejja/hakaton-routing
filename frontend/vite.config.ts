import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1_100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("maplibre-gl") || id.includes("@mapbox") || id.includes("/pbf/") || id.includes("/gl-matrix/")) return "map";
          if (id.includes("react-dom") || id.includes("/react/") || id.includes("lucide-react")) return "ui";
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/healthz": "http://localhost:8080",
      "/swagger": "http://localhost:8080"
    }
  }
});
