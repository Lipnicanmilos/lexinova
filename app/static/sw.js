const CACHE_NAME = 'wordkeeper-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/dashboard',
  '/login',
  '/register',
  '/static/css/style.css',
  '/manifest.json',
  '/favicon.ico',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// Inštalácia - cachovanie základných súborov
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
});

// Aktivácia - vymazanie starej cache
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Fetch stratégia - Network First (pre dynamický obsah ako dashboard)
self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request).then((response) => {
        if (response) return response;
        // Ak zlyhá sieť a ide o navigáciu, vráť dashboard (offline shell)
        if (event.request.mode === 'navigate') {
          return caches.match('/dashboard');
        }
      });
    })
  );
});