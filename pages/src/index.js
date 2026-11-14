// Serve the site from GitHub Pages through the edge cache. The board's attachments link straight to the faculty's
// site; the mails' and Teams files (mail/) come from the GitHub release "mail" (/files/). The site is public: no auth.
const PAGES = "https://kostajovanovic.github.io/nastava";
const RELEASES = "https://github.com/KostaJovanovic/nastava/releases/download";
// Most pages are stored as a fragment, <html lang="sr"> with their <title> and main part; join() puts it into
// shell.html (build.py split_page). A whole page starts with <!doctype html>. pages/serve.py joins the same way.
const FRAGMENT = '<html lang="sr"><title>';
// Pagefind file names have a content hash, except these entry files.
const ENTRY = /^\/pagefind\/pagefind[^/]*\.(js|json|css)$/;
const YEAR = 31536000;

function cacheControl(url) {
	const path = url.pathname;
	// An asset never changes: a changed file is a new path, so a new asset (mail.py asset_name).
	if (path.startsWith("/files/")) return `public, max-age=${YEAR}, immutable`;
	if (path.startsWith("/pagefind/") && !ENTRY.test(path)) return `public, max-age=${YEAR}, immutable`;
	// An item or a news post rarely changes, but its side panel (counts, links) and an edited post do: a day, at the
	// edge too.
	if (path.startsWith("/item/") || path.startsWith("/vest/")) return "public, max-age=86400";
	// A /static/ file the pages link with ?v=<its hash> (build.py VERSIONED: the icons, CSS, JS): a changed file is a
	// new URL. shortcut: a request in the minute GitHub Pages still serves the old file keeps it a year under the new
	// hash; if a deploy ever shows that, check the body's hash here before caching.
	if (path.startsWith("/static/") && url.searchParams.has("v")) return `public, max-age=${YEAR}, immutable`;
	// The home page, /static/ and the Pagefind entry files change with each deploy.
	return "public, max-age=300";
}

// shell.html once per deploy, not once per page: GitHub Pages stamps every file of a deploy with the same
// Last-Modified, so the fragment's names its shell. A path GitHub Pages 404s, so the page cache never stores one there.
// A shell from another deploy (one still going out) is used but not kept.
async function shellFor(url, fragment, ctx) {
	const deploy = fragment.headers.get("Last-Modified");
	const key = deploy && new Request(`${url.origin}/__shell/${encodeURIComponent(deploy)}`);
	const kept = key && (await caches.default.match(key));
	if (kept) return kept.text();
	const shell = await fetch(PAGES + "/shell.html");
	if (!shell.ok) return null;
	if (key && shell.headers.get("Last-Modified") === deploy) {
		const copy = new Response(shell.clone().body, { headers: { "Content-Type": "text/html", "Cache-Control": "public, max-age=86400" } });
		ctx.waitUntil(caches.default.put(key, copy));
	}
	return shell.text();
}

async function page(url, ctx) {
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
	const shell = await shellFor(url, response, ctx);
	if (shell === null) return new Response("shell.html missing", { status: 502 });
	return new Response(join(shell, fragment), response);
}

async function releaseFile(path) {
	// build.py links /files/<release tag>/<asset name>/<file name> (mail_href).
	const [tag, asset, name, extra] = path.slice("/files/".length).split("/");
	if (!tag || !asset || !name || extra !== undefined) return null;
	let filename;
	try {
		filename = decodeURIComponent(name);
	} catch {
		return null;
	}
	const response = await fetch(`${RELEASES}/${encodeURIComponent(tag)}/${encodeURIComponent(asset)}`);
	if (!response.ok) return null;
	// Always a download: an uploaded HTML or SVG file must not run on this origin.
	return new Response(response.body, {
		headers: {
			"Content-Type": "application/octet-stream",
			"Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(filename)}`,
			"X-Content-Type-Options": "nosniff",
		},
	});
}

