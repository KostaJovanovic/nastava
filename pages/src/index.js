// Serve the site from GitHub Pages through the edge cache. The attachments link straight to the faculty's site.
// The site is public: there is no auth.
const PAGES = "https://kostajovanovic.github.io/nastava";
// Most pages are stored as a fragment, <html lang="sr"> with their <title> and main part; join() puts it into
// shell.html (build.py split_page). A whole page starts with <!doctype html>. pages/serve.py joins the same way.
const FRAGMENT = '<html lang="sr"><title>';
// Pagefind file names have a content hash, except these entry files.
const ENTRY = /^\/pagefind\/pagefind[^/]*\.(js|json|css)$/;
const YEAR = 31536000;

function cacheControl(path) {
	if (path.startsWith("/pagefind/") && !ENTRY.test(path)) return `public, max-age=${YEAR}, immutable`;
	// An item or a news post rarely changes, but its side panel (counts, links) and an edited post do: a day, at the
	// edge too.
	if (path.startsWith("/item/") || path.startsWith("/vest/")) return "public, max-age=86400";
	// The home page, /static/ and the Pagefind entry files change with each deploy.
	return "public, max-age=300";
}

async function page(url) {
	const response = await fetch(PAGES + url.pathname + url.search, { redirect: "manual" });
	// GitHub Pages adds the trailing slash with a redirect to the project path.
	const location = response.headers.get("Location");
	if (location?.startsWith(PAGES + "/")) {
		return new Response(null, { status: response.status, headers: { Location: location.slice(PAGES.length) } });
	}
	if (response.status !== 200 || !response.headers.get("Content-Type")?.startsWith("text/html")) return response;
	// A whole page goes out untouched; only a fragment is read and joined.
	const fragment = await response.clone().text();
	if (!fragment.startsWith(FRAGMENT)) return response;
	const shell = await fetch(PAGES + "/shell.html");
	if (!shell.ok) return new Response("shell.html missing", { status: 502 });
	return new Response(join(await shell.text(), fragment), response);
}

// The fragment's own head (<title>, description, canonical) ends at this mark; the main part follows.
const HEAD_END = "<!--/head-->";

export function join(shell, fragment) {
	const start = fragment.indexOf("<title>");
	const mark = fragment.indexOf(HEAD_END);
	// A fragment built before the mark: its head is the <title> alone.
	const end = mark < 0 ? fragment.indexOf("</title>") + "</title>".length : mark;
	const head = fragment.slice(start, end);
	const main = fragment.slice(mark < 0 ? end : mark + HEAD_END.length, fragment.lastIndexOf("</html>"));
	// Function replacements: a "$&" in a post must stay as it is.
	return shell.replace("<title></title>", () => head).replace("<!--main-->", () => main);
}

// Web push: a browser's subscription with its followed subjects (site.js), in KV (binding PUSH): the key is the
// push service's endpoint, the value {k, a, s} its keys and the subjects' hrefs. ci/push.py reads them all with the
// secret PUSH_KEY and sends; an endpoint the service no longer knows it drops with s = [] as a browser does.
// Only the browsers' push services: ci/push.py posts to these URLs.
const PUSH_HOST = /^https:\/\/([a-z0-9-]+\.)*(fcm\.googleapis\.com|push\.services\.mozilla\.com|push\.apple\.com|notify\.windows\.com)\//;
const SUBJECT = /^\/predmet\/[a-z0-9-]+\/[a-z0-9-]+\/$/;
const B64URL = /^[A-Za-z0-9_-]{1,200}$/;

async function push(request, env, url) {
	const status = (code) => new Response(null, { status: code });
	if (!env.PUSH) return status(503);
	if (url.pathname === "/push/subs") {
		if (!env.PUSH_KEY || request.headers.get("Authorization") !== `Bearer ${env.PUSH_KEY}`) return status(403);
		// 500 a call (a KV read each, under the 1000 a Worker call may make); ci/push.py asks again with the cursor.
		const page = await env.PUSH.list({ limit: 500, cursor: url.searchParams.get("cursor") || undefined });
		const subs = await Promise.all(page.keys.map(async (k) => ({ endpoint: k.name, ...(await env.PUSH.get(k.name, "json")) })));
		return Response.json({ subs, cursor: page.list_complete ? null : page.cursor });
	}
	if (request.method !== "POST") return status(405);
	let body;
	try {
		body = await request.json();
	} catch (e) {
		return status(400);
	}
	const { endpoint, keys, s } = body || {};
	if (typeof endpoint !== "string" || endpoint.length > 500 || !PUSH_HOST.test(endpoint) || !Array.isArray(s)) return status(400);
	if (!s.length) {
		await env.PUSH.delete(endpoint);
		return status(204);
	}
	if (!B64URL.test(keys?.p256dh) || !B64URL.test(keys?.auth) || s.length > 300 || !s.every((h) => SUBJECT.test(h))) return status(400);
	await env.PUSH.put(endpoint, JSON.stringify({ k: keys.p256dh, a: keys.auth, s }));
	return status(204);
}

// Visitor counter, as on valjdakosta.com: each IP counts once per three-day period (D1 binding DB, schema.sql). The
// IPs older than that are deleted, so the total is kept on its own. site.js posts from every page; /statistika/ shows n.
async function visit(request, env) {
	if (request.method !== "POST") return new Response(null, { status: 405 });
	if (!env.DB) return new Response(null, { status: 503 });
	const ip = request.headers.get("CF-Connecting-IP") || "";
	const { meta } = await env.DB
		.prepare("INSERT OR IGNORE INTO visits (ip, period) VALUES (?, date(cast(julianday('now') / 3 as integer) * 3))")
		.bind(ip).run();
	if (meta.changes) {
		await env.DB.batch([
			env.DB.prepare("UPDATE visit_total SET n = n + 1"),
			env.DB.prepare("DELETE FROM visits WHERE period < date('now', '-3 days')"),
		]);
	}
	const { n } = await env.DB.prepare("SELECT n FROM visit_total").first();
	return Response.json({ n });
}

export default {
	async fetch(request, env, ctx) {
		const url = new URL(request.url);
		// Before the cache: these are not pages.
		if (url.pathname === "/push" || url.pathname === "/push/subs") return push(request, env, url);
		if (url.pathname === "/visit") return visit(request, env);
		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
		}
		// One domain for search engines and links: the second one moves there (/push stays: its subscriptions).
		if (url.hostname === "nastava.valjdakosta.com") {
			url.hostname = "nastava.masinci.org";
			return Response.redirect(url.toString(), 301);
		}
		const key = new Request(url.toString());
		const cached = await caches.default.match(key);
		if (cached) {
			// The zone's Browser Cache TTL replaces Cache-Control on a cached response, so set it again.
			const response = new Response(cached.body, cached);
			response.headers.set("Cache-Control", cacheControl(url.pathname));
			return response;
		}
		const origin = await page(url);
		// Cache only a 200: a 404 for a new Pagefind file must not stay in the cache.
		if (origin.status !== 200) return origin;
		const response = new Response(origin.body, origin);
		response.headers.delete("Expires");
		response.headers.set("Cache-Control", cacheControl(url.pathname));
		ctx.waitUntil(caches.default.put(key, response.clone()));
		return response;
	},
};
