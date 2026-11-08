/* Optional enhancements of every page (base.html). Every page works without this script.
   Loaded after pismo.js, whose pismoFold it uses. */
(function () {
  var d = document;
  var wide = window.matchMedia && matchMedia('(min-width: 900px)').matches;

  /* Filters: open on wide screens; on phones close unless a filter is active. */
  var f = d.querySelector('details.filters');
  if (f && !wide && !f.hasAttribute('data-active')) f.open = false;

  /* Subject search inside the filter panel. */
  var box = d.querySelector('[data-subject-search]');
  var list = d.querySelector('[data-subject-list]');
  var hint = d.querySelector('[data-subject-hint]');
  var initSubjects = function () {
    box.hidden = false;
    var inp = box.querySelector('input');
    var opts = [].slice.call(list.querySelectorAll('label'));
    /* Cyrillic and Latin alike, so "meh" finds "Механика". */
    var fold = window.pismoFold;
    /* The checkbox value is the name as posted (the text may be converted by pismo.js already).
       _f is its folded form, _at the index in the name of each folded letter ("љ" folds to two). */
    opts.forEach(function (o) {
      o._t = o.querySelector('input').value; o._n = o.querySelector('.opt__name'); o._f = ''; o._at = [];
      for (var k = 0; k < o._t.length; k++) { var c = fold(o._t[k]); o._f += c; for (var j = 0; j < c.length; j++) o._at.push(k); }
      o._at.push(o._t.length);
    });
    var esc = function (s) { return s.replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); };
    var run = function () {
      var v = fold(inp.value.trim()), shown = 0, all = 0;
      opts.forEach(function (o) {
        var i = v ? o._f.indexOf(v) : 0;
        var a = i > -1 ? o._at[i] : 0, b = i > -1 ? o._at[i + v.length - 1] + 1 : 0;
        var on = o.querySelector('input').checked;
        var ok = !v || i > -1 || on;
        var empty = o.classList.contains('is-empty'); /* no posts for this search (search.js) */
        o.hidden = !ok;
        if (!empty) all++;
        if (ok && !empty) shown++;
        o._n.innerHTML = (v && i > -1) ? esc(o._t.slice(0, a)) + '<mark>' + esc(o._t.slice(a, b)) + '</mark>' + esc(o._t.slice(b)) : esc(o._t);
      });
      if (hint) hint.textContent = v ? shown + ' od ' + all + ' predmeta, esc briše' : '';
    };
    inp.addEventListener('input', run);
    inp.addEventListener('keydown', function (e) { if (e.key === 'Escape') { inp.value = ''; run(); } if (e.key === 'Enter') e.preventDefault(); });
  };
  if (box && list) {
    /* Pages other than search load the subject list once from a shared file (sidebar.html). */
    if (list.dataset.src && !list.children.length) {
      fetch(list.dataset.src).then(function (r) { return r.ok ? r.text() : ''; }).then(function (h) { list.innerHTML = h; initSubjects(); });
    } else initSubjects();
  }

  /* Apply filters right away when a choice changes. On a page other than search, this opens the search. */
  d.addEventListener('change', function (e) {
    if (!e.target.matches('.filters input[type=radio], .filters input[type=checkbox]')) return;
    var s = d.getElementById('sf'); if (s) s.requestSubmit ? s.requestSubmit() : s.submit();
  });

  /* Keys: / search, p subject, j/k move between results, Enter opens. */
  d.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    var links = [].slice.call(d.querySelectorAll('.row .t a'));
    var i = links.indexOf(d.activeElement);
    if (e.key === '/') { e.preventDefault(); var q = d.getElementById('q'); q.focus(); q.select(); }
    else if (e.key === 'p' && box) { e.preventDefault(); if (f) f.open = true; box.querySelector('input').focus(); }
    else if ((e.key === 'j' || e.key === 'k') && links.length) {
      e.preventDefault();
      var n = e.key === 'j' ? Math.min(i + 1, links.length - 1) : Math.max(i - 1, 0);
      links[n].focus(); links[n].closest('.row').scrollIntoView({ block: 'nearest' });
    }
  });
})();
