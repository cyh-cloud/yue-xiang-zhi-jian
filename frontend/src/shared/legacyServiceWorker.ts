const LEGACY_SERVICE_WORKER_PATH = "/sw.js";
const LEGACY_CACHE_PATTERN = /^yuexiang-v\d+$/;

export function isLegacyServiceWorker(
  registration: ServiceWorkerRegistration,
): boolean {
  return [
    registration.active?.scriptURL,
    registration.installing?.scriptURL,
    registration.waiting?.scriptURL,
  ].some((scriptURL) => {
    if (!scriptURL) return false;
    try {
      return new URL(scriptURL).pathname === LEGACY_SERVICE_WORKER_PATH;
    } catch {
      return false;
    }
  });
}

export function isLegacyCacheName(cacheName: string): boolean {
  return LEGACY_CACHE_PATTERN.test(cacheName);
}

export async function clearLegacyServiceWorker(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;

  try {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(
      registrations
        .filter(isLegacyServiceWorker)
        .map((registration) => registration.unregister()),
    );
  } catch {
    // Service worker cleanup is best effort.
  }

  if (!("caches" in window)) return;

  try {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter(isLegacyCacheName)
        .map((cacheName) => caches.delete(cacheName)),
    );
  } catch {
    // Cache cleanup must not block application startup.
  }
}
