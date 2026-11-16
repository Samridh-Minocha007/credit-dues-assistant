import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The proxy forwards /api/* to FastAPI, so the browser sees one origin and
// we don't need CORS settings on the backend.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
