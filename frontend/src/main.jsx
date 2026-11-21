import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
// Mukta: an Indian typeface (Ek Type) with Latin and Devanagari, so Hindi
// text will match when we add it. Bundled locally, no outside requests.
import "@fontsource/mukta/400.css";
import "@fontsource/mukta/600.css";
import "@fontsource/mukta/700.css";
import "@fontsource/mukta/devanagari-400.css";
import "@fontsource/mukta/devanagari-600.css";
import "@fontsource/mukta/devanagari-700.css";
import App from "./App.jsx";
import { getLang } from "./i18n.jsx";
import { startAutoSync } from "./offline.js";
import "./styles.css";

// Re-mount the app when the language changes, so every t("...") re-runs.
function Root() {
  const [lang, setLangState] = useState(getLang());
  useEffect(() => {
    const onChange = () => setLangState(getLang());
    window.addEventListener("lang-change", onChange);
    return () => window.removeEventListener("lang-change", onChange);
  }, []);
  return <App key={lang} />;
}

// Installable app: register the service worker in the built app only (in
// development it would cache files you're still editing).
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}
startAutoSync();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Root />
  </StrictMode>
);
