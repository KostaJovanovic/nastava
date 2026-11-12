// The Worker (pages/src/index.js): the page join every page goes through, the web push subscriptions it keeps, and
// the /files/ path check. No network: KV and the cache are stand-ins. Run: node --test test/worker_test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import worker, { join } from "../pages/src/index.js";

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

const call = (env, path, init) => worker.fetch(new Request(`https://nastava.masinci.org${path}`, init), env, { waitUntil() {} });
const post = (env, body) => call(env, "/push", { method: "POST", body: JSON.stringify(body) });
const EP = "https://fcm.googleapis.com/fcm/send/abc";
const keys = { p256dh: "BPumbb_-1", auth: "x-Y_z" };
const S = "/predmet/oas-mi/matematika-1/";

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

test("a /files/ path without its three parts is a 404, with no request to GitHub", async () => {
	for (const path of ["/files/mail/a.pdf", "/files/mail/a.pdf/b.pdf/c"]) assert.equal((await call({}, path)).status, 404);
});
