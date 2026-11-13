// Runs in <head>, before the first paint (base.html): the saved theme, so a dark choice does not flash light.
// site.js has the button's click.
try {
	const t = localStorage.getItem("tema");
	if (t) document.documentElement.dataset.tema = t;
	// The phone's browser bar takes the header's colour (base.html has the light one).
	if (t === "dark") document.querySelector('meta[name="theme-color"]').content = "#011321";
	// A font picked in the font menu (site.js), in place of IBM Plex Sans.
	const f = localStorage.getItem("font");
	if (f) document.documentElement.style.setProperty("--sans", f);
} catch (e) {}

// "Moji predmeti": while the side panel's choice is "Samo moji predmeti" ("sve" not "1") and some subjects are
// followed ("moji", site.js), the site shows only them. A style made here hides the others before the first paint:
// [data-pid] is a row of a subject or of a topic in one, [data-pids] a smer's row (its subjects); a box or group left
// without such a row goes too. The home page (#res) keeps its boxes: Studije greys its other smerovi, and Najnovije
// objave shows the followed subjects' newest (site.js fillMine). site.js calls it again when the choice or the subjects
// change; it returns {only, has(href)} for the list counts. sve: the switch as given ("1" off, "" on), not as saved
// (mojiAhead).
window.moji = function (sve) {
	let list = [], all = false;
	try {
		list = (JSON.parse(localStorage.getItem("moji")) || []).map((s) => s.href);
		all = (sve === undefined ? localStorage.getItem("sve") : sve) === "1";
	} catch (e) {}
	const only = list.length > 0 && !all;
	const q = (h) => `"${h.replace(/["\\]/g, "\\$&")}"`;
	let css = "";
	if (only) {
		const pid = list.map((h) => `:not([data-pid=${q(h)}])`).join("");
		const pids = list.map((h) => `:not([data-pids~=${q(h)}])`).join("");
		const any = list.map((h) => `[data-pid=${q(h)}],[data-pids~=${q(h)}]`).join(",");
		// Studije's greyed smerovi: without their last post (and a wide screen's subject count), a half-size icon
		// (centred where the 32px ones are) and less padding: one short line each; a phone's last post is all of
		// .fr__more. The switch fades the change in (site.js fadeStudije).
		const grey = `#res [data-pids]${pids}`;
		css = `[data-pid]${pid},[data-pids]${pids}:not(#res *),:is(.fb,.sg,.sg__s,.sg__slot):not(#res *):has([data-pid],[data-pids]):not(:has(${any}))`
			+ `{display:none!important}${grey}{opacity:.45;padding-block:2px;row-gap:0}`
			+ `${grey} :is(.fr__sub,.fr__last>*){display:none}${grey} .fr__last{min-height:0}`
			+ `@container main (max-width:759.98px){${grey} .fr__more{display:none}}`
			// A wide screen: the name over the whole row; the columns stay in their places under it, faded and unclickable.
			+ `@container main (min-width:760px){${grey} .fr__t{grid-area:1/2/2/-1}`
			+ `${grey} .fr__more>*{grid-row:1;opacity:0;border-left-color:transparent;pointer-events:none}`
			+ `${grey} .fr__more>:nth-child(1){grid-column:3}${grey} .fr__more>:nth-child(2){grid-column:4}${grey} .fr__more>:nth-child(3){grid-column:5}}`
			+ `${grey} .fr__i{width:16px;height:16px;translate:8px 0}${grey} .fr__i .i{width:12px;height:12px}`;
	}
	let style = document.getElementById("moji-css");
	if (!style) {
		style = document.createElement("style");
		style.id = "moji-css";
		document.head.append(style);
	}
	style.textContent = css;
	// For style.css: a list cut short (.fb--short) shows all of what is left.
	document.documentElement.classList.toggle("moji-only", only);
	return { only, n: list.length, has: (h) => list.includes(h) };
};
window.mojiNow = window.moji();

// The page as the saved choice will show it (or the switch as sve gives it, moji()), for fn to measure (site.js):
// moji()'s style for it, fn, then the style on the page back; nothing is painted between.
window.mojiAhead = function (fn, sve) {
	const st = document.getElementById("moji-css"), css = st.textContent, only = document.documentElement.classList.contains("moji-only");
	window.moji(sve);
	const v = fn();
	st.textContent = css;
	document.documentElement.classList.toggle("moji-only", only);
	return v;
};

