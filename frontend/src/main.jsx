import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Mukta: an Indian typeface (Ek Type) with Latin and Devanagari, so Hindi
// text will match when we add it. Bundled locally, no outside requests.
import "@fontsource/mukta/400.css";
import "@fontsource/mukta/600.css";
import "@fontsource/mukta/700.css";
import "@fontsource/mukta/devanagari-400.css";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
