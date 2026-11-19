// Runs in <head>, before the first paint (base.html): the saved theme, so a dark choice does not flash light.
// site.js has the button's click.
// Scripts run (style.css "Without JavaScript"): not @media (scripting), which a blocker such as NoScript or uBlock
// leaves at "enabled".
document.documentElement.dataset.js = "";
try {
	const t = localStorage.getItem("tema");
	if (t) document.documentElement.dataset.tema = t;
	// The phone's browser bar takes the header's colour (base.html has the light one).
	if (t === "dark") document.querySelector('meta[name="theme-color"]').content = "#011321";
} catch (e) {}

// No "install the site" banner on arrival (Samsung Internet, Chrome's mini-infobar): the manifest stays, for the
// iPhone's home screen push (base.html); the browser's menu can still install it. site.js offers the APK instead.
addEventListener("beforeinstallprompt", (e) => e.preventDefault());

// Teacher photos fade in once loaded (style.css [data-fade]): too small for a progressive JPG's passes to show, they
// would otherwise appear all at once. Set here, before any <img> is parsed, so no load is missed; a failed one shows too.
document.documentElement.dataset.fade = "";
for (const ev of ["load", "error"])
	document.addEventListener(ev, (e) => e.target.matches?.(".pc__img, .tp__img") && (e.target.dataset.in = ""), true);

// "Moji predmeti": while the side panel's choice is "Samo moji predmeti" ("sve" not "1") and some subjects are
// followed ("moji", site.js), the site shows only them. A style made here hides the others before the first paint:
// [data-pid] is a row of a subject or of a topic in one, [data-pids] a smer's row (its subjects); a box or group left
// without such a row goes too. The home page (#res) keeps its boxes: Studije greys its other smerovi, and Najnovije
// threadovi shows the followed subjects' newest (site.js fillMine). site.js calls it again when the choice or the subjects
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
		// With subjects chosen, no heading: the switch says what the panel is, with the count.
		iz.querySelector("#moji-h").hidden = n > 0;
		iz.querySelector("[data-moji-scope]").hidden = !n;
		let all = false;
		try { all = localStorage.getItem("sve") === "1"; } catch (e) {}
		iz.querySelector("[data-moji-only]").checked = !all;
		// The followed subjects are not listed here: the link says that some are, and opens them.
		const open = iz.querySelector("[data-moji-open]");
		if (open.classList.contains("is-set") !== n > 0) {
			open.classList.toggle("is-set", n > 0);
			open.querySelector("span").textContent = n ? "Izmeni predmete" : "Izaberi predmete";
			open.querySelector("use").setAttribute("href", "#i-star" + (n ? "-on" : ""));
		}
		const chip = iz.querySelector("[data-moji-c]");
		if (chip.textContent !== String(n || "")) chip.textContent = n || "";
	}
	// The side panel's link to the saved posts (/sacuvano/): only once something is saved, with how many.
	const sv = d.querySelector("[data-saved]"), ns = window.savedList().length;
	if (sv) {
		sv.hidden = !ns;
		sv.querySelector("[data-saved-n]").textContent = ns || "";
	}
	const tb = d.getElementById("tema"), dark = d.documentElement.dataset.tema === "dark";
	if (tb) {
		tb.querySelector("use").setAttribute("href", dark ? "#i-moon" : "#i-sun");
		tb.setAttribute("aria-label", "Tema: " + (dark ? "tamna" : "svetla"));
	}
	if (window.pismoButton) window.pismoButton();
};

// Saved posts and topics, in this browser only: [{href, title, sub, date}] in localStorage "sacuvano", newest first
// (site.js saves; /sacuvano/ lists them).
window.savedList = function () {
	try { return JSON.parse(localStorage.getItem("sacuvano")) || []; } catch (e) { return []; }
};
// The page's address as saved: its canonical path (the github.io copy's canonical is the main domain's).
window.herePath = function () {
	return new URL((document.querySelector('link[rel="canonical"]') || location).href).pathname;
};
// A post's or topic's "Sačuvaj" (detail.html, tema.html): saved or not.
window.showBookmark = function () {
	const here = window.herePath(), on = window.savedList().some((s) => s.href === here);
	for (const b of document.querySelectorAll("[data-save]")) {
		b.hidden = false;
		b.setAttribute("aria-pressed", on);
		b.querySelector("use").setAttribute("href", "#i-bookmark" + (on ? "-on" : ""));
		b.querySelector("span").textContent = on ? "Sačuvano" : "Sačuvaj";
	}
};

// A subject page's star (predmet.html): followed or not.
window.showStar = function () {
	const star = document.querySelector("[data-star]");
	if (!star) return;
	const on = window.mojiNow.has(star.dataset.star);
	star.hidden = false;
	star.setAttribute("aria-pressed", on);
	star.querySelector("use").setAttribute("href", "#i-star" + (on ? "-on" : ""));
	star.querySelector("span").textContent = on ? "Pratiš" : "Prati";
};

