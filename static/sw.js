/**
 * OJA Campus Marketplace — Service Worker
 * Strategy: Cache-first for static assets, Network-first for pages.
 * Offline fallback page shown when network is unavailable.
 */

const CACHE_NAME    = 'oja-v1';
const STATIC_ASSETS = [
  '/',
  '/static/css/oja.css',
  '/static/img/oja_logo.png',
  '/static/img/icons/icon-192.svg',
  '/static/manifest.json',
  '/offline/',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap',
];

// ── Install: cache static assets ──
self.addEventListener('install', function(event) {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS.filter(url => !url.startsWith('http')));
    }).catch(function(err) {
      console.warn('[SW] Install cache error:', err);
    })
  );
});

// ── Activate: clean old caches ──
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

// ── Fetch: smart caching strategy ──
self.addEventListener('fetch', function(event) {
  var req = event.request;
  var url = new URL(req.url);

  // Skip non-GET, external, or API requests
  if (req.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/paystack/') || url.pathname.startsWith('/upgrade/')) return;
  if (url.pathname.startsWith('/admin/')) return;

  // Static assets → Cache first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then(function(cached) {
        if (cached) return cached;
        return fetch(req).then(function(response) {
          if (response.ok) {
            var clone = response.clone();
            caches.open(CACHE_NAME).then(function(cache) { cache.put(req, clone); });
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML pages → Network first, fall back to cache, then offline page
  event.respondWith(
    fetch(req).then(function(response) {
      if (response.ok && req.headers.get('accept') && req.headers.get('accept').includes('text/html')) {
        var clone = response.clone();
        caches.open(CACHE_NAME).then(function(cache) { cache.put(req, clone); });
      }
      return response;
    }).catch(function() {
      return caches.match(req).then(function(cached) {
        if (cached) return cached;
        if (req.headers.get('accept') && req.headers.get('accept').includes('text/html')) {
          return caches.match('/offline/');
        }
        return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
      });
    })
  );
});

// ── Push Notifications ──
self.addEventListener('push', function(event) {
  var data = event.data ? event.data.json() : {};
  var title   = data.title   || 'OJA Campus';
  var body    = data.body    || 'You have a new notification';
  var icon    = data.icon    || '/static/img/icons/icon-192.svg';
  var badge   = data.badge   || '/static/img/icons/icon-192.svg';
  var url     = data.url     || '/notifications/';

  event.waitUntil(
    self.registration.showNotification(title, {
      body:    body,
      icon:    icon,
      badge:   badge,
      tag:     data.tag || 'oja-notification',
      data:    { url: url },
      actions: [
        { action: 'view',    title: 'View' },
        { action: 'dismiss', title: 'Dismiss' },
      ],
    })
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  if (event.action === 'dismiss') return;
  var url = event.notification.data && event.notification.data.url ? event.notification.data.url : '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        var client = clientList[i];
        if (client.url === url && 'focus' in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});