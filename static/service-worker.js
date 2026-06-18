// Service Worker for Smart Waste Management PWA
const CACHE_NAME = 'smart-waste-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/manifest.json',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap'
];

// Install Service Worker
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching files');
        return cache.addAll(urlsToCache);
      })
      .catch(err => console.log('Service Worker: Cache failed', err))
  );
});

// Activate Service Worker
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Service Worker: Clearing old cache');
            return caches.delete(cache);
          }
        })
      );
    })
  );
});

// Fetch Event - Network First, then Cache
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Clone the response
        const responseClone = response.clone();
        
        // Cache the fetched response
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, responseClone);
        });
        
        return response;
      })
      .catch(() => {
        // If network fails, try cache
        return caches.match(event.request);
      })
  );
});

// Background Sync for offline uploads
self.addEventListener('sync', event => {
  if (event.tag === 'sync-uploads') {
    event.waitUntil(syncUploads());
  }
});

async function syncUploads() {
  // Sync any pending uploads when back online
  console.log('Service Worker: Syncing uploads...');
}

// Push Notifications
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Smart Waste Management';
  const options = {
    body: data.body || 'New notification',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      url: data.url || '/'
    }
  };
  
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Notification Click
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.openWindow(event.notification.data.url)
  );
});