// The home page's Studije: the smerovi with followed subjects first while only they show (mojiNow.only), else as
// built. Moved in the page, not by CSS order, so the stripes and the tab order follow. search.html calls it right
// after Studije (before the first paint), site.js on each change (its fadeStudije hides the move).
window.mojiSort = function () {
	const ol = document.querySelector("#res > .fb--forums .fb__rows");
	if (!ol) return;
	const rows = ol.built || (ol.built = [...ol.children]), m = window.mojiNow;
	const mine = (r) => m.only && (r.dataset.pids || "").split(" ").some(m.has);
	ol.append(...rows.filter(mine), ...rows.filter((r) => !mine(r)));
};

// The page's parts that show a saved choice, set before the first frame by a script right after them (the side panel's
// last, sidebar.html; predmet.html's star; raspored.html's programs) and again by site.js when the choice changes.

// The side panel's "Obaveštenja" (the subjects followed, the switch "Samo moji predmeti", the link to the picker) and
// the header's theme and script buttons.
window.showSaved = function () {
	const d = document, n = window.mojiNow.n, iz = d.querySelector("[data-izbor]");
	if (iz) {
		iz.hidden = false;
		const count = iz.querySelector("[data-moji-n]");
		if (count.textContent !== String(n || "")) count.textContent = n || "";
		iz.querySelector("[data-moji-scope]").hidden = !n;
		let all = false;
		try { all = localStorage.getItem("sve") === "1"; } catch (e) {}
		iz.querySelector("[data-moji-only]").checked = !all;
		// The followed subjects are not listed here: the link says that some are, and opens them.
		const open = iz.querySelector("[data-moji-open]");
		if (open.classList.contains("is-set") !== n > 0) {
			open.classList.toggle("is-set", n > 0);
			open.querySelector("span").textContent = n ? "Izmeni predmete" : "Izaberi predmete";
			open.querySelector("use").setAttribute("href", "/static/icons.svg#i-star" + (n ? "-on" : ""));
		}
		// A phone's chip (style.css): "17 predmeta".
		const c = n ? n + (n % 10 === 1 && n % 100 !== 11 ? " predmet" : " predmeta") : "";
		const chip = open.querySelector("[data-moji-c]");
		if (chip.textContent !== c) chip.textContent = c;
	}
	const tb = d.getElementById("tema"), dark = d.documentElement.dataset.tema === "dark";
	if (tb) {
		tb.querySelector("use").setAttribute("href", dark ? "/static/icons.svg#i-moon" : "/static/icons.svg#i-sun");
		tb.setAttribute("aria-label", "Tema: " + (dark ? "tamna" : "svetla"));
	}
	if (window.pismoButton) window.pismoButton();
};

// A subject page's star (predmet.html): followed or not.
window.showStar = function () {
	const star = document.querySelector("[data-star]");
	if (!star) return;
	const on = window.mojiNow.has(star.dataset.star);
	star.hidden = false;
	star.setAttribute("aria-pressed", on);
	star.querySelector("use").setAttribute("href", "/static/icons.svg#i-star" + (on ? "-on" : ""));
	star.querySelector("span").textContent = on ? "Pratiš" : "Prati";
};

// The lecture schedule (/raspored/): one program at a time, picked by its tab. key: the program (else the #, else the
// one picked last time, else the first); keep: remember it, for the next visit and in the URL. Without scripts the
// tabs are links to the programs one under the other.
window.rsPick = function (key, keep) {
	const rs = document.querySelector("[data-rs]"), progs = rs ? [...rs.querySelectorAll("[data-prog]")] : [];
	if (!progs.length) return;
	if (key === undefined) {
		key = decodeURIComponent(location.hash.slice(1));
		try { key = key || localStorage.getItem("raspored"); } catch (e) {}
	}
	if (!progs.some((p) => p.id === key)) key = progs[0].id;
	rs.classList.add("rs--tabs");
	progs.forEach((p) => { p.hidden = p.id !== key; });
	rs.querySelectorAll("[data-rs-tab]").forEach((t) => t.setAttribute("aria-current", t.hash === "#" + key));
	if (!keep) return;
	try { localStorage.setItem("raspored", key); } catch (e) {}
	history.replaceState(null, "", "#" + key);
};
