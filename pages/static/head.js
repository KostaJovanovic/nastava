// Runs in <head>, before the first paint (base.html): the saved theme, so a dark choice does not flash light.
// site.js has the button.
try {
	const t = localStorage.getItem("tema");
	if (t) document.documentElement.dataset.tema = t;
	// The phone's browser bar takes the header's colour (base.html has the light one).
	if (t === "dark") document.querySelector('meta[name="theme-color"]').content = "#011321";
} catch (e) {}

// "Moji predmeti": while the side panel's choice is "Samo moji predmeti" ("sve" not "1") and some subjects are
// followed ("moji", site.js), the site shows only them. A style made here hides the others before the first paint:
// [data-pid] is a row of a subject or of a topic in one, [data-pids] a smer's row (its subjects); a box or group left
// without such a row goes too. site.js calls it again when the choice or the subjects change; it returns
// {only, has(href)} for the list counts.
window.moji = function () {
	let list = [], all = false;
	try {
		list = (JSON.parse(localStorage.getItem("moji")) || []).map((s) => s.href);
		all = localStorage.getItem("sve") === "1";
	} catch (e) {}
	const only = list.length > 0 && !all;
	const q = (h) => `"${h.replace(/["\\]/g, "\\$&")}"`;
	let css = "";
	if (only) {
		const pid = list.map((h) => `:not([data-pid=${q(h)}])`).join("");
		const pids = list.map((h) => `:not([data-pids~=${q(h)}])`).join("");
		const any = list.map((h) => `[data-pid=${q(h)}],[data-pids~=${q(h)}]`).join(",");
		css = `[data-pid]${pid},[data-pids]${pids},:is(.fb,.sg,.sg__s,.sg__slot):has([data-pid],[data-pids]):not(:has(${any}))`
			+ "{display:none!important}";
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
	return { only, has: (h) => list.includes(h) };
};
window.mojiNow = window.moji();
