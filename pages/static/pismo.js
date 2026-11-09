// Script switch for the whole page: Latin (the default), Cyrillic, or the text as it was posted.
// It rewrites the text nodes in the browser and keeps each original, so a switch back is exact.
// New content (search results, the subject list) is converted as it arrives. The choice is kept in localStorage.
(function () {
	const KEY = "pismo";
	const L = Object.fromEntries([..."абвгдђежзијклљмнњопрстћуфхцчџш"].map((c, i) =>
		[c, "a b v g d đ e ž z i j k l lj m n nj o p r s t ć u f h c č dž š".split(" ")[i]]));
	const C = Object.fromEntries(Object.entries(L).map(([c, l]) => [l, c]));
	// Elements whose text stays as it is: code, the hidden search copy (.pf), and the switch itself.
	const SKIP = "script, style, textarea, code, .pf, [data-notx]";
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
		return s.replace(/\S+/g, (w) =>
			// Foreign words, addresses and file names stay in Latin.
			// The file extension or domain ends the word, so "maš.inž." is still converted.
			/[qwxyQWXY@]|:\/\/|www\.|\.[a-z]{2,4}[)\],.;:!?]*$/.test(w) ? w
				: w.replace(/dž|lj|nj|[a-zčćšžđ]/gi, (m) => {
					const c = C[m.toLowerCase()];
					return !c ? m : m === m.toLowerCase() ? c : c.toUpperCase();
				}));
	}

	// For comparing names in either script (the subject search in the side panel).
	window.pismoFold = (s) => toLat(s).toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/đ/g, "dj");

	// Blocked storage throws: the switch then lasts for this page only (as head.js and site.js do for the theme).
	let mode = "lat";
	try { mode = localStorage.getItem(KEY) || mode; } catch (e) {}
	const text = new WeakMap();
	const attrs = new WeakMap();
	const convert = (s) => (mode === "lat" ? toLat(s) : mode === "cyr" ? toCyr(s) : s);

	function convertNode(n) {
		if (!text.has(n)) text.set(n, n.nodeValue);
		const v = convert(text.get(n));
		if (n.nodeValue !== v) n.nodeValue = v;
	}

	function apply(root) {
		if (root.nodeType === Node.TEXT_NODE) {
			if (!root.parentElement?.closest(SKIP)) convertNode(root);
			return;
		}
		if (root.nodeType !== Node.ELEMENT_NODE || root.closest(SKIP)) return;
		const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
			acceptNode: (n) => (n.parentElement.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
		});
		for (let n = walker.nextNode(); n; n = walker.nextNode()) convertNode(n);
		for (const el of [root, ...root.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(","))]) {
			if (el.closest(SKIP)) continue;
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
	const LABEL = { lat: ["Lat", "inica"], cyr: ["Ћир", "илица"], orig: ["Orig", "inalno"] };
	const MODES = Object.keys(LABEL);
	if (!LABEL[mode]) mode = "lat";

	const title = document.title;
	function set(m) {
		mode = m;
		try { localStorage.setItem(KEY, m); } catch (e) {}
		document.documentElement.lang = m === "cyr" ? "sr-Cyrl" : m === "lat" ? "sr-Latn" : "sr";
		document.title = convert(title);
		apply(document.body);
		const b = document.getElementById("pismo");
		if (!b) return;
		const [short, rest] = LABEL[m];
		b.dataset.pismo = m;
		b.innerHTML = `${short}<span>${rest}</span>`;
		b.setAttribute("aria-label", "Pismo: " + short + rest);
	}

	// Our own changes are to text (characterData), which this does not watch, so it cannot loop.
	new MutationObserver((records) => {
		for (const r of records) for (const n of r.addedNodes) apply(n);
	}).observe(document.body, { childList: true, subtree: true });
	document.addEventListener("click", (e) => {
		if (e.target.closest("#pismo")) set(MODES[(MODES.indexOf(mode) + 1) % MODES.length]);
	});
	set(mode);
})();
