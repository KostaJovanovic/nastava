// Client search over the Pagefind index. The site has no server: all search state is in the URL.
// Without a query or a filter in the URL, the page keeps the newest items from the build.
const PAGE = 20;
const form = document.getElementById("sf");
const res = document.getElementById("res");
const heading = document.querySelector(".mh");
const rowTpl = document.getElementById("row-tpl");
const resTpl = document.getElementById("res-tpl");
const years = JSON.parse(document.querySelector("script[data-years]").dataset.years);
// Pagefind loads at the first search (or the box's focus), not with the page: most home page views search nothing,
// and each of its files is a call to the Worker. No index (a build Pagefind did not run on, or no network): the board
// index shows, with a note, not "Tražim…".
let pagefindLoad = null;
function loadPagefind() {
	return (pagefindLoad ??= (async () => {
		let loadError;
		const pf = await import("/pagefind/pagefind.js").catch((e) => ((loadError = e), null));
		if (!pf) {
			document.documentElement.classList.remove("searching");
			// A failed import does not say why; asking for the file again does: no network, no index, the server, or the file.
			const r = await fetch("/pagefind/pagefind.js", { method: "HEAD", cache: "no-store" }).catch(() => null);
			const why = !r ? "nema mreže" : r.status === 404 ? "nema indeksa" : !r.ok ? `greška servera (${r.status})` : "indeks neispravan";
			heading.append(build("p", { className: "note", textContent: `Pretraga nije dostupna: ${why}.` }, []));
			throw loadError;
		}
		await pf.options({ excerptLength: 30 });
		return pf;
	})());
}
form.elements.q.addEventListener("focus", () => loadPagefind().catch(() => {}), { once: true });
// The newest items from the build, shown again when the search and the filters are cleared.
const home = { heading: heading.innerHTML, res: res.innerHTML };

// The index holds a folded copy of each text (build.py fold): Cyrillic to Latin, no diacritics.
// Folding the query the same way finds "распоред", "raspored" and "rasporedjen" alike. pismo.js, a classic script
// at the end of the body, has run before this module.
const fold = window.pismoFold;

function build(tag, props, children) {
	const node = Object.assign(document.createElement(tag), props);
	node.append(...children);
	return node;
}

// The order of a search with a query: by relevance, or newest first (?red=novije). Without a query: always newest.
let newest = false;
// A text's kind (?kind=, Pagefind's "vrsta") as its chip names it.
const KINDS = { vest: "Vesti", obavestenje: "Threadovi", dokument: "Dokumenti" };

// The subjects this browser follows (site.js, the side panel's picker and a subject's star): their URLs.
function followed() {
	try { return (JSON.parse(localStorage.getItem("moji")) || []).map((s) => s.href); } catch (e) { return []; }
}

// The side panel's switch "Samo moji predmeti" off (site.js): a choice of this browser, as the followed subjects are.
function everySubject() {
	try { return localStorage.getItem("sve") === "1"; } catch (e) { return false; }
}

function readState() {
	const f = new FormData(form);
	const s = {
		newest,
		// Words in quotes are an exact word or phrase (Pagefind's own): "ispit" not ispita. The quotes as typed („…“, a
		// phone's “…”) become the plain " Pagefind reads.
		q: String(f.get("q") ?? "").trim().replace(/[„“”«»]/g, '"'),
		kind: String(f.get("kind") ?? ""),
		smer: String(f.get("smer") ?? ""),
		subjects: f.getAll("subject").map(String),
		authors: f.getAll("autor").map(String),
		from: String(f.get("from") ?? ""),
		to: String(f.get("to") ?? ""),
		all: everySubject(),
	};
	// A search covers the followed subjects unless the side panel's switch is off, or a link names a smer, subject or
	// author.
	s.mine = s.all || s.smer || s.subjects.length || s.authors.length ? [] : followed();
	return s;
}

function writeUrl(s, pages) {
	const p = new URLSearchParams();
	// The query folded (Latin, no diacritics), so a URL never has Cyrillic; the search folds it anyway.
	if (s.q) p.set("q", fold(s.q));
	if (s.q && s.newest) p.set("red", "novije");
	if (s.kind) p.set("kind", s.kind);
	if (s.smer) p.set("smer", s.smer);
	for (const x of s.subjects) p.append("subject", x);
	for (const x of s.authors) p.append("autor", x);
	if (s.from) p.set("from", s.from);
	if (s.to) p.set("to", s.to);
	// Each list's page (showPages): the subjects' (or the one kind's) page=, the news' vpage=.
	if (pages.p > 1) p.set("page", pages.p);
	if (pages.v > 1) p.set("vpage", pages.v);
	// String(p), not p.size: Safari before 17 has no size.
	history.replaceState(history.state, "", String(p) ? `?${p}` : location.pathname);
}

