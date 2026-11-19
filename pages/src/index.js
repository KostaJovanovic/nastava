// Serve the site from GitHub Pages through the edge cache. Every file links to where it was published (the board,
// the faculty's sites, the Wayback Machine): no files here (docs/PLAN-pravno.md 1). The site is public: no auth, but the contact form's inbox
// (/kontakt/poruke/).
const PAGES = "https://kostajovanovic.github.io/nastava";
// Most pages are stored as a fragment, <html lang="sr"> with their <title> and main part; join() puts it into
// shell.html (build.py split_page). A whole page starts with <!doctype html>. pages/serve.py joins the same way.
const FRAGMENT = '<html lang="sr"><title>';
// Pagefind file names have a content hash, except these entry files.
const ENTRY = /^\/pagefind\/pagefind[^/]*\.(js|json|css)$/;
const YEAR = 31536000;
// The hosts that redirect to masinci.org (wrangler.toml routes).
const OLD_HOSTS = ["nastava.masinci.org", "nastava.valjdakosta.com", "www.masinci.org"];

function cacheControl(url) {
	const path = url.pathname;
	if (path.startsWith("/pagefind/") && !ENTRY.test(path)) return `public, max-age=${YEAR}, immutable`;
	// An item or a news post rarely changes, but its side panel (counts, links) and an edited post do: a day, at the
	// edge too.
	if (path.startsWith("/item/") || path.startsWith("/vest/")) return "public, max-age=86400";
	// A file linked with ?v=<its hash> (build.py VERSIONED, izbor.json, novo.json, rows-<year>.json): a changed file is a
	// new URL. Only once the body is checked against the hash (verified): before that, GitHub Pages may still serve the
	// old file under the new URL.
	if (HASHED.test(url.searchParams.get("v") || "")) return "public, max-age=300";
	// Teachers' photos, fonts and icons: named by their source (photo_path), not their bytes, so a changed one keeps its
	// name; they rarely change. A week saves a browser's recheck at every visit.
	if (WEEK.test(path)) return "public, max-age=604800";
	// The home page, /static/ and the Pagefind entry files change with each deploy.
	return "public, max-age=300";
}

// output.py v_of: the first 10 hex digits of the file's SHA-256.
const HASHED = /^[0-9a-f]{10}$/;
const WEEK = /^\/(foto\/|static\/fonts\/|static\/(favicon\.svg|apple-touch-icon\.png|manifest\.webmanifest|icon-\d+\.png|badge\.png)$)/;

// A body that is the file its ?v= names: kept a year (the browser and the edge never ask again).
async function verified(url, response) {
	const v = url.searchParams.get("v");
	if (!HASHED.test(v || "")) return null;
	const body = await response.arrayBuffer();
	const hex = [...new Uint8Array(await crypto.subtle.digest("SHA-256", body))].map((b) => b.toString(16).padStart(2, "0")).join("");
	return { body, ok: hex.startsWith(v) };
}

// shell.html once per deploy, not once per page. GitHub Pages stamps a deploy's files with Last-Modified seconds apart
// (19:09:18 to 19:09:20 on 2026-11-15), and two deploys are minutes apart: a shell stamped within SAME_DEPLOY of the
// fragment is its deploy's. One kept shell, at a path GitHub Pages 404s, so the page cache never stores one there.
// A shell from another deploy (one still going out) is used but not kept.
const SAME_DEPLOY = 120e3;
const near = (a, b) => Math.abs(a - b) < SAME_DEPLOY; // false for a missing date (NaN)

async function shellFor(url, fragment, ctx) {
	const deploy = Date.parse(fragment.headers.get("Last-Modified"));
	const key = new Request(`${url.origin}/__shell/`);
	const kept = await caches.default.match(key);
	if (kept && near(Date.parse(kept.headers.get("X-Deploy")), deploy)) return kept.text();
	const shell = await fetch(PAGES + "/shell.html");
	if (!shell.ok) return null;
	const stamped = shell.headers.get("Last-Modified");
	if (near(Date.parse(stamped), deploy)) {
		const headers = { "Content-Type": "text/html", "Cache-Control": "public, max-age=86400", "X-Deploy": stamped };
		ctx.waitUntil(caches.default.put(key, new Response(shell.clone().body, { headers })));
	}
	return shell.text();
}

