// Shows the notifications ci/push.py sends, {title, body, url}; a click opens the url. site.js registers it and
// subscribes. One with no data is the Worker's: a new message from the contact form (src/index.js notify).
self.addEventListener("push", (e) => {
	let m = { title: "Nova poruka na sajtu", url: "/kontakt/poruke/" };
	try {
		if (e.data) m = e.data.json();
	} catch (err) {}
	e.waitUntil(self.registration.showNotification(m.title || "Arhiva nastave", { body: m.body || "", data: m.url || "/", icon: "/static/icon-192.png", badge: "/static/badge.png" }));
});

self.addEventListener("notificationclick", (e) => {
	e.notification.close();
	e.waitUntil(self.clients.openWindow(e.notification.data));
});
