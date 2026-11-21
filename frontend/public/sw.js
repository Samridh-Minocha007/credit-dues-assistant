// Service worker: lets the installed app open without internet.
// - The app's own files (HTML, JS, CSS, fonts) are cached and served offline.
// - Data requests (/api/...) are NEVER cached: balances must always be live.
//   Entries made offline are queued by the app itself (src/offline.js).
const CACHE = "dues-app-v1";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(["/", "/manifest.webmanifest", "/icon.svg"])));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return; // live data only
  if (e.request.mode === "navigate") {
    // Pages: try the network, fall back to the cached app.
    e.respondWith(fetch(e.request).catch(() => caches.match("/")));
    return;
  }
  // Files: cached copy first, refreshed in the background.
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const fresh = fetch(e.request).then((res) => {
        if (res.ok) caches.open(CACHE).then((c) => c.put(e.request, res.clone()));
        return res;
      });
      return hit || fresh;
    })
  );
});
