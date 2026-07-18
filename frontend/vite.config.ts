import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the control-plane API at VITE_API_URL (default :8000)
// with CORS enabled server-side, so no dev proxy is needed.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
