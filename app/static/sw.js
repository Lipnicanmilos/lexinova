const CACHE_NAME = 'wordkeeper-v8';
const ASSETS_TO_CACHE = [
  '/manifest.json',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
  // Auth stránky (dashboard, login, atď.) sa cachujú dynamicky pri návšteve,
  // nie pri install — server by vrátil redirect (nie 200) pre neprihlásených
];

// Inštalácia - cachovanie základných súborov
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker...');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching assets...');
      return cache.addAll(ASSETS_TO_CACHE).catch(err => {
        console.warn('[SW] Some assets failed to cache (expected for some files):', err);
        // Ak sa nejaké súbory nepodarí cachovať, pokračujeme
        return cache.addAll(ASSETS_TO_CACHE.filter(url => 
          !url.includes('.css') && !url.includes('.js')
        ));
      });
    })
  );
  self.skipWaiting();
});

// Aktivácia - vymazanie starej cache
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// ✅ NOVÉ: Offline fallback dáta pre API
const OFFLINE_FALLBACK_DATA = {
  // /api/v1/categories vracia priamo pole kategórií, nie objekt
  categories: [],
  user: { error: 'offline', offline: true },
  // /api/user/stats očakáva words_by_level.{dont_know, learning, know}
  stats: {
    total_words: 0,
    total_categories: 0,
    tests_taken: 0,
    success_rate: 0,
    words_by_level: { dont_know: 0, learning: 0, know: 0 }
  }
};


// Fetch stratégia - s vylepšeným offline handlingom
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    console.log('[SW] Ignoring non-GET request:', event.request.url);
    return;
  }

  const url = new URL(event.request.url);
  const isNavigate = event.request.mode === 'navigate';
  const isApi = url.pathname.startsWith('/api/');
  const isStatic = url.pathname.startsWith('/static/');
  const isManifest = url.pathname === '/manifest.json' || url.pathname === '/sw.js';
  const isMainPage = url.pathname === '/' || url.pathname === '/dashboard';

  // Ignorujeme: login, register (nemajú offline zmysel)
  const shouldSkip = url.pathname.includes('login') || url.pathname.includes('register');
  
  if (shouldSkip && !isNavigate) {
    console.log('[SW] Skipping:', url.pathname);
    return;
  }

  event.respondWith(
    (async () => {
      try {
        // 1) NAVIGÁCIE: network-first s cache fallback
        if (isNavigate) {
          console.log('[SW] Navigation request:', url.pathname);
          try {
            const networkResponse = await fetch(event.request);
            if (networkResponse.status === 200) {
              const cache = await caches.open(CACHE_NAME);
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          } catch (err) {
            console.log('[SW] Network failed for navigation, using cache:', url.pathname);
            const cachedResponse = await caches.match(event.request) ||
                                   await caches.match(url.pathname);
            if (cachedResponse) return cachedResponse;

            // Offline fallback — zobraz offline stránku (nepresmieruj na dashboard)
            return new Response(`<!DOCTYPE html>
<html lang="sk">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Offline – WordKeeper</title>
  <style>
    body { font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f4f7fe; color: #333; text-align: center; padding: 2rem; box-sizing: border-box; }
    .icon { font-size: 4rem; margin-bottom: 1rem; }
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
    p { color: #666; margin-bottom: 2rem; }
    a { background: #4079ff; color: #fff; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: 600; }
  </style>
</head>
<body>
  <div class="icon">📶</div>
  <h1>Ste offline</h1>
  <p>Táto stránka nie je dostupná bez pripojenia.<br>Vráťte sa na dashboard kde sú uložené vaše dáta.</p>
  <a href="/dashboard">← Dashboard</a>
</body>
</html>`, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
          }
        }

        // 2) MANIFEST a SW: network-first, bez cache (vždy chceme najnovší)
        if (isManifest) {
          console.log('[SW] Manifest/SW request (no-cache policy):', url.pathname);
          try {
            const response = await fetch(event.request);
            if (response.status === 200) {
              const cache = await caches.open(CACHE_NAME);
              cache.put(event.request, response.clone());
            }
            return response;
          } catch (err) {
            const cached = await caches.match(event.request);
            return cached || new Response('{}', { status: 503 });
          }
        }

        // 3) API REQUESTY: stale-while-revalidate s offline fallback
        if (isApi) {
          console.log('[SW] API request:', url.pathname);
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match(event.request);

          // ✅ NOVÉ: Vrátim cached data ak existuje (offline)
          const fetchPromise = fetch(event.request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                console.log('[SW] API response cached:', url.pathname);
                cache.put(event.request, networkResponse.clone());
              }
              return networkResponse;
            })
            .catch((err) => {
              console.log('[SW] API fetch failed, using cache for:', url.pathname);
              if (cachedResponse) {
                return cachedResponse;
              }

              // ✅ NOVÉ: Fallback na dummy dáta pre známe API endpointy
              const pathname = url.pathname;
              if (pathname.includes('/api/v1/categories')) {
                return new Response(JSON.stringify(OFFLINE_FALLBACK_DATA.categories), {
                  status: 200,
                  headers: { 'Content-Type': 'application/json', 'X-Offline': 'true' }
                });
              }

              if (pathname.includes('/api/user/stats')) {
                return new Response(JSON.stringify(OFFLINE_FALLBACK_DATA.stats), {
                  status: 200,
                  headers: { 'Content-Type': 'application/json', 'X-Offline': 'true' }
                });
              }
              if (pathname.includes('/api/user')) {
                return new Response(JSON.stringify(OFFLINE_FALLBACK_DATA.user), {
                  status: 200,
                  headers: { 'Content-Type': 'application/json', 'X-Offline': 'true' }
                });
              }

              // Default error response (vraciame status 200, aby frontend nespadol do presmerovania)
              return new Response(JSON.stringify({ error: 'offline', offline: true }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
              });

            });

          // Return cached if available, otherwise wait for network
          return cachedResponse || fetchPromise;
        }

        // 4) STATICKÉ SÚBORY: stale-while-revalidate
        if (isStatic) {
          console.log('[SW] Static file request:', url.pathname);
          const cache = await caches.open(CACHE_NAME);
          const cachedResponse = await cache.match(event.request);

          const fetchPromise = fetch(event.request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                cache.put(event.request, networkResponse.clone());
              }
              return networkResponse;
            })
            .catch((err) => {
              console.log('[SW] Static fetch failed, using cache:', url.pathname);
              return cachedResponse;
            });

          return cachedResponse || fetchPromise;
        }

        // 5) OSTATNÉ REQUESTY
        console.log('[SW] Other request (passthrough):', url.pathname);
        return await fetch(event.request);

      } catch (error) {
        console.error('[SW] Fetch handler error:', error);
        return new Response('Service Worker error', { status: 500 });
      }
    })()
  );
});

// ✅ NOVÉ: Periodické skúšanie internetu a aktualizácia cache
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// --- Offline notifications (local) ---
// Používame jednoduchý mechanizmus: keď stránka pošle message typu
// { type: 'SHOW_NOTIFICATION', title, body } tak SW zobrazí notifikáciu.
self.addEventListener('message', (event) => {
  try {
    const data = event.data;
    if (!data || data.type !== 'SHOW_NOTIFICATION') return;

    const title = data.title || 'WordKeeper';
    const options = {
      body: data.body || '',
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/icon-192x192.png',
      tag: data.tag || 'wordkeeper-offline',
      renotify: true
    };

    event.waitUntil(self.registration.showNotification(title, options));
  } catch (e) {
    // ignoruj
  }
});

console.log('[SW] Service Worker loaded successfully!');