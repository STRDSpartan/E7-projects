import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En développement, /api et /media sont relayés vers FastAPI (même origine → cookie de session).
const backend = process.env.E7S_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: backend, ws: true },
      "/media": backend,
    },
  },
});
