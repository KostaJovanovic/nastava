// Runs in <head>, before the first paint (base.html): the saved theme, so a dark choice does not flash light.
// site.js has the button.
try {
	const t = localStorage.getItem("tema");
	if (t) document.documentElement.dataset.tema = t;
	// The phone's browser bar takes the header's colour (base.html has the light one).
	if (t === "dark") document.querySelector('meta[name="theme-color"]').content = "#011321";
} catch (e) {}
