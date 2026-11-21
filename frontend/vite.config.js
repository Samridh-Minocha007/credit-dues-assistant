import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The proxy forwards /api/* to FastAPI, so the browser sees one origin and
// we don't need CORS settings on the backend.
//
// host: true lets other devices on the same Wi-Fi (your phone) open the dev
// app at http://<this computer's Wi-Fi address>:5173. The backend itself
// stays private to this computer: the phone only talks to this dev server,
// which passes /api requests on.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true, proxy: { "/api": "http://127.0.0.1:8000" } },
});