function filtersOf(s) {
	// Pagefind needs a filter for a search without a query; run() only searches then when some filter is set.
	// "vrsta" only when picked: as a filter on every search it doubled the time of one with a query.
	const filters = s.kind ? { vrsta: { any: [s.kind] } } : {};
	if (s.smer) filters.smer = { any: [s.smer] };
	if (s.subjects.length) filters.predmet = { any: s.subjects };
	if (s.authors.length) filters.autor = { any: s.authors };
	// The news are no subject's: only the scope Vesti finds them while only the followed subjects show.
	if (s.mine.length && s.kind !== "vest") filters.pid = { any: s.mine };
	const from = Number(s.from) || -Infinity;
	const to = Number(s.to) || Infinity;
	if (s.from || s.to) filters.godina = { any: years.filter((y) => y >= from && y <= to).map(String) };
	return filters;
}

function excerptNodes(html, text) {
	// Keep only text and <mark> from the Pagefind excerpt; drop all other markup.
	const parts = [...new DOMParser().parseFromString(html, "text/html").body.childNodes];
	const plain = () => parts.map((n) =>
		n.nodeName === "MARK" ? build("mark", { textContent: n.textContent }, []) : document.createTextNode(n.textContent),
	);
	// The excerpt is a run of words of the folded copy, which has the words of the text as written in the same
	// order (build.py pagefind_tags "tekst"). Find the run and show those words as written.
	const words = [];
	let glued = false; // the next piece continues the last word (no space between)
	for (const n of parts) {
		const marked = n.nodeName === "MARK";
		n.textContent.split(/(\s+)/).forEach((w) => {
			if (!w) return;
			if (/^\s/.test(w)) { glued = false; return; }
			if (glued) { words.at(-1).w += w; words.at(-1).marked ||= marked; }
			else words.push({ w, marked });
			glued = true;
		});
	}
	const orig = (text ?? "").split(/\s+/).filter(Boolean);
	if (!words.length || !orig.length) return plain();
	const folded = orig.map(fold);
	// An excerpt that reaches the end of the text ends with a "." Pagefind adds.
	const at = folded.findIndex((_, i) => words.every((x, k) => folded[i + k] === x.w
		|| (k === words.length - 1 && `${folded[i + k]}.` === x.w)));
	if (at < 0) return plain();
	return words.flatMap((x, k) => {
		const w = orig[at + k];
		return [k ? " " : "", x.marked ? build("mark", { textContent: w }, []) : w];
	});
}

// 2026-11-08 -> 08.11.2026., as the board writes dates.
const dmy = (iso) => (iso ? `${iso.slice(0, 10).split("-").reverse().join(".")}.` : "");
// "1 rezultat", "21 rezultat"; every other number "rezultata".
const rezultata = (n) => (n % 10 === 1 && n % 100 !== 11 ? " rezultat" : " rezultata");

// A row without a query (a year, an author): the text's first words. Pagefind's excerpt would start with the title,
// which the row already has (the indexed text is the title, then the text).
function lead(title, text) {
	const t = (title ?? "").split(/\s+/).filter(Boolean), w = (text ?? "").split(/\s+/).filter(Boolean);
	const body = t.every((x, i) => w[i] === x) ? w.slice(t.length) : w;
	return body.slice(0, 30).join(" ") + (body.length > 30 ? " …" : "");
}

// "još 1 post", "još 3 posta", "još 5 postova" of the same thread.
const posta = (n) => (n % 10 === 1 && n % 100 !== 11 ? "post" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "posta" : "postova");

// more: the other results of its thread on this page, merged into this row (showPages).
function renderRow(data, more = 0) {
	const li = rowTpl.content.firstElementChild.cloneNode(true);
	const kind = { dokument: "file", vest: "news" }[data.meta.vrsta];
	if (kind) li.querySelector("use").setAttribute("href", `/static/icons.svg#i-${kind}`);
	const d = li.querySelector(".fr__d");
	d.dateTime = data.meta.datum ?? "";
	d.textContent = dmy(data.meta.datum);
	li.querySelector(".s1").textContent = data.meta.predmet ?? data.meta.smer ?? data.meta.kategorija ?? "";
	const author = li.querySelector(".s2");
	author.textContent = data.meta.autor ?? "";
	// A teacher's full name follows the script switch; a bare username stays as it is.
	if (!author.textContent.includes(" ")) author.dataset.notx = "";
	const a = li.querySelector(".fr__a");
	a.href = data.url;
	a.textContent = data.meta.title;
	const x = li.querySelector(".fr__x");
	if (state.q) x.append(...excerptNodes(data.excerpt, data.meta.tekst));
	else x.textContent = lead(data.meta.title, data.meta.tekst);
	if (more) {
		li.querySelector(".fr__t").append(build("a", {
			className: "fr__in", href: data.meta.tema, textContent: `+ još ${more} ${posta(more)} iz ovog threada`,
		}, []));
	}
	return li;
}

