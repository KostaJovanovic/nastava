// The Worker (pages/src/index.js): the page join every page goes through, the web push subscriptions it keeps, and
// the /files/ path check. No network: KV and the cache are stand-ins. Run: node --test test/worker_test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import worker, { dispatch, join } from "../pages/src/index.js";

globalThis.caches = { default: { match: async () => undefined, put: async () => {} } };

function kv() {
	const m = new Map();
	return {
		m,
		get: async (k, type) => (m.has(k) ? (type === "json" ? JSON.parse(m.get(k)) : m.get(k)) : null),
		put: async (k, v) => void m.set(k, v),
		delete: async (k) => void m.delete(k),
		list: async () => ({ keys: [...m.keys()].map((name) => ({ name })), list_complete: true }),
	};
}

const call = (env, path, init, host = "masinci.org") => worker.fetch(new Request(`https://${host}${path}`, init), env, { waitUntil() {} });
const post = (env, body) => call(env, "/push", { method: "POST", body: JSON.stringify(body) });
const EP = "https://fcm.googleapis.com/fcm/send/abc";
const keys = { p256dh: "BPumbb_-1", auth: "x-Y_z" };
const S = "/predmet/oas-mi/matematika-1/";

test("the old domains redirect to masinci.org with the path; /push stays", async () => {
	for (const host of ["nastava.masinci.org", "nastava.valjdakosta.com"]) {
		const r = await call({}, "/tema/3/?x=1", undefined, host);
		assert.equal(r.status, 301);
		assert.equal(r.headers.get("Location"), "https://masinci.org/tema/3/?x=1");
	}
	const r = await call({ PUSH: kv() }, "/push", { method: "POST", body: "{}" }, "nastava.masinci.org");
	assert.notEqual(r.status, 301);
});

test("join puts the fragment's head and main into the shell, a $& in a post as it is", () => {
	const shell = "<html><title></title><body><main><!--main--></main></body></html>";
	const page = '<html lang="sr"><title>T</title><meta name="d"><!--/head--><p>$& a</p></html>';
	assert.equal(join(shell, page), '<html><title>T</title><meta name="d"><body><main><p>$& a</p></main></body></html>');
});

test("shell.html is fetched once per deploy; a shell from another deploy is used, not kept", async () => {
	const real = { fetch: globalThis.fetch, caches: globalThis.caches };
	const store = new Map(), got = [];
	globalThis.caches = { default: { match: async (r) => store.get(r.url)?.clone(), put: async (r, res) => void store.set(r.url, res) } };
	let deploy = "D1", shellDeploy = "D1";
	globalThis.fetch = async (u) => {
		got.push(u.slice(u.lastIndexOf("/")));
		const shell = u.endsWith("/shell.html");
		const body = shell ? `<html><title></title><!--main-->${shellDeploy}</html>` : '<html lang="sr"><title>T</title><!--/head-->p</html>';
		return new Response(body, { headers: { "Content-Type": "text/html", "Last-Modified": shell ? shellDeploy : deploy } });
	};
	const ctx = { waitUntil: (p) => p };
	const get = async (path) => (await worker.fetch(new Request(`https://masinci.org${path}`), {}, ctx)).text();
	try {
		assert.equal(await get("/a"), "<html><title>T</title>pD1</html>");
		await get("/b");
		assert.deepEqual(got.splice(0), ["/a", "/shell.html", "/b"]);
		deploy = "D2"; // the pages are out, shell.html not yet: used each time, never kept
		assert.equal(await get("/c"), "<html><title>T</title>pD1</html>");
		await get("/d");
		assert.deepEqual(got.splice(0), ["/c", "/shell.html", "/d", "/shell.html"]);
		shellDeploy = "D2";
		assert.equal(await get("/e"), "<html><title>T</title>pD2</html>");
		await get("/f");
		assert.deepEqual(got.splice(0), ["/e", "/shell.html", "/f"]);
	} finally {
		Object.assign(globalThis, real);
	}
});

test("a subscription is kept, read back with the key, and dropped with no subjects", async () => {
	const env = { PUSH: kv(), PUSH_KEY: "k" };
	assert.equal((await post(env, { endpoint: EP, keys, s: [S], t: { [S]: ["pera.peric"] } })).status, 204);
	assert.deepEqual(JSON.parse(env.PUSH.m.get(EP)), { k: keys.p256dh, a: keys.auth, s: [S], t: { [S]: ["pera.peric"] } });
	assert.equal((await call(env, "/push/subs")).status, 403);
	const subs = await (await call(env, "/push/subs", { headers: { Authorization: "Bearer k" } })).json();
	assert.equal(subs.subs[0].endpoint, EP);
	assert.equal((await post(env, { endpoint: EP, s: [] })).status, 204);
	assert.equal(env.PUSH.m.size, 0);
});