// The fragment's own head (<title>, description, canonical) ends at this mark; the main part follows.
const HEAD_END = "<!--/head-->";

export function join(shell, fragment) {
	// Every fragment has the mark: a deploy replaces the whole site, so none from before it is left.
	const mark = fragment.indexOf(HEAD_END);
	const head = fragment.slice(fragment.indexOf("<title>"), mark);
	const main = fragment.slice(mark + HEAD_END.length, fragment.lastIndexOf("</html>"));
	// The side panel's link this page is under (build.py write): its first <a href> in the shell.
	const snav = head.match(/<meta name="snav" content="([^"]+)">/);
	if (snav) shell = shell.replace(`<a href="${snav[1]}"`, (a) => `${a} aria-current="page"`);
	// Function replacements: a "$&" in a post must stay as it is.
	return shell.replace("<title></title>", () => head).replace("<!--main-->", () => main);
}

// Web push: a browser's subscription with its followed subjects (site.js), in KV (binding PUSH): the key is the
// push service's endpoint, the value {k, a, s, t} its keys, the subjects' hrefs and (optional) the picked teachers. ci/push.py reads them all with the
// secret PUSH_KEY and sends; an endpoint the service no longer knows it drops with s = [] as a browser does.
// Only the browsers' push services: ci/push.py posts to these URLs.
const PUSH_HOST = /^https:\/\/([a-z0-9-]+\.)*(fcm\.googleapis\.com|push\.services\.mozilla\.com|push\.apple\.com|notify\.windows\.com)\//;
const SUBJECT = /^\/predmet\/[a-z0-9-]+\/[a-z0-9-]+\/$/;
const B64URL = /^[A-Za-z0-9_-]{1,200}$/;
// A teacher page's slug (build.py set_hrefs): URL-safe characters.
const TEACHER = /^[A-Za-z0-9._~-]{1,80}$/;

// The count of browsers with notifications on (/statistika/): one row per subscription in D1's push_subs. Only a
// count: a failure here (no DB, no table yet) never stops a subscription or a send.
const counted = (env, statements) => env.DB ? env.DB.batch(statements(env.DB)).catch(() => {}) : null;

async function push(request, env, url) {
	const status = (code) => new Response(null, { status: code });
	if (!env.PUSH) return status(503);
	if (url.pathname === "/push/subs") {
		if (!env.PUSH_KEY || request.headers.get("Authorization") !== `Bearer ${env.PUSH_KEY}`) return status(403);
		// 500 a call (a KV read each, under the 1000 a Worker call may make); ci/push.py asks again with the cursor.
		const page = await env.PUSH.list({ limit: 500, cursor: url.searchParams.get("cursor") || undefined });
		const subs = await Promise.all(page.keys.map(async (k) => ({ endpoint: k.name, ...(await env.PUSH.get(k.name, "json")) })));
		// The count's list (push_subs) gets every subscription listed: the ones from before it, and any it missed.
		if (subs.length) await counted(env, (db) => subs.map((x) => db.prepare("INSERT OR IGNORE INTO push_subs (endpoint) VALUES (?)").bind(x.endpoint)));
		return Response.json({ subs, cursor: page.list_complete ? null : page.cursor });
	}
	if (request.method !== "POST") return status(405);
	let body;
	try {
		body = await request.json();
	} catch (e) {
		return status(400);
	}
	const { endpoint, keys, s, t } = body || {};
	if (typeof endpoint !== "string" || endpoint.length > 500 || !PUSH_HOST.test(endpoint) || !Array.isArray(s)) return status(400);
	if (!s.length) {
		await env.PUSH.delete(endpoint);
		await counted(env, (db) => [db.prepare("DELETE FROM push_subs WHERE endpoint = ?").bind(endpoint)]);
		return status(204);
	}
	if (!B64URL.test(keys?.p256dh) || !B64URL.test(keys?.auth) || s.length > 300 || !s.every((h) => SUBJECT.test(h))) return status(400);
	// t (optional): per followed subject, the teachers (their pages' slugs) whose posts alone notify.
	const picked = t === undefined || (t && typeof t === "object" && !Array.isArray(t) && Object.entries(t).every(([h, ts]) =>
		s.includes(h) && Array.isArray(ts) && ts.length && ts.length <= 50 && ts.every((x) => typeof x === "string" && TEACHER.test(x))));
	if (!picked) return status(400);
	await env.PUSH.put(endpoint, JSON.stringify(t ? { k: keys.p256dh, a: keys.auth, s, t } : { k: keys.p256dh, a: keys.auth, s }));
	await counted(env, (db) => [db.prepare("INSERT OR IGNORE INTO push_subs (endpoint) VALUES (?)").bind(endpoint)]);
	return status(204);
}