// The active filters as chips; a chip's × clears that choice.
// The count for a screen reader: one live region that stays, as a region made anew with each search is not read.
const live = build("p", { className: "vh", role: "status" }, []);
document.body.append(live);
// The query in the heading in Serbian quotes: „ispit“; one with an exact part as typed, its quotes Serbian: „ispit“ rok.
const quoted = (q) => (q.includes('"') ? `${q.replace(/"([^"]*)"?/g, "„$1“")} (tačno)` : `„${q}“`);
function renderHeading(s, total) {
	const h1 = build("h1", { id: "res-h" }, [build("b", { textContent: String(total) }, []), rezultata(total)]);
	if (s.q) h1.append(" za ", build("span", { className: "q", textContent: quoted(s.q) }, []));
	heading.replaceChildren(h1);
	live.textContent = h1.textContent;
	if (s.q) {
		const order = build("p", { className: "order" }, ["Redosled: "]);
		for (const [value, label] of [[false, "najrelevantnije"], [true, "najnovije"]]) {
			const b = build("button", { type: "button", textContent: label }, []);
			b.setAttribute("aria-pressed", String(s.newest === value));
			b.addEventListener("click", () => {
				newest = value;
				run();
			});
			order.append(b);
		}
		heading.append(order);
	}
	const chips = build("p", { className: "chips" }, []);
	const chip = (label, clear) => {
		const b = build("button", { type: "button", className: "chip", title: "Ukloni filter" }, [label, icon("x")]);
		b.addEventListener("click", () => {
			clear();
			run();
		});
		chips.append(b);
	};
	for (const input of document.querySelectorAll('#sf input[type="hidden"]')) {
		if (!input.value) continue;
		const label = input.name === "from" ? `od ${input.value}` : input.name === "to" ? `do ${input.value}`
			: input.dataset.name ?? input.value;
		chip(label, () => input.remove());
	}
	// Its ×: the switch off, all subjects on the whole site too (site.js, head.js).
	if (s.mine.length) chip(`Moji predmeti (${s.mine.length})`, () => {
		try { localStorage.setItem("sve", "1"); } catch (e) {}
		document.dispatchEvent(new Event("moji"));
	});
	if (chips.children.length) heading.append(chips);
}

function renderEmpty(s) {
	const box = build("div", { className: "empty" }, [build("h2", { textContent: `0 rezultata${s.q ? ` za ${quoted(s.q)}` : ""}` }, [])]);
	box.append(build("ul", {}, [
		build("li", { textContent: "proverite pravopis ili upišite kraći pojam" }, []),
		build("li", { textContent: "uklonite filtere i tražite u celoj arhivi" }, []),
	]));
	res.replaceChildren(box);
}

// A list's pages under it, as /vesti/'s (style.css .lp): first, last, two either side of this one; go(n) opens one.
function renderPager(page, pages, go) {
	const ks = [];
	for (let k = 1; k <= pages; k++) if (k === 1 || k === pages || Math.abs(k - page) <= 2) ks.push(k);
	const btn = (k, text, label) => {
		if (k < 1 || k > pages) return build("span", { className: "lp__a lp__a--off", textContent: text, ariaHidden: "true" }, []);
		if (k === page && !text) {
			const cur = build("span", { className: "lp__a", textContent: String(k) }, []);
			cur.setAttribute("aria-current", "page");
			return cur;
		}
		const b = build("button", { type: "button", className: "lp__a", textContent: text || String(k) }, []);
		if (label) b.setAttribute("aria-label", label);
		b.addEventListener("click", () => go(k));
		return b;
	};
	const parts = [btn(page - 1, "‹", "Prethodna strana")];
	ks.forEach((k, i) => {
		if (i && k - ks[i - 1] > 1) parts.push(build("span", { className: "lp__gap", textContent: "…" }, []));
		parts.push(btn(k));
	});
	parts.push(btn(page + 1, "›", "Sledeća strana"));
	const nav = build("nav", { className: "lp" }, [build("span", { className: "lp__pages" }, parts)]);
	nav.setAttribute("aria-label", "Strane");
	return nav;
}

