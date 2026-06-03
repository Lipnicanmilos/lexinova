const CACHE_NAME = 'wordkeeper-v5';
const ASSETS_TO_CACHE = [
  '/',
  '/dashboard',
  '/login',
  '/register',
  '/test',
  '/repeat',
  '/profile',
  '/static/css/style.css',
  '/manifest.json',
  '/favicon.ico',
  '/apple-touch-icon.png',
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
  self.skipWaiting(); // Vynúti aktiváciu novej verzie hneď po inštalácii
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
  self.clients.claim(); // Prevezme kontrolu nad všetkými klientmi okamžite
});

// Fetch stratégia
// - Navigácie (mode: navigate): cache-first s fallback na /dashboard
// - GET requesty na HTML/Assets/API: stale-while-revalidate, s offline fallback
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  const isNavigate = event.request.mode === 'navigate';
  const isApi = url.pathname.startsWith('/api/');
  const isV1Api = url.pathname.startsWith('/api/v1/');
  const shouldHandle = isNavigate || isApi || isV1Api || url.pathname.startsWith('/static/') || url.pathname === '/' || url.pathname === '/dashboard';

  if (!shouldHandle) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      // 1) NAVIGÁCIE: cache-first
      if (isNavigate) {
        const cachedNav = await cache.match(event.request) || await cache.match(url.pathname);
        if (cachedNav) return cachedNav;
        const fallback = await cache.match('/dashboard');
        return fallback || fetch(event.request).catch(() => fallback);
      }

      // 2) API + STATIC: stale-while-revalidate
      const cachedResponse = await cache.match(event.request);

      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        })
        .catch(() => {
          // Offline fallback: ak je to API, vrátime poslednú cache ak existuje
          if (cachedResponse) return cachedResponse;

          // fallback pre navigate už riešime vyššie, tu len pre istotu
          if (!isNavigate) {
            return new Response(JSON.stringify({ error: 'offline' }), {
              status: 503,
              headers: { 'Content-Type': 'application/json' },
            });
          }
        });

      return cachedResponse || fetchPromise;
    })
  );
});
