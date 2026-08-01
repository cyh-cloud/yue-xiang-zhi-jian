// 粤乡智匠 Service Worker — 离线缓存策略
const CACHE_NAME = 'yuexiang-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/case-detail.html',
    '/styles.css',
    '/script.js',
    'https://cdn.bootcdn.net/ajax/libs/font-awesome/6.0.0/css/all.min.css'
];

// 安装：预缓存核心静态资源
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('[SW] 缓存核心资源');
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.warn('[SW] 部分资源缓存失败:', err);
            });
        })
    );
    self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// 请求拦截：API网络优先 / 静态资源缓存优先
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response(
                    JSON.stringify({ success: false, message: '离线模式：请检查网络连接' }),
                    { status: 503, headers: { 'Content-Type': 'application/json' } }
                );
            })
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                if (response.ok && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            });
        })
    );
});