function icon(name) {
	// Uses the sprite in base.html; the icon is decorative, the button text names the action.
	const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
	svg.setAttribute("class", "i");
	svg.setAttribute("aria-hidden", "true");
	const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
	use.setAttribute("href", `/static/icons.svg#i-${name}`);
	svg.append(use);
	return svg;
}

// The results of a run: total, and get(from, to) -> their data. One search's in its own order; several (a subject's
// acronym searched as its name too, site.js masinciExpand) merged, each text once: by score, or newest first, merged
// as the pages ask (each list is newest first already; only the heads' dates are read).
function pool(lists, newest) {
	const byId = new Map();
	for (const l of lists) for (const r of l) if (!byId.has(r.id) || byId.get(r.id).score < r.score) byId.set(r.id, r);
	if (lists.length < 2 || !newest) {
		const all = lists.length < 2 ? lists[0] ?? [] : [...byId.values()].sort((a, b) => b.score - a.score);
		return { total: all.length, get: (a, b) => Promise.all(all.slice(a, b).map((r) => r.data())) };
	}
	const out = [], pos = lists.map(() => 0), taken = new Set(), cache = new Map();
	const data = (r) => (cache.has(r.id) || cache.set(r.id, r.data()), cache.get(r.id));
	const fill = async (n) => {
		while (out.length < n) {
			const heads = [];
			lists.forEach((l, i) => {
				while (pos[i] < l.length && taken.has(l[pos[i]].id)) pos[i]++;
				if (pos[i] < l.length) heads.push(i);
			});
			if (!heads.length) return;
			const ds = await Promise.all(heads.map((i) => data(lists[i][pos[i]])));
			let best = 0;
			ds.forEach((x, k) => { if ((x.meta.datum ?? "") > (ds[best].meta.datum ?? "")) best = k; });
			taken.add(lists[heads[best]][pos[heads[best]]].id);
			out.push(ds[best]);
		}
	};
	// One fill at a time: two pages asked at once would take the same heads.
	let chain = Promise.resolve();
	return { total: byId.size, get: (a, b) => (chain = chain.then(() => fill(b))).then(() => out.slice(a, b)) };
}

// The lists of a run (run): [{key, title, side, pool}]: the subjects' texts (posts, documents) and the news apart, or
// the one kind a link asked for (?kind=).
let lists = [];
let state = null;

// pages: each list's page by its key ({p, v}). id: the run that asked; a newer run's page wins. Returns false when
// it was too late to draw.
async function showPages(pages, id = runs) {
	const shown = lists.filter((l) => l.pool.total);
	for (const l of lists) pages[l.key] = Math.min(Math.max(1, pages[l.key] || 1), Math.max(1, Math.ceil(l.pool.total / PAGE)));
	writeUrl(state, pages);
	if (!shown.length) {
		renderEmpty(state);
		return true;
	}
	const batches = await Promise.all(shown.map((l) => l.pool.get((pages[l.key] - 1) * PAGE, pages[l.key] * PAGE)));
	if (id !== runs) return false;
	// A teacher or a subject from a link (/?autor=username, /?subject=slug): the chip shows the name, which every
	// result has.
	const first = batches[0][0];
	for (const [name, meta] of [["autor", "autor"], ["subject", "predmet"], ["smer", "smer"]]) {
		const input = form.querySelectorAll(`input[name="${name}"]`);
		if (input.length === 1 && first.meta[meta]) input[0].dataset.name = first.meta[meta];
	}
	res.replaceChildren(...shown.map((l, i) => {
		// One row per thread: its best result, with a link to the whole thread for the others on this page.
		// shortcut: only within a page; a thread can show again on the next one. Merge across pages if that bothers.
		const rows = [], of = {};
		for (const data of batches[i]) {
			const t = data.meta.tema;
			if (t && of[t]) of[t].more++;
			else rows.push(of[t || data.url] = { data, more: 0 });
		}
		const table = resTpl.content.firstElementChild.cloneNode(true);
		const h = table.querySelector(".fb__h");
		h.querySelector("h2").replaceChildren(l.title, build("span", { className: "fb__n", textContent: ` · ${l.pool.total}` }, []));
		h.querySelector(":scope > span").textContent = l.side;
		table.querySelector("ol").append(...rows.map((r) => renderRow(r.data, r.more)));
		const box = build("div", { className: "res__list" }, [table]);
		box.dataset.list = l.key;
		// A page of one list: the other keeps its own; back up to this list's top.
		const n = Math.ceil(l.pool.total / PAGE);
		if (n > 1) box.append(renderPager(pages[l.key], n, (k) => {
			showPages({ ...pages, [l.key]: k }).then(() => res.querySelector(`[data-list="${l.key}"]`)?.scrollIntoView({ block: "start" }));
		}));
		return box;
	}));
	return true;
}