// A post or a news page is kept a day (cacheControl), under its deploy: the kept shell's stamp is in its cache key, so
// once a deploy's shell is kept (the first fragment of that deploy fetched, minutes after it), the old copies are
// passed over and the new CSS and JS reach every post, not a day later. Only Cloudflare's copy: a browser's stays.
async function cacheKey(url) {
	if (!url.pathname.startsWith("/item/") && !url.pathname.startsWith("/vest/")) return new Request(url.toString());
	const kept = await caches.default.match(new Request(`${url.origin}/__shell/`));
	const key = new URL(url);
	key.searchParams.set("__deploy", kept?.headers.get("X-Deploy") ?? "");
	return new Request(key.toString());
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
// push service's endpoint, the value {k, a, s, t} its keys, the subjects' hrefs and (optional) the picked teachers; the
// Android app's is "fcm:<token>" with {s, t}. ci/push.py reads them all with the
// secret PUSH_KEY and sends; an endpoint the service no longer knows it drops with s = [] as a browser does.
// Only the browsers' push services: ci/push.py posts to these URLs.
const PUSH_HOST = /^https:\/\/([a-z0-9-]+\.)*(fcm\.googleapis\.com|push\.services\.mozilla\.com|push\.apple\.com|notify\.windows\.com)\//;
const SUBJECT = /^\/predmet\/[a-z0-9-]+\/[a-z0-9-]+\/$/;
const B64URL = /^[A-Za-z0-9_-]{1,200}$/;
// An FCM registration token (the app's): about 150-180 of these characters.
const FCM_TOKEN = /^[A-Za-z0-9_:-]{100,300}$/;
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
		// The count's list (push_subs) gets every subscription listed: the ones from before it, and any it missed. All of
		// them in one page: the list is set to exactly them, so a row whose delete failed goes too.
		// shortcut: only while every subscription fits one page (500); past that, rows are only added.
		const whole = !url.searchParams.get("cursor") && page.list_complete;
		const add = (db) => subs.map((x) => db.prepare("INSERT OR IGNORE INTO push_subs (endpoint) VALUES (?)").bind(x.endpoint));
		await counted(env, (db) => (whole ? [db.prepare("DELETE FROM push_subs"), ...add(db)] : add(db)));
		return Response.json({ subs, cursor: page.list_complete ? null : page.cursor });
	}
	if (request.method !== "POST") return status(405);
	let body;
	try {
		body = await request.json();
	} catch (e) {
		return status(400);
	}
	const { fcm, keys, s, t } = body || {};
	// The Android app (app/) has no web push: its FCM token instead, kept as "fcm:<token>" (ci/push.py sends to it
	// through FCM) with no keys.
	const app = fcm !== undefined;
	const endpoint = app ? `fcm:${fcm}` : body?.endpoint;
	const where = app ? typeof fcm === "string" && FCM_TOKEN.test(fcm) : typeof endpoint === "string" && endpoint.length <= 500 && PUSH_HOST.test(endpoint);
	if (!where || !Array.isArray(s)) return status(400);
	if (!s.length) {
		await env.PUSH.delete(endpoint);
		await counted(env, (db) => [db.prepare("DELETE FROM push_subs WHERE endpoint = ?").bind(endpoint)]);
		return status(204);
	}
	if ((!app && (!B64URL.test(keys?.p256dh) || !B64URL.test(keys?.auth))) || s.length > 300 || !s.every((h) => SUBJECT.test(h))) return status(400);
	// t (optional): per followed subject, the teachers (their pages' slugs) whose posts alone notify.
	const picked = t === undefined || (t && typeof t === "object" && !Array.isArray(t) && Object.entries(t).every(([h, ts]) =>
		s.includes(h) && Array.isArray(ts) && ts.length && ts.length <= 50 && ts.every((x) => typeof x === "string" && TEACHER.test(x))));
	if (!picked) return status(400);
	const value = app ? { s } : { k: keys.p256dh, a: keys.auth, s };
	await env.PUSH.put(endpoint, JSON.stringify(t ? { ...value, t } : value));
	await counted(env, (db) => [db.prepare("INSERT OR IGNORE INTO push_subs (endpoint) VALUES (?)").bind(endpoint)]);
	return status(204);
}

const sha256hex = async (s) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)))].map((b) => b.toString(16).padStart(2, "0")).join("");

