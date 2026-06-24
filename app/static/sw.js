const CACHE_NAME = 'lexinova-v16';
const ASSETS_TO_CACHE = [
  '/manifest.json',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/js/offline-cache.js',
];

self.addEventListener('install', (event) => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) return caches.delete(cacheName);
          return Promise.resolve();
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Iba GET requesty cachujeme; POST/PUT/... vzdy do siete.
  if (event.request.method !== 'GET') {
    event.respondWith(fetch(event.request));
    return;
  }

  // Auth endpointy + dashboard navigacie - nikdy neinterceptujeme.
  // Browser musi spracovat Set-Cookie nativne. Pri OAuth flow navigate-mode fetch()
  // v SW kontexte moze stratit cookie nastavenu v rovnakom response cykle.
  if (url.pathname.startsWith('/auth/') || event.request.mode === 'navigate') {
    return;
  }

  const isStaticAsset = url.pathname.startsWith('/static/') || url.pathname === '/manifest.json';
  const isApi = url.pathname.startsWith('/api/');

  // API nikdy necachujeme ani nemaskujeme - vzdy siet.
  if (isApi) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Staticke assety: cache-first, potom siet (a uloz do cache).
  if (isStaticAsset) {
    event.respondWith(
      caches.match(event.request).then(async (cached) => {
        if (cached) return cached;
        const res = await fetch(event.request);
        if (res && res.status === 200) {
          const cache = await caches.open(CACHE_NAME);
          cache.put(event.request, res.clone());
        }
        return res;
      })
    );
    return;
  }

  // Vsetko ostatne: iba siet.
  event.respondWith(fetch(event.request));
});

self.addEventListener('message', (event) => {
  if (!event.data) return;
  if (event.data.type === 'SKIP_WAITING') self.skipWaiting();
  if (event.data.type === 'SHOW_NOTIFICATION') {
    const { title, body, tag } = event.data;
    event.waitUntil(
      self.registration.showNotification(title || 'LexiNova', {
        body: body || '',
        tag: tag || 'lexinova',
        icon: '/static/icons/icon-192x192.png',
      })
    );
  }
});

console.log('[SW] Service Worker v16 loaded');