// The board index stays hidden from the start until the first results (search.html, style.css .searching).
const shown = () => document.documentElement.classList.remove("searching");

function showHome() {
	writeUrl(readState(), {});
	heading.innerHTML = home.heading;
	res.innerHTML = home.res;
	other.hidden = true;
	state = null;
	shown();
	// site.js fills "Moji predmeti" again.
	document.dispatchEvent(new Event("pocetna"));
}

// wait: the debounce in ms. Only typing needs one; a click searches at once.
let runs = 0;

async function run(pages = {}) {
	// A slow search that ends after a newer run must not draw over it.
	const id = ++runs;
	const s = readState();
	if (!s.q && !s.kind && !s.smer && !s.subjects.length && !s.authors.length && !s.from && !s.to) return showHome();
	const query = s.q ? fold(s.q) : null;
	const sort = s.q && !s.newest ? undefined : { datum: "desc" };
	// The subjects' texts and the news apart (each its own vrsta filter); a link's ?kind= is one list.
	const kinds = s.kind
		? [{ key: "p", title: KINDS[s.kind] ?? "Rezultati", side: s.kind === "vest" ? "Kategorija" : "Predmet · autor", filters: filtersOf(s) }]
		: [
			{ key: "p", title: "Predmeti", side: "Predmet · autor", filters: { ...filtersOf(s), vrsta: { any: ["obavestenje", "dokument"] } } },
			{ key: "v", title: "Vesti", side: "Kategorija", filters: filtersOf({ ...s, kind: "vest" }) },
		];
	// A subject's acronym in the query: its name searched too (TMO: Tehnologija mašinske obrade).
	const queries = [query, ...(s.q && window.masinciExpand ? await window.masinciExpand(s.q) : [])];
	const pagefind = await loadPagefind();
	const found = await Promise.all(kinds.map((k) => Promise.all(queries.map((q) => pagefind.search(q, { filters: k.filters, sort })))));
	if (id !== runs) return;
	state = s;
	lists = kinds.map((k, i) => ({ ...k, pool: pool(found[i].map((r) => r.results), Boolean(sort)) }));
	// The heading with the rows, in one frame: a new count never stands over the old rows.
	if (await showPages(pages, id)) {
		renderHeading(s, lists.reduce((n, l) => n + l.pool.total, 0));
		shown();
		showMatches(s, id);
	}
}

// Over the texts' results, what the list under the bar finds for the query: subjects, teachers, katedre, the schedule,
// Linkovi (site.js masinciMatches).
const other = build("div", { className: "cmd__list cmd__list--page", hidden: true }, []);
heading.after(other);
async function showMatches(s, id) {
	if (!s.q || !window.masinciMatches) return void (other.hidden = true);
	const box = build("div", { className: "cmd__scroll" }, []);
	const n = await window.masinciMatches(s.q, box);
	if (id !== runs) return;
	other.replaceChildren(box);
	other.hidden = !n;
}

function restoreFromUrl() {
	const p = new URLSearchParams(location.search);
	// Text typed before this module loaded stays, and is searched.
	if (p.has("q")) form.elements.q.value = p.get("q");
	newest = p.get("red") === "novije";
	// A kind, a teacher, a subject, a smer or the years have no choice in the panel: they come from a link (the news'
	// own search, a teacher's page, a year on /statistika/) and stay in the form as a hidden field, shown as a chip until
	// it is removed.
	for (const name of ["kind", "autor", "subject", "smer", "from", "to"]) {
		for (const value of p.getAll(name)) {
			const input = build("input", { type: "hidden", name, value }, []);
			if (name === "kind") input.dataset.name = KINDS[value] ?? value;
			form.append(input);
		}
	}
	return String(p) !== "" || form.elements.q.value.trim() !== "";
}

form.addEventListener("submit", (e) => {
	e.preventDefault();
	run();
});
// Typing shows only the list under the bar (site.js); Enter searches. A box cleared puts the home page back.
form.elements.q.addEventListener("input", () => { if (state && !form.elements.q.value.trim()) run(); });
// A subject followed or no longer followed: a search on view covers the new list.
document.addEventListener("moji", () => { if (state) run(); });
if (restoreFromUrl()) {
	const p = new URLSearchParams(location.search);
	run({ p: Number(p.get("page")) || 1, v: Number(p.get("vpage")) || 1 });
}
