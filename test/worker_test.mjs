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
		for (const h of [1, 5, 9, 13, 17, 21]) await dispatch({ GH_TOKEN: "t" }, Date.UTC(2026, 10, 12, h, 0, 3));
		assert.deepEqual(sent.map(([, i]) => JSON.parse(i.body).inputs.what),
			["auto night", "auto morning", "auto noon", "auto afternoon", "auto evening", "auto late"]);
		assert.match(sent[0][0], /\/actions\/workflows\/sync\.yml\/dispatches$/);
		assert.equal(sent[0][1].headers.Authorization, "Bearer t");
		await assert.rejects(dispatch({ GH_TOKEN: "t" }, Date.UTC(2026, 10, 12, 5)), /401/);
		await assert.rejects(dispatch({ GH_TOKEN: "t" }, Date.UTC(2026, 10, 12, 3)), /no slot/);
	} finally {
		globalThis.fetch = real;
	}
});

test("a /files/ path without its three parts is a 404, with no request to GitHub", async () => {
	for (const path of ["/files/mail/a.pdf", "/files/mail/a.pdf/b.pdf/c"]) assert.equal((await call({}, path)).status, 404);
});