// Visitor counter, as on valjdakosta.com: each IP counts once per three-day period (D1 binding DB, schema.sql). The
// IPs older than that are deleted, so the total is kept on its own. site.js posts from every page; /statistika/ shows n,
// and asks (?push) for push too: the browsers with notifications on (push_subs).
async function visit(request, env, url) {
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
	if (!url.searchParams.has("push")) return Response.json({ n });
	const row = await env.DB.prepare("SELECT count(*) AS push FROM push_subs").first().catch(() => null);
	return Response.json(row ? { n, push: row.push } : { n });
}

// The automatic update (wrangler.toml crons): GitHub's own schedule started runs 5–8 hours late, a dispatch starts at
// once. The UTC hour -> the run's slot (ci/plan.py). GH_TOKEN: a fine-grained token, this repo, Actions read and write.
export const SLOTS = { 6: "morning", 10: "noon", 14: "afternoon", 18: "evening", 21: "late" };

export async function dispatch(env, time) {
	const slot = SLOTS[new Date(time).getUTCHours()];
	if (!slot) throw new Error(`no slot at ${new Date(time).toISOString()}`);
	const r = await fetch("https://api.github.com/repos/KostaJovanovic/nastava/actions/workflows/sync.yml/dispatches", {
		method: "POST",
		headers: { Authorization: `Bearer ${env.GH_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "nastava-worker" },
		body: JSON.stringify({ ref: "main", inputs: { what: `auto ${slot}` } }),
	});
	// Thrown: the Worker's log shows the failed trigger.
	if (!r.ok) throw new Error(`dispatch ${slot}: ${r.status} ${await r.text()}`);
}

export default {
	async scheduled(controller, env) {
		await dispatch(env, controller.scheduledTime);
	},
	async fetch(request, env, ctx) {
		const url = new URL(request.url);
		// Before the cache: these are not pages.
		if (url.pathname === "/push" || url.pathname === "/push/subs") return push(request, env, url);
		if (url.pathname === "/visit") return visit(request, env, url);
		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
		}
		// One domain for search engines and links: the old ones move there, path and all (/push and /visit stay
		// above: the subscriptions made on the old domains).
		if (url.hostname === "nastava.masinci.org" || url.hostname === "nastava.valjdakosta.com") {
			url.hostname = "masinci.org";
			return Response.redirect(url.toString(), 301);
		}
		const key = new Request(url.toString());
		const cached = await caches.default.match(key);
		if (cached) {
			// The zone's Browser Cache TTL replaces Cache-Control on a cached response, so set it again.
			const response = new Response(cached.body, cached);
			response.headers.set("Cache-Control", cacheControl(url));
			return response;
		}
		const origin = url.pathname.startsWith("/files/") ? await releaseFile(url.pathname) : await page(url, ctx);
		if (!origin) return new Response("Not found", { status: 404 });
		// Cache only a 200: a 404 for a new Pagefind file must not stay in the cache.
		if (origin.status !== 200) return origin;
		const response = new Response(origin.body, origin);
		response.headers.delete("Expires");
		response.headers.set("Cache-Control", cacheControl(url));
		ctx.waitUntil(caches.default.put(key, response.clone()));
		return response;
	},
};