// "Nazad" under the crumbs (base.html; site.js tells the whole of it): the page this one was opened from, shown before
// the first frame, so the rows under it do not move down after it. Gives that page, {u, t}, or null. Not in a
// prerender: it sees the tab's sessionStorage only once shown (site.js calls it again then).
// The page the tab showed last ('cur', site.js keepCur), when it is the referrer: else this page has no "Nazad".
const openedFrom = () => {
	let left = null, ref = null;
	try { left = JSON.parse(sessionStorage.getItem("cur")); ref = document.referrer && new URL(document.referrer); } catch (e) {}
	const from = left && left.u.split("?")[0];
	return ref && ref.origin === location.origin && from === ref.pathname && from !== location.pathname ? left : null;
};
window.showBackLink = function () {
	if (document.prerendering) return null;
	const a = document.querySelector("[data-back]"), st = history.state || {};
	let prev = st.back;
	if (!prev && (prev = openedFrom())) history.replaceState(Object.assign({}, st, { back: prev }), "");
	if (a && prev) {
		a.href = prev.u;
		a.querySelector("b").textContent = prev.t;
		a.hidden = false;
	}
	return prev || null;
};

// The failed-update banner (base.html .fail): its two UTC times in the reader's, "sutra" before the next try when
// that is on the day after the failure.
window.showFail = function () {
	const t = document.querySelectorAll(".fail time"), p2 = (n) => String(n).padStart(2, "0");
	const a = new Date(t[0] && t[0].dateTime), n = new Date(t[1] && t[1].dateTime);
	if (isNaN(a) || isNaN(n)) return;
	const hm = (d) => "u " + p2(d.getHours()) + ":" + p2(d.getMinutes());
	t[0].textContent = hm(a);
	t[1].textContent = (n.toDateString() !== a.toDateString() ? "sutra " : "") + hm(n);
};

// The stale banner (base.html .fail[data-stale]): the board last read over a day ago, its time as the footer's
// (site.js); it replaces the failed-update banner.
window.showStale = function () {
	const b = document.querySelector(".fail[data-stale]"), t = b && b.querySelector("time"), d = new Date(t && t.dateTime);
	if (isNaN(d) || Date.now() - d < 864e5) return;
	const p2 = (n) => String(n).padStart(2, "0"), f = document.querySelector(".fail:not([data-stale])");
	t.textContent = "u " + p2(d.getHours()) + ":" + p2(d.getMinutes()) + ", " + p2(d.getDate()) + "." + p2(d.getMonth() + 1) + "." + d.getFullYear() + ".";
	if (f) f.hidden = true;
	b.hidden = false;
};

// "Profesor dana" (sidebar.html): t is one of /izbor.json dana (site.js picks it, load_teachers.of_the_day).
window.fillDana = function (dana, t) {
	const a = dana.querySelector(".dana__b");
	a.href = t[2];
	dana.querySelector(".sec").textContent = t[0];
	a.querySelector("img").src = t[3];
	a.querySelector("b").textContent = t[1];
	a.querySelector("small").textContent = t[4] || "";
	// The katedra's icon, as on /nastavnici/'s cards (cards.html .pc__ki). Hidden again for a pick without one: a saved
	// pick (showDana) can be another teacher than site.js's after a deploy.
	a.querySelector(".dana__ki").toggleAttribute("hidden", !t[5]);
	if (t[5]) a.querySelector("use").setAttribute("href", "#i-" + t[5]);
	// The Studentska lista badge, the same text as cards.html sp_badge.
	const sp = dana.querySelector(".dana__sp");
	sp.hidden = !t[6];
	if (t[6]) {
		const tip = "Studentska lista „Studenti pobeđuju“, parlamentarni izbori 2026: " + t[6] + ". na listi";
		sp.setAttribute("aria-label", tip);
		sp.querySelector(".sp__tip").textContent = tip;
	}
	dana.hidden = false;
};

// Today's pick as site.js saved it, before the first frame (base.html rel=expect): site.js runs after the whole page,
// and on a long one the card would come in seconds after the rest.
window.showDana = function () {
	const dana = document.querySelector("[data-dana]");
	let saved = null;
	try { saved = JSON.parse(localStorage.getItem("dana")); } catch (e) {}
	if (!dana || !saved || saved.day !== new Date().toDateString()) return;
	// Seen on an earlier page, so in the cache: no fade in (data-fade above), which would blink it on each page.
	const img = dana.querySelector("img");
	img.decoding = "sync";
	img.dataset.in = "";
	window.fillDana(dana, saved.t);
};

// The lecture schedule (/raspored/): one program at a time, picked by its tab. key: the program (else the #, else the
// one picked last time, else the first); keep: remember it, for the next visit and in the URL. Without scripts the
// tabs are links to the programs one under the other.
window.rsPick = function (key, keep) {
	const rs = document.querySelector("[data-rs]"), progs = rs ? [...rs.querySelectorAll("[data-prog]")] : [];
	if (!progs.length) return;
	if (key === undefined) {
		key = decodeURIComponent(location.hash.slice(1));
		try { key = key || localStorage.getItem(rs.dataset.rs || "raspored"); } catch (e) {}
	}
	if (!progs.some((p) => p.id === key)) key = progs[0].id;
	rs.classList.add("rs--tabs");
	progs.forEach((p) => { p.hidden = p.id !== key; });
	rs.querySelectorAll("[data-rs-tab]").forEach((t) => t.setAttribute("aria-current", t.hash === "#" + key));
	if (!keep) return;
	try { localStorage.setItem(rs.dataset.rs || "raspored", key); } catch (e) {}
	history.replaceState(history.state, "", "#" + key);
};
