import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config suitable for Tauri + web dev
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true
  },
  clearScreen: false
});
