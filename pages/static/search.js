// Client search over the Pagefind index. The site has no server: all search state is in the URL.
// Without a query or a filter in the URL, the page keeps the newest items from the build.
const PAGE = 20;
const form = document.getElementById("sf");
const res = document.getElementById("res");
const heading = document.querySelector(".mh");
const status = document.querySelector("nav.status");
const rowTpl = document.getElementById("row-tpl");
const years = JSON.parse(document.querySelector("script[data-years]").dataset.years);
const pagefind = await import("/pagefind/pagefind.js");
await pagefind.options({ excerptLength: 30 });
// A search returns counts only for the filter groups that are loaded, so load all of them first.
// These are also the counts of the whole archive: a search that would match every item takes about a second.
const TOTALS = await pagefind.filters();
// The newest items from the build, shown again when the search and the filters are cleared.
const home = { heading: heading.innerHTML, res: res.innerHTML };

// The index holds a folded copy of each text (build.py fold): Cyrillic to Latin, no diacritics.
// Folding the query the same way finds "распоред", "raspored" and "rasporedjen" alike.
const CYR = Object.fromEntries([..."абвгдђежзијклљмнњопрстћуфхцчџш"].map((c, i) =>
	[c, "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split(" ")[i]]));
function fold(s) {
	const latin = [...s.toLowerCase()].map((c) => CYR[c] ?? c).join("").replaceAll("đ", "dj");
	return latin.normalize("NFD").replace(/\p{M}/gu, "");
}

function build(tag, props, children) {
	const node = Object.assign(document.createElement(tag), props);
	node.append(...children);
	return node;
}

function readState() {
	const f = new FormData(form);
	return {
		q: String(f.get("q") ?? "").trim(),
		kind: String(f.get("kind") ?? ""),
		smer: String(f.get("smer") ?? ""),
		subjects: f.getAll("subject").map(String),
		from: String(f.get("from") ?? ""),
		to: String(f.get("to") ?? ""),
	};
}

function writeUrl(s, page) {
	const p = new URLSearchParams();
	if (s.q) p.set("q", s.q);
	if (s.kind) p.set("kind", s.kind);
	if (s.smer) p.set("smer", s.smer);
	for (const x of s.subjects) p.append("subject", x);
	if (s.from) p.set("from", s.from);
	if (s.to) p.set("to", s.to);
	if (page > 1) p.set("page", page);
	history.replaceState(null, "", p.size ? `?${p}` : location.pathname);
}

function filtersOf(s) {
	// Pagefind needs a filter for a search without a query, so "vrsta" is always set.
	const filters = { vrsta: { any: s.kind ? [s.kind] : ["obavestenje", "dokument"] } };
	if (s.smer) filters.smer = { any: [s.smer] };
	if (s.subjects.length) filters.predmet = { any: s.subjects };
	const from = Number(s.from) || -Infinity;
	const to = Number(s.to) || Infinity;
	if (s.from || s.to) filters.godina = { any: years.filter((y) => y >= from && y <= to).map(String) };
	return filters;
}

function excerptNodes(html) {
	// Keep only text and <mark> from the Pagefind excerpt; drop all other markup.
	const doc = new DOMParser().parseFromString(html, "text/html");
	return [...doc.body.childNodes].map((n) =>
		n.nodeName === "MARK" ? build("mark", { textContent: n.textContent }, []) : document.createTextNode(n.textContent),
	);
}

function renderRow(data) {
	const li = rowTpl.content.firstElementChild.cloneNode(true);
	const isDoc = data.meta.vrsta === "dokument";
	const k = li.querySelector(".k");
	k.classList.add(isDoc ? "k--doc" : "k--post");
	k.title = isDoc ? "Dokument" : "Obaveštenje";
	k.querySelector("use").setAttribute("href", isDoc ? "#i-file" : "#i-megaphone");
	k.lastElementChild.textContent = k.title;
	const d = li.querySelector(".d");
	d.textContent = d.dateTime = data.meta.datum ?? "";
	li.querySelector(".s").textContent = data.meta.predmet ?? "";
	const a = li.querySelector(".t a");
	a.href = data.url;
	a.textContent = data.meta.title;
	li.querySelector(".x").append(...excerptNodes(data.excerpt));
	return li;
}

function renderHeading(s, total) {
	const h1 = build("h1", { id: "res-h", role: "status" }, [build("b", { textContent: String(total) }, []), " rezultata"]);
	if (s.q) h1.append(" za ", build("span", { className: "q", textContent: `„${s.q}“` }, []));
	heading.replaceChildren(h1);
}

function renderEmpty(s) {
	const box = build("div", { className: "empty" }, [build("h2", { textContent: `0 rezultata${s.q ? ` za „${s.q}“` : ""}` }, [])]);
	box.append(build("ul", {}, [
		build("li", { textContent: "proverite pravopis ili upišite kraći pojam" }, []),
		build("li", { textContent: "uklonite filtere i tražite u celoj arhivi" }, []),
	]));
	res.replaceChildren(box);
}

function renderPager(page, pages, go) {
	status.querySelector(".pg")?.remove();
	if (pages < 2) return;
	const btn = (parts, target, rel) => {
		const b = build("button", { type: "button", className: "btn" }, parts);
		if (target < 1 || target > pages) b.setAttribute("aria-disabled", "true");
		else b.addEventListener("click", () => go(target));
		b.rel = rel;
		return b;
	};
	const info = build("span", {}, ["stranica ", build("b", { textContent: String(page) }, []), ` od ${pages}`]);
	const prev = btn([icon("arrow-left"), "nazad"], page - 1, "prev");
	const next = btn(["dalje", icon("arrow-right")], page + 1, "next");
	status.append(build("span", { className: "pg" }, [prev, info, next]));
}

function icon(name) {
	// Uses the sprite in base.html; the icon is decorative, the button text names the action.
	const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	svg.setAttribute("class", "i");
	svg.setAttribute("aria-hidden", "true");
	const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
	use.setAttribute("href", `#i-${name}`);
	svg.append(use);
	return svg;
}

const GROUP = { kind: "vrsta", smer: "smer", subject: "predmet" };

async function groupCounts(s, query, search) {
	// Each group counts without its own filter, so picking one value does not drop the others to 0.
	const counts = {};
	for (const [field, group] of Object.entries(GROUP)) {
		const active = field === "subject" ? s.subjects.length : s[field];
		if (!active) {
			counts[group] = search.filters[group] ?? {};
			continue;
		}
		const filters = filtersOf(s);
		if (group === "vrsta") filters.vrsta = { any: ["obavestenje", "dokument"] }; // a search needs one filter
		else delete filters[group];
		// No query and no other filter: the counts are the archive totals.
		const everything = !query && Object.keys(filters).length === 1 && (group === "vrsta" || !s.kind);
		counts[group] = everything ? TOTALS[group] ?? {} : (await pagefind.search(query, { filters })).filters[group] ?? {};
	}
	return counts;
}

function updateCounts(counts) {
	const sum = (o) => Object.values(o).reduce((a, b) => a + b, 0);
	for (const input of document.querySelectorAll('.filters input[name="subject"], .filters input[name="kind"], .filters input[name="smer"]')) {
		const n = input.closest("label").querySelector(".n");
		if (!n) continue;
		const group = counts[GROUP[input.name]];
		n.textContent = input.value ? (group[input.value] ?? 0) : sum(group);
		// A subject with nothing for this search is hidden, unless it is checked (so it can be unchecked).
		if (input.name === "subject") input.closest("label").classList.toggle("is-empty", !group[input.value] && !input.checked);
	}
}

let results = [];
let state = null;

async function showPage(page) {
	const pages = Math.max(1, Math.ceil(results.length / PAGE));
	page = Math.min(Math.max(1, page), pages);
	writeUrl(state, page);
	if (!results.length) {
		renderEmpty(state);
	} else {
		const batch = await Promise.all(results.slice((page - 1) * PAGE, page * PAGE).map((r) => r.data()));
		const th = build("div", { className: "th", ariaHidden: "true" }, []);
		th.innerHTML = "<span></span><span>Datum</span><span>Predmet</span><span>Naslov</span>";
		res.replaceChildren(th, build("ol", { className: "rows" }, batch.map(renderRow)));
	}
	renderPager(page, pages, (n) => {
		showPage(n);
		heading.scrollIntoView({ block: "start" });
	});
}

function showHome() {
	writeUrl(readState(), 1);
	heading.innerHTML = home.heading;
	res.innerHTML = home.res;
	status.querySelector(".pg")?.remove();
	updateCounts({ vrsta: TOTALS.vrsta ?? {}, smer: TOTALS.smer ?? {}, predmet: TOTALS.predmet ?? {} });
}

// wait: the debounce in ms. Only typing needs one; a click searches at once.
let runs = 0;

async function run(page = 1, wait = 0) {
	// A slow search that ends after a newer run must not draw over it.
	const id = ++runs;
	const s = readState();
	for (const input of document.querySelectorAll('.filters input[name="kind"], .filters input[name="smer"]')) {
		input.closest("label").classList.toggle("is-on", input.checked);
	}
	if (!s.q && !s.kind && !s.smer && !s.subjects.length && !s.from && !s.to) return showHome();
	const query = s.q ? fold(s.q) : null;
	const search = await pagefind.debouncedSearch(query, { filters: filtersOf(s), sort: s.q ? undefined : { datum: "desc" } }, wait);
	if (search === null || id !== runs) return;
	const counts = await groupCounts(s, query, search);
	if (id !== runs) return;
	state = s;
	results = search.results;
	renderHeading(s, results.length);
	updateCounts(counts);
	await showPage(page);
}

function restoreFromUrl() {
	const p = new URLSearchParams(location.search);
	form.elements.q.value = p.get("q") ?? "";
	const subjects = new Set(p.getAll("subject"));
	for (const input of document.querySelectorAll('input[form="sf"]')) {
		if (input.name === "kind" || input.name === "smer") input.checked = input.value === (p.get(input.name) ?? "");
		else if (input.name === "subject") input.checked = subjects.has(input.value);
		else if (input.name === "from" || input.name === "to") input.value = p.get(input.name) ?? "";
	}
	// Checked subjects first, as in the server version of the page.
	const list = document.querySelector("[data-subject-list]");
	list.prepend(...[...list.querySelectorAll("label")].filter((l) => l.querySelector("input").checked));
	if (subjects.size || p.get("kind") || p.get("smer") || p.get("from") || p.get("to")) document.querySelector("details.filters").dataset.active = "1";
	return p.size > 0;
}

form.addEventListener("submit", (e) => {
	e.preventDefault();
	run();
});
form.elements.q.addEventListener("input", () => run(1, 200));
for (const input of document.querySelectorAll('input[form="sf"][type="number"]')) {
	input.addEventListener("change", () => run());
}
if (restoreFromUrl()) run(Number(new URLSearchParams(location.search).get("page")) || 1);
