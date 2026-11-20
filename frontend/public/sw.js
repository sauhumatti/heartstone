// Service worker: keeps the app shell, the card art and the sound clips on the
// device, so the game opens at once and nothing reloads every match. Once the
// player has chosen "Make available offline" (src/local/offline.ts fills these
// same stores), it also holds the engine that plays on the device, and the
// whole game opens with no connection. Talking to the game server is never
// answered from here.
const SHELL = 'shell-v1';
const ART = 'art-v1';
// The on-device engine: the Python runtime (py/<version>/) and the engine pack (offline/).
const OFFLINE = 'offline-v1';
const KEPT = [SHELL, ART, OFFLINE];
const SCOPE = new URL(self.registration.scope).pathname;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => !KEPT.includes(n)).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

async function fromCacheFirst(cacheName, request) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) cache.put(request, res.clone());
  return res;
}

// Art and sound clips may be remade: use what is stored, fetch the current file for next time.
async function staleWhileRevalidate(cacheName, request) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  const fresh = fetch(request)
    .then((res) => {
      if (res.ok) cache.put(request, res.clone());
      return res;
    })
    .catch(() => hit);
  return hit || fresh;
}

// The list of what the offline game consists of: the current one when there is a
// connection, the stored one when there is none.
async function networkFirst(cacheName, request) {
  const cache = await caches.open(cacheName);
  try {
    // Not stored from here: the stored list must only ever name files that are stored too.
    return await fetch(request);
  } catch (err) {
    const hit = await cache.match(request.url);
    if (hit) return hit;
    throw err;
  }
}

// The page itself comes from the network when there is one, so a new build shows up at once.
async function pageNetworkFirst(request) {
  const cache = await caches.open(SHELL);
  try {
    const res = await fetch(request);
    if (res.ok) {
      cache.put(SCOPE, res.clone());
      // A new page means new script files: drop the ones no page refers to any more.
      const text = await res.clone().text();
      for (const key of await cache.keys()) {
        const path = new URL(key.url).pathname.slice(SCOPE.length);
        if (path.startsWith('assets/') && !text.includes(path) && /index-[^/]+\.(js|css)$/.test(path)) cache.delete(key);
      }
    }
    return res;
  } catch (err) {
    const hit = await cache.match(SCOPE);
    if (hit) return hit;
    throw err;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(SCOPE)) return;
  const path = url.pathname.slice(SCOPE.length);

  if (request.mode === 'navigate') {
    event.respondWith(pageNetworkFirst(request));
  } else if (path.startsWith('art/') || path.startsWith('sfx/') || path.startsWith('music/')) {
    event.respondWith(staleWhileRevalidate(ART, request));
  } else if (path.startsWith('assets/') || path.startsWith('icons/') || path === 'favicon.svg') {
    event.respondWith(fromCacheFirst(SHELL, request));
  } else if (path === 'offline/manifest.json') {
    event.respondWith(networkFirst(OFFLINE, request));
  } else if (path.startsWith('py/') || path.startsWith('offline/')) {
    // Named after their version or content, so a stored copy never goes stale.
    event.respondWith(fromCacheFirst(OFFLINE, request));
  }
  // api/, ws/, audio/ and the app manifest go straight to the network.
});
