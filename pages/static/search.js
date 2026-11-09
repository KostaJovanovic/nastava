// Client search over the Pagefind index. The site has no server: all search state is in the URL.
// Without a query or a filter in the URL, the page keeps the newest items from the build.
const PAGE = 20;
const form = document.getElementById("sf");
const res = document.getElementById("res");
const heading = document.querySelector(".mh");
const status = document.querySelector("nav.status");
const rowTpl = document.getElementById("row-tpl");
const resTpl = document.getElementById("res-tpl");
const years = JSON.parse(document.querySelector("script[data-years]").dataset.years);
// No index (a build Pagefind did not run on, or no network): the board index shows, with a note, not "Tražim…".
const pagefind = await import("/pagefind/pagefind.js").catch(() => null);
if (!pagefind) {
	document.documentElement.classList.remove("searching");
	heading.append(build("p", { className: "note", textContent: "Pretraga trenutno nije dostupna." }, []));
	throw new Error("pagefind.js did not load");
}
await pagefind.options({ excerptLength: 30 });
// A search returns counts only for the filter groups that are loaded, so load all of them first.
// These are also the counts of the whole archive: a search that would match every item takes about a second.
// Only the "Vrsta" group shows counts, and only when documents are archived (sidebar.html): else skip that second.
const TOTALS = document.querySelector('.filters input[name="kind"]') ? await pagefind.filters() : {};
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
		q: String(f.get("q") ?? "").trim(),
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

function writeUrl(s, page) {
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
	if (page > 1) p.set("page", page);
	history.replaceState(null, "", p.size ? `?${p}` : location.pathname);
}

function filtersOf(s) {
	// Pagefind needs a filter for a search without a query; run() only searches then when some filter is set.
	// "vrsta" only when picked: as a filter on every search it doubled the time of one with a query.
	const filters = s.kind ? { vrsta: { any: [s.kind] } } : {};
	if (s.smer) filters.smer = { any: [s.smer] };
	if (s.subjects.length) filters.predmet = { any: s.subjects };
	if (s.authors.length) filters.autor = { any: s.authors };
	if (s.mine.length) filters.pid = { any: s.mine };
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

// "još 1 post", "još 3 posta", "još 5 postova" of the same objava.
const posta = (n) => (n % 10 === 1 && n % 100 !== 11 ? "post" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "posta" : "postova");

// more: the other results of its objava on this page, merged into this row (showPage).
function renderRow(data, more = 0) {
	const li = rowTpl.content.firstElementChild.cloneNode(true);
	if (data.meta.vrsta === "dokument") li.querySelector("use").setAttribute("href", "/static/icons.svg#i-file");
	const d = li.querySelector(".fr__d");
	d.dateTime = data.meta.datum ?? "";
	d.textContent = dmy(data.meta.datum);
	li.querySelector(".s1").textContent = data.meta.predmet ?? data.meta.smer ?? "";
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
			className: "fr__in", href: data.meta.tema, textContent: `+ još ${more} ${posta(more)} iz ove objave`,
		}, []));
	}
	return li;
}

// The active filters as chips; a chip's × clears that choice.
function renderHeading(s, total) {
	const h1 = build("h1", { id: "res-h", role: "status" }, [build("b", { textContent: String(total) }, []), rezultata(total)]);
	if (s.q) h1.append(" za ", build("span", { className: "q", textContent: `„${s.q}“` }, []));
	heading.replaceChildren(h1);
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
	const active = '.filters input[form="sf"]:checked, #sf input[type="hidden"]';
	for (const input of document.querySelectorAll(active)) {
		if (!input.value) continue;
		const label = input.name === "from" ? `od ${input.value}` : input.name === "to" ? `do ${input.value}`
			: input.dataset.name ?? input.value;
		chip(label, () => {
			if (input.type === "hidden") input.remove();
			else document.querySelector(`.filters input[name="${input.name}"][value=""]`).checked = true;
		});
	}
	// Its ×: the switch off, all subjects on the whole site too (site.js, head.js).
	if (s.mine.length) chip(`Moji predmeti (${s.mine.length})`, () => {
		try { localStorage.setItem("sve", "1"); } catch (e) {}
		document.dispatchEvent(new Event("moji"));
	});
	if (chips.children.length) heading.append(chips);
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
	use.setAttribute("href", `/static/icons.svg#i-${name}`);
	svg.append(use);
	return svg;
}

// The filter groups with counts in the side panel. A teacher, a subject or a smer has none: it comes only from a link.
const GROUP = { kind: "vrsta" };

