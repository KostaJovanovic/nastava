// Runs in <head>, before the first paint (base.html): the saved theme, so a dark choice does not flash light.
// site.js has the button.
try {
	const t = localStorage.getItem("tema");
	if (t) document.documentElement.dataset.tema = t;
} catch (e) {}
