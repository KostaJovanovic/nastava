// Shows the notifications ci/push.py sends, {title, body, url}; a click opens the url. site.js registers it and
// subscribes.
self.addEventListener("push", (e) => {
	let m = {};
	try {
		m = e.data ? e.data.json() : {};
	} catch (err) {}
	e.waitUntil(self.registration.showNotification(m.title || "Arhiva nastave", { body: m.body || "", data: m.url || "/", icon: "/static/icon-192.png", badge: "/static/badge.png" }));
});

self.addEventListener("notificationclick", (e) => {
	e.notification.close();
	e.waitUntil(self.clients.openWindow(e.notification.data));
});
