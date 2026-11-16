// Operation JARVIS — Mobile PWA Service Worker (jarvis-pwa-v2)
// Network-First strategy ensures Android devices always receive latest UI and upload capabilities.

const CACHE_NAME = "jarvis-pwa-v2";
const ASSETS_TO_CACHE = [
  "/pwa/",
  "/pwa/index.html",
  "/pwa/style.css?v=20261107_v2",
  "/pwa/app.js?v=20261107_v2",
  "/pwa/manifest.json"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => {
          console.log("[ServiceWorker] Purging legacy cache:", k);
          return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  // 1. API Calls: Never intercept API calls in the Service Worker.
  // Let the browser manage API traffic directly via native HTTP connections.
  // This avoids Chromium ServiceWorker multipart/FormData upload drops,
  // eliminates the 30-second SW watchdog timeout on deep LLM inference,
  // and guarantees native connection error reporting.
  if (event.request.url.includes("/api/")) {
    return;
  }

  // 2. Shell Assets: Network-First with cache fallback
  // Guarantees Android phones never get trapped on stale HTML/CSS/JS caches
  event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200 && event.request.method === "GET") {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request);
        })
    );
  }
});

self.addEventListener("message", event => {
  if (event.data && event.data.action === "skipWaiting") {
    self.skipWaiting();
  }
});