// Visitor counter, as on valjdakosta.com: each IP counts once per three-day period (D1 binding DB, schema.sql). The
// IPs older than that are deleted, so the total is kept on its own. site.js posts from every page; /statistika/ shows n,
// and asks (?push) for push too: the browsers with notifications on (push_subs).
async function visit(request, env, url) {
	if (request.method !== "POST") return new Response(null, { status: 405 });
	if (!env.DB) return new Response(null, { status: 503 });
	// Not the IP: its SHA-256 with the period and the secret COUNTER_SALT (docs/PLAN-pravno.md 7.3), which tells one
	// visitor's visits of a period apart from another's and nothing more. The period as SQLite's
	// date(cast(julianday('now') / 3 as integer) * 3).
	const period = new Date((Math.floor((Date.now() / 864e5 + 2440587.5) / 3) * 3 - 2440587.5) * 864e5).toISOString().slice(0, 10);
	const ip = await sha256hex(`${request.headers.get("CF-Connecting-IP") || ""}|${period}|${env.COUNTER_SALT || ""}`);
	const { meta } = await env.DB.prepare("INSERT OR IGNORE INTO visits (ip, period) VALUES (?, ?)").bind(ip, period).run();
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

// The contact form (kontakt.html, docs/PLAN-pravno.md 5a): POST /kontakt checks Cloudflare Turnstile (TURNSTILE_SECRET)
// and the fields, keeps the message in D1 (messages, schema.sql) and sends the author a push with no payload
// (INBOX_PUSH: a browser subscription's endpoint; sw.js shows "Nova poruka na sajtu"). The inbox, /kontakt/poruke/, is
// the Worker's own page behind HTTP Basic auth (INBOX_PASSWORD), never cached. The cron deletes a message after
// RETAIN_DAYS. A form without JS gets a short page back; site.js asks for JSON (Accept: application/json).
export const TOPICS = { uklanjanje: "Uklanjanje", ispravka: "Ispravka", predlog: "Predlog", drugo: "Drugo" };
const EMAIL = /^[^\s@<>"]{1,64}@[^\s@<>"]{1,190}\.[^\s@<>".]{2,}$/;
const PATH = /^\/(?!\/)[^\s<>"]{0,300}$/;
export const RETAIN_DAYS = 90;
const INBOX = "/kontakt/poruke/";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

// The fields of a form post, checked: { email, topic, page, text } or { error } in Serbian (shown to the sender).
export function checkMessage(form, referer) {
	const email = String(form.get("email") || "").trim(), topic = String(form.get("tema") || ""), text = String(form.get("poruka") || "").trim();
	let page = String(form.get("str") || "");
	// Without JS the hidden field is empty: the page is the one the form was opened for (its ?str=).
	if (!page && referer) {
		try {
			page = new URL(referer).searchParams.get("str") || "";
		} catch {}
	}
	if (!EMAIL.test(email) || email.length > 200) return { error: "Mejl adresa nije ispravna." };
	if (!TOPICS[topic]) return { error: "Izaberi temu." };
	if (!text || text.length > 5000) return { error: "Poruka mora imati tekst, do 5.000 znakova." };
	return { email, topic, page: PATH.test(page) ? page : null, text };
}

async function turnstile(env, token, ip) {
	if (!env.TURNSTILE_SECRET || !token) return false;
	const body = new FormData();
	body.append("secret", env.TURNSTILE_SECRET);
	body.append("response", token);
	if (ip) body.append("remoteip", ip);
	try {
		const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body });
		return (await r.json()).success === true;
	} catch {
		return false;
	}
}

// A short page of the site's look for a form sent without JS, or for the inbox.
function htmlPage(title, body, status = 200, headers = {}) {
	const page = `<!doctype html><html lang="sr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>${esc(title)} · masinci.org</title><link rel="stylesheet" href="/static/style.css"><body><main class="main" style="max-width:760px;margin:0 auto;padding:24px 16px">${body}</main></body></html>`;
	return new Response(page, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex", ...headers } });
}

async function kontakt(request, env, ctx) {
	const json = (request.headers.get("Accept") || "").includes("application/json");
	const answer = (ok, error, text) => json
		? Response.json(ok ? { ok } : { ok, error }, { status: ok ? 200 : 400 })
		: ok
			? htmlPage("Poslato", '<h1>Poslato, hvala!</h1><p>Odgovoriću na mejl koji si ostavio.</p><p><a href="/">Početna</a></p>')
			: htmlPage("Nije poslato", `<h1>Poruka nije poslata</h1><p>${esc(error)}</p>${text ? `<p>Tvoja poruka, da je ne izgubiš:</p><textarea class="field" rows="8" style="height:auto;width:100%" readonly>${esc(text)}</textarea>` : ""}<p><a href="/kontakt/">Nazad na formu</a></p>`, 400);
	if (request.method !== "POST") return new Response(null, { status: 405, headers: { Allow: "POST" } });
	let form;
	try {
		form = await request.formData();
	} catch {
		return answer(false, "Poruka nije stigla cela. Pokušaj ponovo.");
	}
	const m = checkMessage(form, request.headers.get("Referer"));
	if (m.error) return answer(false, m.error, String(form.get("poruka") || ""));
	if (!(await turnstile(env, form.get("cf-turnstile-response"), request.headers.get("CF-Connecting-IP")))) {
		return answer(false, "Provera da nisi bot nije prošla. Sačekaj da se provera završi, pa pošalji ponovo.", m.text);
	}
	try {
		await env.DB.prepare("INSERT INTO messages (email, topic, page, text) VALUES (?, ?, ?, ?)").bind(m.email, m.topic, m.page, m.text).run();
	} catch {
		return answer(false, "Poruka nije sačuvana, greška na sajtu. Pokušaj malo kasnije.", m.text);
	}
	if (env.INBOX_PUSH && env.VAPID_PRIVATE) ctx.waitUntil(notify(env.INBOX_PUSH, env.VAPID_PRIVATE).catch(() => {}));
	return answer(true);
}

// HTTP Basic auth against INBOX_PASSWORD (any user name), compared in constant time (by their SHA-256).
async function authorized(request, env) {
	const m = (request.headers.get("Authorization") || "").match(/^Basic ([A-Za-z0-9+/=]+)$/);
	if (!m || !env.INBOX_PASSWORD) return false;
	let given;
	try {
		given = new TextDecoder().decode(Uint8Array.from(atob(m[1]), (c) => c.charCodeAt(0)));
	} catch {
		return false;
	}
	const hash = async (s) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
	const [a, b] = await Promise.all([hash(given.slice(given.indexOf(":") + 1)), hash(env.INBOX_PASSWORD)]);
	return a.reduce((diff, x, i) => diff | (x ^ b[i]), 0) === 0;
}

async function inbox(request, env, url) {
	// The password only over https (the redirect below the routes comes too late for it).
	if (url.protocol !== "https:") return Response.redirect(`https://masinci.org${INBOX}`, 301);
	if (!(await authorized(request, env))) {
		return new Response("Lozinka", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="poruke", charset="UTF-8"', "Cache-Control": "no-store" } });
	}
	if (!env.DB) return new Response(null, { status: 503 });
	if (request.method === "POST") {
		const id = Number((await request.formData()).get("id"));
		if (Number.isInteger(id)) await env.DB.prepare("DELETE FROM messages WHERE id = ?").bind(id).run();
		return new Response(null, { status: 303, headers: { Location: INBOX } });
	}
	const { results } = await env.DB.prepare("SELECT id, time, email, topic, page, text FROM messages ORDER BY time DESC, id DESC").all();
	const rows = results.map((r) => {
		const subject = encodeURIComponent(`Re: masinci.org, ${TOPICS[r.topic] || r.topic}`);
		return `<article class="note" style="margin:12px 0"><p><b>${esc(TOPICS[r.topic] || r.topic)}</b> · ${esc(r.time)} UTC · ${esc(r.email)}${r.page ? ` · <a href="${esc(r.page)}">${esc(r.page)}</a>` : ""}</p><p style="white-space:pre-wrap">${esc(r.text)}</p><form method="post" style="display:flex;gap:8px"><a class="btn" href="mailto:${esc(r.email)}?subject=${subject}">Odgovori</a><input type="hidden" name="id" value="${r.id}"><button class="btn">Obriši</button></form></article>`;
	});
	// The bell's subscription in this browser, to put in INBOX_PUSH (wrangler secret put INBOX_PUSH).
	const sub = `<p style="font-size:.8rem">Obaveštenja: <code id="ep">uključi zvonce na sajtu u ovom browseru</code></p><script>navigator.serviceWorker&&navigator.serviceWorker.getRegistration("/").then(function(r){return r&&r.pushManager.getSubscription()}).then(function(s){if(s)document.getElementById("ep").textContent=s.endpoint})</script>`;
	return htmlPage("Poruke", `<h1>Poruke <small>${results.length}</small></h1>${rows.join("") || "<p>Nema poruka.</p>"}${sub}<p style="font-size:.8rem">Brišu se same posle ${RETAIN_DAYS} dana.</p>`);
}

// The site's VAPID public key (site.js PUSH_PUBLIC; ci/push.py keys), whose private half is VAPID_PRIVATE (32 bytes).
export const VAPID_PUBLIC = "BPumbbNmB0El3blUr_wKj4PWrpCq0b6pSakijI6H3gtrlgxAqz4abQ63IIwe9EEq50gJNhGDay-Mdb28hsUCSqE";
const b64url = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

// A VAPID JWT (RFC 8292) for a push service: ES256, signed with crypto.subtle (its signature is already r || s).
export async function vapidJwt(endpoint, privateKey, publicKey = VAPID_PUBLIC, now = Date.now()) {
	const pub = unb64url(publicKey);
	const key = await crypto.subtle.importKey(
		"jwk",
		{ kty: "EC", crv: "P-256", d: privateKey, x: b64url(pub.slice(1, 33)), y: b64url(pub.slice(33, 65)), ext: true },
		{ name: "ECDSA", namedCurve: "P-256" },
		false,
		["sign"],
	);
	const part = (o) => b64url(new TextEncoder().encode(JSON.stringify(o)));
	const unsigned = `${part({ typ: "JWT", alg: "ES256" })}.${part({ aud: new URL(endpoint).origin, exp: Math.floor(now / 1000) + 12 * 3600, sub: "https://masinci.org" })}`;
	const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, new TextEncoder().encode(unsigned));
	return `${unsigned}.${b64url(sig)}`;
}

// A push with no payload (no encryption needed): the service worker shows a fixed notification.
async function notify(endpoint, privateKey) {
	const jwt = await vapidJwt(endpoint, privateKey);
	await fetch(endpoint, { method: "POST", headers: { TTL: "86400", Urgency: "normal", Authorization: `vapid t=${jwt}, k=${VAPID_PUBLIC}` } });
}

// The cron's cleanup: the messages older than RETAIN_DAYS.
export async function retain(env) {
	if (env.DB) await env.DB.prepare(`DELETE FROM messages WHERE time < datetime('now', '-${RETAIN_DAYS} days')`).run();
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
		// The cleanup's failure must not stop the update.
		await retain(env).catch((e) => console.error("retain", e));
		await dispatch(env, controller.scheduledTime);
	},
	async fetch(request, env, ctx) {
		const url = new URL(request.url);
		// Before the cache: these are not pages.
		if (url.pathname === "/push" || url.pathname === "/push/subs") return push(request, env, url);
		if (url.pathname === "/visit") return visit(request, env, url);
		if ((url.pathname === "/kontakt" || url.pathname === "/kontakt/") && request.method === "POST") return kontakt(request, env, ctx);
		if (url.pathname === INBOX || url.pathname === INBOX.slice(0, -1)) return inbox(request, env, url);
		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
		}
		// One domain for search engines and links: the old ones move there, path and all (/push and /visit stay
		// above: the subscriptions made on the old domains).
		// www and plain http too (HSTS works only after an https visit).
			if (OLD_HOSTS.includes(url.hostname) || (url.hostname === "masinci.org" && url.protocol === "http:")) {
				url.protocol = "https:";
			url.hostname = "masinci.org";
			return Response.redirect(url.toString(), 301);
		}
		const key = await cacheKey(url);
		const cached = await caches.default.match(key);
		if (cached) {
			// The zone's Browser Cache TTL replaces Cache-Control on a cached response, so set it again (X-Cache-Control:
			// the one it was stored with, a verified file's year).
			const response = new Response(cached.body, cached);
			// None: kept before the check existed, when every /static/ ?v= file was kept a year as it is.
			const old = url.pathname.startsWith("/static/") && HASHED.test(url.searchParams.get("v") || "");
			response.headers.set("Cache-Control", cached.headers.get("X-Cache-Control") || (old ? `public, max-age=${YEAR}, immutable` : cacheControl(url)));
			response.headers.delete("X-Cache-Control");
			return response;
		}
		const origin = await page(url, ctx);
		// Cache only a 200: a 404 for a new Pagefind file must not stay in the cache.
		if (origin.status !== 200) return origin;
		const check = await verified(url, origin);
		const cc = check?.ok ? `public, max-age=${YEAR}, immutable` : cacheControl(url);
		const response = new Response(check ? check.body : origin.body, origin);
		response.headers.delete("Expires");
		response.headers.set("Cache-Control", cc);
		const kept = response.clone();
		kept.headers.set("X-Cache-Control", cc);
		ctx.waitUntil(caches.default.put(key, kept));
		return response;
	},
};