async function groupCounts(s, query, search) {
	// Each group counts without its own filter, so picking one value does not drop the others to 0.
	const counts = {};
	for (const [field, group] of Object.entries(GROUP)) {
		if (!s[field]) {
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
	for (const input of document.querySelectorAll('.filters input[form="sf"][type="radio"]')) {
		const n = input.closest("label").querySelector(".n");
		const group = counts[GROUP[input.name]];
		if (!n || !group) continue;
		n.textContent = input.value ? (group[input.value] ?? 0) : sum(group);
	}
}

let results = [];
let state = null;

// id: the run that asked; a newer run's page wins. Returns false when it was too late to draw.
async function showPage(page, id = runs) {
	const pages = Math.max(1, Math.ceil(results.length / PAGE));
	page = Math.min(Math.max(1, page), pages);
	writeUrl(state, page);
	if (!results.length) {
		renderEmpty(state);
	} else {
		const batch = await Promise.all(results.slice((page - 1) * PAGE, page * PAGE).map((r) => r.data()));
		if (id !== runs) return false;
		// A teacher or a subject from a link (/?autor=username, /?subject=slug): the chip shows the name, which every
		// result has.
		for (const [name, meta] of [["autor", "autor"], ["subject", "predmet"], ["smer", "smer"]]) {
			const input = form.querySelectorAll(`input[name="${name}"]`);
			if (input.length === 1 && batch[0].meta[meta]) input[0].dataset.name = batch[0].meta[meta];
		}
		// One row per objava: its best result, with a link to the whole objava for the others on this page.
		// shortcut: only within a page; an objava can show again on the next one. Merge across pages if that bothers.
		const rows = [], of = {};
		for (const data of batch) {
			const t = data.meta.tema;
			if (t && of[t]) of[t].more++;
			else rows.push(of[t || data.url] = { data, more: 0 });
		}
		const table = resTpl.content.firstElementChild.cloneNode(true);
		table.querySelector("ol").append(...rows.map((r) => renderRow(r.data, r.more)));
		res.replaceChildren(table);
	}
	renderPager(page, pages, (n) => {
		showPage(n);
		heading.scrollIntoView({ block: "start" });
	});
	return true;
}

// The board index stays hidden from the start until the first results (search.html, style.css .searching).
const shown = () => document.documentElement.classList.remove("searching");

function showHome() {
	writeUrl(readState(), 1);
	heading.innerHTML = home.heading;
	res.innerHTML = home.res;
	status.querySelector(".pg")?.remove();
	updateCounts({ vrsta: TOTALS.vrsta ?? {} });
	state = null;
	shown();
	// site.js fills "Moji predmeti" again.
	document.dispatchEvent(new Event("pocetna"));
}

// wait: the debounce in ms. Only typing needs one; a click searches at once.
let runs = 0;

async function run(page = 1, wait = 0) {
	// A slow search that ends after a newer run must not draw over it.
	const id = ++runs;
	const s = readState();
	for (const input of document.querySelectorAll('.filters input[type="radio"]')) {
		input.closest("label").classList.toggle("is-on", input.checked);
	}
	if (!s.q && !s.kind && !s.smer && !s.subjects.length && !s.authors.length && !s.from && !s.to) return showHome();
	const query = s.q ? fold(s.q) : null;
	const sort = s.q && !s.newest ? undefined : { datum: "desc" };
	const search = await pagefind.debouncedSearch(query, { filters: filtersOf(s), sort }, wait);
	if (search === null || id !== runs) return;
	const counts = await groupCounts(s, query, search);
	if (id !== runs) return;
	state = s;
	results = search.results;
	updateCounts(counts);
	// The heading with the rows, in one frame: a new count never stands over the old rows.
	if (await showPage(page, id)) {
		renderHeading(s, results.length);
		shown();
	}
}

function restoreFromUrl() {
	const p = new URLSearchParams(location.search);
	// Text typed before this module loaded stays, and is searched.
	if (p.has("q")) form.elements.q.value = p.get("q");
	newest = p.get("red") === "novije";
	for (const input of document.querySelectorAll('input[form="sf"]')) {
		if (input.type === "radio") input.checked = input.value === (p.get(input.name) ?? "");
	}
	// A teacher, a subject, a smer or the years have no choice in the panel: they come from a link (a teacher's page,
	// a year on /statistika/) and stay in the form as a hidden field, shown as a chip until it is removed.
	for (const name of ["autor", "subject", "smer", "from", "to"]) {
		for (const value of p.getAll(name)) form.append(build("input", { type: "hidden", name, value }, []));
	}
	return p.size > 0 || form.elements.q.value.trim() !== "";
}

// The header search's scope (site.js): in the teachers or the subjects, the bar does not search the posts.
const posts = () => !["nastavnici", "predmeti"].includes(form.dataset.u);
form.addEventListener("submit", (e) => {
	e.preventDefault();
	if (posts()) run();
});
form.elements.q.addEventListener("input", () => { if (posts()) run(1, 200); });
// A subject followed or no longer followed: a search on view covers the new list.
document.addEventListener("moji", () => { if (state) run(); });
if (restoreFromUrl() && posts()) run(Number(new URLSearchParams(location.search).get("page")) || 1);
