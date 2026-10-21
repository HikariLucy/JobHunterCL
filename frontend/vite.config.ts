/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo, Vite (5173) reenvía /api al backend FastAPI local.
const API = process.env.JOBHUNTER_API ?? "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: API, changeOrigin: false } },
  },
  preview: { host: "127.0.0.1" },
  build: { outDir: "dist", sourcemap: false },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
