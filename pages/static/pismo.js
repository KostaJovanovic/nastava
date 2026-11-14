// Script switch for the whole page: Latin (the default) or Cyrillic.
// It rewrites the text nodes in the browser and keeps each original, so a switch back is exact.
// New content (search results, the subject list) is converted as it arrives. The choice is kept in localStorage.
(function () {
	const KEY = "pismo";
	const L = Object.fromEntries([..."абвгдђежзијклљмнњопрстћуфхцчџш"].map((c, i) =>
		[c, "a b v g d đ e ž z i j k l lj m n nj o p r s t ć u f h c č dž š".split(" ")[i]]));
	const C = Object.fromEntries(Object.entries(L).map(([c, l]) => [l, c]));
	// Elements whose text stays as it is: code, the hidden search copy (.pf), and the switch itself.
	const SKIP = "head, script, style, textarea, code, .pf, [data-notx]";
	const ATTRS = ["placeholder", "title", "aria-label"];

	function toLat(s) {
		return s.replace(/[Ѐ-ӿ]/g, (c, i) => {
			const low = c.toLowerCase();
			const l = L[low];
			if (l === undefined || c === low) return l ?? c;
			// Љ is "LJ" inside an all-capitals word, "Lj" otherwise.
			const next = s[i + 1];
			return next && next !== next.toLowerCase() ? l.toUpperCase() : l[0].toUpperCase() + l.slice(1);
		});
	}

	function toCyr(s) {
		const letters = (w) => w.replace(/dž|lj|nj|[a-zčćšžđ]/gi, (m) => {
			const c = C[m.toLowerCase()];
			return !c ? m : m === m.toLowerCase() ? c : c.toUpperCase();
		});
		return s.replace(/\S+/g, (w) =>
			// The site's "thread" (a forum topic) is "niz" in Cyrillic, ending and all: threadova, низова.
			/^\W*thread/i.test(w) ? letters(w.replace(/thread/i, (t) => t === "THREAD" ? "NIZ" : t[0] === "T" ? "Niz" : "niz"))
			// Foreign words, addresses and file names stay in Latin.
			// The file extension or domain ends the word, so "maš.inž." is still converted.
			: /[qwxyQWXY@]|:\/\/|www\.|\.[a-z]{2,4}[)\],.;:!?]*$/.test(w) ? w
			: letters(w));
	}

	// For comparing names in either script (the subject search in the side panel).
	window.pismoFold = (s) => toLat(s).toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/đ/g, "dj");

	// Blocked storage throws: the switch then lasts for this page only (as head.js and site.js do for the theme).
	let mode = "lat";
	try { mode = localStorage.getItem(KEY) || mode; } catch (e) {}
	const text = new WeakMap();
	const shown = new WeakMap();
	const attrs = new WeakMap();
	const convert = (s) => (mode === "cyr" ? toCyr(s) : toLat(s));

	// kept: the page's second pass (DOMContentLoaded), which leaves a node shown as this mode has it.
	function convertNode(n, kept) {
		const s = shown.get(n);
		if (kept && n.nodeValue === s) return;
		if (s === undefined) text.set(n, n.nodeValue);
		// The parser added to it after it was converted (its text came in two network chunks): the new end is original
		// too. Changed some other way: that is the original now.
		else if (n.nodeValue !== s) text.set(n, n.nodeValue.startsWith(s) ? text.get(n) + n.nodeValue.slice(s.length) : n.nodeValue);
		const v = convert(text.get(n));
		if (n.nodeValue !== v) n.nodeValue = v;
		shown.set(n, v);
	}

	function apply(root, kept) {
		if (root.nodeType === Node.TEXT_NODE) {
			if (!root.parentElement?.closest(SKIP)) convertNode(root, kept);
			return;
		}
		if (root.nodeType !== Node.ELEMENT_NODE || root.closest(SKIP)) return;
		const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
			acceptNode: (n) => (n.parentElement.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
		});
		for (let n = walker.nextNode(); n; n = walker.nextNode()) convertNode(n, kept);
		for (const el of [root, ...root.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(","))]) {
			if (el.closest(SKIP) || (kept && attrs.has(el))) continue;
			const saved = attrs.get(el) ?? {};
			for (const a of ATTRS) {
				if (!el.hasAttribute(a)) continue;
				saved[a] ??= el.getAttribute(a);
				el.setAttribute(a, convert(saved[a]));
			}
			attrs.set(el, saved);
		}
	}

	// An attribute a script changes later (site.js: the header search's placeholder): pismoAttr(el, a, v) keeps v as
	// the original and shows it converted; pismoAttr(el, a) returns the original.
	window.pismoAttr = (el, a, v) => {
		const saved = attrs.get(el) ?? {};
		if (v === undefined) return saved[a] ?? el.getAttribute(a);
		saved[a] = v;
		attrs.set(el, saved);
		el.setAttribute(a, convert(v));
	};

	// The button's label per mode (the part in <span> shows on wide screens), in the order a click cycles them.
	// A saved "orig" (the posted text, a choice no longer offered) is Latin again.
	const LABEL = { lat: ["Lat", "inica"], cyr: ["Ћир", "илица"] };
	const MODES = Object.keys(LABEL);
	if (!LABEL[mode]) mode = "lat";

	// The header's button as the mode has it: also run before the first frame, from sidebar.html (head.js showSaved).
	window.pismoButton = () => {
		const b = document.getElementById("pismo");
		// base.html has the Latin one.
		if (!b || b.dataset.pismo === mode) return;
		const [short, rest] = LABEL[mode];
		b.dataset.pismo = mode;
		b.innerHTML = `${short}<span>${rest}</span>`;
		b.setAttribute("aria-label", "Pismo: " + short + rest);
	};

	const title = document.title;
	const lang = () => { document.documentElement.lang = mode === "cyr" ? "sr-Cyrl" : "sr-Latn"; };
	function set(m, kept) {
		mode = m;
		try { localStorage.setItem(KEY, m); } catch (e) {}
		lang();
		document.title = convert(title);
		apply(document.body, kept);
		window.pismoButton();
	}

	// Loaded in <head> (base.html): each node is converted as the parser adds it, before any frame shows it (an
	// observer's callback runs first), so neither script flashes. Then the whole page once more, when it is parsed, for
	// the text the parser added to after converting it (kept: what is shown as converted is left alone).
	// Our own changes are to text (characterData), which this does not watch, so it cannot loop.
	new MutationObserver((records) => {
		for (const r of records) for (const n of r.addedNodes) apply(n);
	}).observe(document.documentElement, { childList: true, subtree: true });
	document.addEventListener("click", (e) => {
		if (e.target.closest("#pismo")) set(MODES[(MODES.indexOf(mode) + 1) % MODES.length]);
	});
	lang();
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => set(mode, true));
	else set(mode);
})();
