const CACHE_NAME = 'iraq-school-portal-v1';

// الملفات والصفحات المطلوب حفظها محلياً للعمل بدون إنترنت
const STATIC_ASSETS = [
    '/portal/',
    '/portal/registry/',
    '/portal/exam-halls/',
    '/portal/promotion/',
    '/portal/letter-builder/',
    '/static/manifest.json',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.rtl.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js'
];

// تثبيت الـ Service Worker وحفظ الأصول الأساسية
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// تنشيط وتطهير النسخ القديمة من الكاش
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// استراتيجية جلب البيانات (Network-first with offline cache fallback)
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                // تحديث الكاش بالبيانات الأحدث إن توفر الاتصال
                return caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, networkResponse.clone());
                    return networkResponse;
                });
            })
            .catch(() => {
                // في حال انقطاع الشبكة، جلب الصفحة من الكاش المحلي
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    if (event.request.mode === 'navigate') {
                        return caches.match('/portal/');
                    }
                });
            })
    );
});