// D1 as far as the count needs it: push_subs as a set, visit_total as n; no table (made = false) throws, as D1 would.
function d1(made = true) {
	const subs = new Set();
	const stmt = (sql, args = []) => ({
		bind: (...a) => stmt(sql, a),
		run: async () => {
			if (!made && /push_subs/.test(sql)) throw new Error("no such table: push_subs");
			if (/^INSERT OR IGNORE INTO push_subs/.test(sql)) subs.add(args[0]);
			else if (/^DELETE FROM push_subs/.test(sql)) subs.delete(args[0]);
			return { meta: { changes: 0 } };
		},
		first: async () => {
			if (!made && /push_subs/.test(sql)) throw new Error("no such table: push_subs");
			return /push_subs/.test(sql) ? { push: subs.size } : { n: 7 };
		},
	});
	return { subs, prepare: (sql) => stmt(sql), batch: async (list) => { for (const s of list) await s.run(); } };
}

test("the count of browsers with notifications: on subscribe, off, the listing; only /visit?push gives it", async () => {
	const env = { PUSH: kv(), PUSH_KEY: "k", DB: d1() };
	const visit = async (q = "?push") => (await call(env, `/visit${q}`, { method: "POST" })).json();
	await post(env, { endpoint: EP, keys, s: [S] });
	await post(env, { endpoint: EP, keys, s: [S, "/predmet/oas-mi/fizika/"] }); // a change of subjects: still one
	assert.deepEqual(await visit(), { n: 7, push: 1 });
	assert.deepEqual(await visit(""), { n: 7 });
	await post(env, { endpoint: EP, s: [] });
	assert.deepEqual(await visit(), { n: 7, push: 0 });
	// One made before the count: the listing (ci/push.py, every run) adds it.
	env.PUSH.m.set(EP, JSON.stringify({ k: keys.p256dh, a: keys.auth, s: [S] }));
	await call(env, "/push/subs", { headers: { Authorization: "Bearer k" } });
	assert.deepEqual(await visit(), { n: 7, push: 1 });
});

test("no push_subs table yet: subscriptions and the listing still work, /visit has no count", async () => {
	const env = { PUSH: kv(), PUSH_KEY: "k", DB: d1(false) };
	assert.equal((await post(env, { endpoint: EP, keys, s: [S] })).status, 204);
	const r = await call(env, "/push/subs", { headers: { Authorization: "Bearer k" } });
	assert.equal((await r.json()).subs.length, 1);
	assert.deepEqual(await (await call(env, "/visit?push", { method: "POST" })).json(), { n: 7 });
	assert.equal((await post(env, { endpoint: EP, s: [] })).status, 204);
});

test("a subscription the Worker must refuse", async () => {
	const env = { PUSH: kv(), PUSH_KEY: "k" };
	for (const body of [
		{ endpoint: "https://evil.example/fcm.googleapis.com/x", keys, s: [S] }, // not a push service
		{ endpoint: EP, keys, s: ["/item/p1/"] }, // not a subject page
		{ endpoint: EP, keys: { p256dh: "a b", auth: "x" }, s: [S] }, // a key that is not base64url
		{ endpoint: EP, keys, s: [S], t: { "/predmet/a/b/": ["x"] } }, // teachers of a subject not followed
		{ endpoint: EP, keys, s: [S], t: { [S]: ["<script>"] } }, // not a page's slug
	]) assert.equal((await post(env, body)).status, 400, JSON.stringify(body));
	assert.equal(env.PUSH.m.size, 0);
});

test("each cron hour starts sync.yml as its slot; a failed dispatch throws", async () => {
	const sent = [], real = globalThis.fetch;
	globalThis.fetch = async (url, init) => (sent.push([url, init]), new Response(null, { status: sent.length > 6 ? 401 : 204 }));
	try {
		for (const h of [6, 10, 14, 18, 21, 21]) await dispatch({ GH_TOKEN: "t" }, Date.UTC(2026, 10, 12, h, 17, 3));
		assert.deepEqual(sent.map(([, i]) => JSON.parse(i.body).inputs.what),
			["auto morning", "auto noon", "auto afternoon", "auto evening", "auto late", "auto late"]);
		assert.match(sent[0][0], /\/actions\/workflows\/sync\.yml\/dispatches$/);
		assert.equal(sent[0][1].headers.Authorization, "Bearer t");
		await assert.rejects(dispatch({ GH_TOKEN: "t" }, Date.UTC(2026, 10, 12, 6, 17)), /401/);
		await assert.rejects(dispatch({ GH_TOKEN: "t" }, Date.UTC(2026, 10, 12, 3)), /no slot/);
	} finally {
		globalThis.fetch = real;
	}
});

test("a /files/ path without its three parts is a 404, with no request to GitHub", async () => {
	for (const path of ["/files/mail/a.pdf", "/files/mail/a.pdf/b.pdf/c"]) assert.equal((await call({}, path)).status, 404);
});
