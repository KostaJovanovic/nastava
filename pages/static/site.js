/* Optional enhancements of every page (base.html). Every page works without this script.
   Loaded after pismo.js, whose pismoFold it uses. */
(function () {
  var d = document;
  var wide = window.matchMedia && matchMedia('(min-width: 900px)').matches;
  var fold = window.pismoFold;

  /* Filters: open on wide screens, closed on phones (the search shows the active ones as chips). */
  var f = d.querySelector('details.filters');
  if (f && !wide) f.open = false;

  /* Apply filters right away when a choice or a year changes. On a page other than search, this opens the search. */
  d.addEventListener('change', function (e) {
    if (!e.target.matches('.filters input[form=sf]')) return;
    var s = d.getElementById('sf'); if (s) s.requestSubmit ? s.requestSubmit() : s.submit();
  });

  /* A table filter in the page (a subject's topics, the teachers): every row is in the page.
     data-f="find": all words in the row's folded data-find; data-f="x" on a select: the value is one of row data-x ("a|b"). */
  var bar = d.querySelector('[data-filter]');
  if (bar) {
    var rows = [].slice.call(d.querySelectorAll('[data-rows] > li'));
    var ctl = [].slice.call(bar.querySelectorAll('[data-f]'));
    var runRows = function () {
      var shown = 0, p = new URLSearchParams();
      ctl.forEach(function (c) { if (c.value.trim()) p.set(c.name, c.value.trim()); });
      rows.forEach(function (r) {
        var ok = ctl.every(function (c) {
          var v = c.value.trim(), have = r.dataset[c.dataset.f] || '';
          if (!v) return true;
          if (c.tagName === 'SELECT') return ('|' + have + '|').indexOf('|' + v + '|') > -1;
          return fold(v).split(/\s+/).every(function (w) { return have.indexOf(w) > -1; });
        });
        r.hidden = !ok;
        if (ok) shown++;
      });
      bar.querySelector('[data-shown]').textContent = shown;
      d.querySelector('[data-none]').hidden = shown > 0;
      history.replaceState(null, '', p.size ? '?' + p : location.pathname);
    };
    var p = new URLSearchParams(location.search);
    ctl.forEach(function (c) {
      c.value = p.get(c.name) || '';
      c.addEventListener(c.tagName === 'SELECT' ? 'change' : 'input', runRows);
    });
    if (p.size) runRows();
  }

  /* Header tabs: mark the section of this page; data-for lists its path prefixes ("/" only the home page itself). */
  var path = location.pathname;
  [].forEach.call(d.querySelectorAll('.tabs a'), function (a) {
    var on = (a.dataset.for || a.getAttribute('href')).split(' ').some(function (p) {
      return p === '/' ? path === '/' : path.indexOf(p) === 0;
    });
    if (on) a.setAttribute('aria-current', 'page');
  });

  /* Theme button: light ↔ dark. Until the first click the system's scheme applies; head.js applies the saved one
     before the first paint. */
  var root = d.documentElement, tb = d.getElementById('tema');
  var THEMES = { light: ['sun', 'svetla'], dark: ['moon', 'tamna'] };
  var theme = function () {
    var t = root.dataset.tema;
    return THEMES[t] ? t : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  };
  var showTheme = function () {
    var v = THEMES[theme()];
    tb.querySelector('use').setAttribute('href', '/static/icons.svg#i-' + v[0]);
    tb.setAttribute('aria-label', 'Tema: ' + v[1]);
  };
  if (tb) {
    tb.addEventListener('click', function () {
      var t = theme() === 'dark' ? 'light' : 'dark';
      root.dataset.tema = t;
      try { localStorage.setItem('tema', t); } catch (e) {}
      showTheme();
    });
    showTheme();
  }

  /* Keys: / search, j/k move between rows, Enter opens. */
  d.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    var links = [].slice.call(d.querySelectorAll('.fr:not([hidden]) .fr__a, .pc:not([hidden]) .pc__a'));
    var i = links.indexOf(d.activeElement);
    if (e.key === '/') { e.preventDefault(); var q = d.getElementById('q'); q.focus(); q.select(); }
    else if ((e.key === 'j' || e.key === 'k') && links.length) {
      e.preventDefault();
      var n = e.key === 'j' ? Math.min(i + 1, links.length - 1) : Math.max(i - 1, 0);
      links[n].focus(); links[n].closest('.fr, .pc').scrollIntoView({ block: 'nearest' });
    }
  });
})();
