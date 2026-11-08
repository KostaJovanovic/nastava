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
	// An item rarely changes, but its side panel (counts, links) and an edited post do: a day, at the edge too.
	if (path.startsWith("/item/")) return "public, max-age=86400";
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

export function join(shell, fragment) {
	const start = fragment.indexOf("<title>");
	const end = fragment.indexOf("</title>") + "</title>".length;
	const title = fragment.slice(start, end);
	const main = fragment.slice(end, fragment.lastIndexOf("</html>"));
	// Function replacements: a "$&" in a post must stay as it is.
	return shell.replace("<title></title>", () => title).replace("<!--main-->", () => main);
}

export default {
	async fetch(request, env, ctx) {
		if (request.method !== "GET" && request.method !== "HEAD") {
			return new Response("Method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
		}
		const url = new URL(request.url);
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
