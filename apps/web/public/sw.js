// RecallRadar service worker: an offline page for navigations, and Web Push alerts.
// Recall data is never cached: a stale verdict is worse than no verdict.
const CACHE = "recallradar-shell-v1";
const OFFLINE = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.add(OFFLINE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request).catch(() => caches.match(OFFLINE)));
});

self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(data.title || "RecallRadar", {
      body: data.body || "A recall may affect something on your list.",
      icon: "/icon/192",
      badge: "/icon/192",
      tag: data.tag,
      data: { url: data.url || "/list" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/list", self.location.origin);
  // Only open pages on this site, whatever the payload says.
  const target = url.origin === self.location.origin ? url.href : "/list";
  event.waitUntil(self.clients.openWindow(target));
});
