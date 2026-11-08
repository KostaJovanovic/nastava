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
    /* Grouping and order (the teachers, the subjects): [data-group] groups by a row's data-<value> ('-': one group),
       '' is the page's own grouping; [data-sort] orders each group by data-<value>, '-x' by the number x, highest first.
       The rows are moved, not copied (pismo.js keeps each text's original). A row with the data-id of an earlier one
       (a subject in two plans) is only in the page's own grouping. */
    var box = d.querySelector('[data-groups]'), gsel = bar.querySelector('[data-group]'), ssel = bar.querySelector('[data-sort]');
    var own = box ? [].slice.call(box.children) : [], home = rows.map(function (r) { return [r, r.parentNode]; }), made = null;
    // A group's heading: the row's value is a Latin slug (it goes in the URL), so the name is the filter option's
    // data-label, in full ('Катедра за бродоградњу'; without the prefix it reads in the wrong case).
    var label = function (g, v) {
      var o = v && bar.querySelector('[data-f="' + g + '"] option[value="' + v + '"]');
      v = o ? o.dataset.label : v;
      return v ? v[0].toUpperCase() + v.slice(1) : 'Bez podatka';
    };
    var arrange = function () {
      var g = gsel ? gsel.value : '', s = ssel ? ssel.value : '';
      home.forEach(function (h) { h[1].appendChild(h[0]); });
      if (made) { made.remove(); made = null; }
      own.forEach(function (c) { c.hidden = !!g; });
      if (g) {
        var seen = {}, groups = {};
        home.forEach(function (h) {
          var id = h[0].dataset.id, v = g === '-' ? '' : h[0].dataset[g] || '';
          if (seen[id]) return;
          seen[id] = 1;
          (groups[v] = groups[v] || []).push(h[0]);
        });
        made = d.createElement('div');
        made.className = 'groups';
        // The groups by name, the rows without a value last.
        Object.keys(groups).sort(function (a, b) { return !a - !b || label(g, a).localeCompare(label(g, b), 'sr'); }).forEach(function (v) {
          var sec = d.createElement('section'), ol = d.createElement('ol');
          sec.className = 'sg';
          if (g !== '-') {
            var h = d.createElement('h2');
            h.className = 'sg__h';
            h.textContent = label(g, v);
            sec.appendChild(h);
          }
          ol.className = home[0][1].className;
          ol.setAttribute('data-rows', '');
          groups[v].forEach(function (r) { ol.appendChild(r); });
          sec.appendChild(ol);
          made.appendChild(sec);
        });
        box.appendChild(made);
      }
      if (s) {
        var key = s.replace('-', '');
        var cmp = s[0] === '-' ? function (a, b) { return b.dataset[key] - a.dataset[key]; }
          : function (a, b) { return a.dataset[key].localeCompare(b.dataset[key], 'sr'); };
        [].forEach.call((made || box).querySelectorAll('[data-rows]'), function (ol) {
          [].slice.call(ol.children).sort(cmp).forEach(function (r) { ol.appendChild(r); });
        });
      }
    };
    var runRows = function () {
      var p = new URLSearchParams(), ids = {};
      ctl.concat([gsel, ssel]).forEach(function (c) { if (c && c.value.trim()) p.set(c.name, c.value.trim()); });
      rows.forEach(function (r, i) {
        var ok = ctl.every(function (c) {
          var v = c.value.trim(), have = r.dataset[c.dataset.f] || '';
          if (!v) return true;
          if (c.tagName === 'SELECT') return ('|' + have + '|').indexOf('|' + v + '|') > -1;
          return fold(v).split(/\s+/).every(function (w) { return have.indexOf(w) > -1; });
        });
        r.hidden = !ok;
        // Counted once per subject, among the rows on view.
        if (ok && (!made || made.contains(r))) ids[r.dataset.id || i] = 1;
      });
      // A group, semester or elective slot with no row left is hidden.
      if (box) [].forEach.call(box.querySelectorAll('.sg, .sg__s, .sg__slot'), function (g) {
        g.classList.toggle('is-empty', !g.querySelector('[data-rows] > li:not([hidden])'));
      });
      var shown = Object.keys(ids).length;
      bar.querySelector('[data-shown]').textContent = shown;
      d.querySelector('[data-none]').hidden = shown > 0;
      history.replaceState(null, '', p.size ? '?' + p : location.pathname);
    };
    var p = new URLSearchParams(location.search);
    ctl.forEach(function (c) {
      c.value = p.get(c.name) || '';
      c.addEventListener(c.tagName === 'SELECT' ? 'change' : 'input', runRows);
    });
    [gsel, ssel].forEach(function (c) {
      if (!c) return;
      c.value = p.get(c.name) || '';
      if (c.selectedIndex < 0) c.selectedIndex = 0;
      c.addEventListener('change', function () { arrange(); runRows(); });
    });
    var ar = bar.querySelector('[data-arrange]');
    if (ar) ar.hidden = false;
    if (p.size) { arrange(); runRows(); }
  }

  /* My subjects: the subjects this browser follows, [{href, name}] in localStorage. A subject's page has the star;
     the home page shows their newest topics, merged from each subject's novo.json (build.py, rows as the home page's).
     shortcut: a followed subject whose URL changes (a rename) shows no rows until it is followed again. */
  var mine = function () { try { return JSON.parse(localStorage.getItem('moji')) || []; } catch (e) { return []; } };
  var keepMine = function (list) { try { localStorage.setItem('moji', JSON.stringify(list)); } catch (e) {} };
  var star = d.querySelector('[data-star]');
  if (star) {
    var showStar = function () {
      var on = mine().some(function (s) { return s.href === star.dataset.star; });
      star.setAttribute('aria-pressed', on);
      star.querySelector('use').setAttribute('href', '/static/icons.svg#i-star' + (on ? '-on' : ''));
      star.querySelector('span').textContent = on ? 'Pratiš' : 'Prati';
    };
    star.addEventListener('click', function () {
      var list = mine(), rest = list.filter(function (s) { return s.href !== star.dataset.star; });
      keepMine(rest.length < list.length ? rest : list.concat([{ href: star.dataset.star, name: star.dataset.name }]));
      showStar();
    });
    star.hidden = false;
    showStar();
  }
  var fillMine = function () {
    var sec = d.getElementById('moji'), list = mine();
    if (!sec) return;
    sec.hidden = !list.length;
    var names = sec.querySelector('.moji__s');
    names.textContent = '';
    list.forEach(function (s) {
      var chip = d.createElement('span'), a = d.createElement('a'), x = d.createElement('button');
      chip.className = 'chip';
      a.href = s.href;
      a.textContent = s.name;
      x.type = 'button';
      x.setAttribute('aria-label', 'Ne prati: ' + s.name);
      x.innerHTML = '<svg class="i" aria-hidden="true"><use href="/static/icons.svg#i-x"></use></svg>';
      x.addEventListener('click', function () {
        keepMine(mine().filter(function (m) { return m.href !== s.href; }));
        fillMine();
      });
      chip.appendChild(a);
      chip.appendChild(x);
      names.appendChild(chip);
    });
    Promise.all(list.map(function (s) {
      return fetch(s.href + 'novo.json').then(function (r) { return r.ok ? r.json() : { rows: [] }; })
        .catch(function () { return { rows: [] }; });
    })).then(function (all) {
      // [last post time, row HTML]: the newest across the subjects first. The rows are this site's own build.
      var rows = [].concat.apply([], all.map(function (j) { return j.rows; }));
      rows.sort(function (a, b) { return a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0; });
      sec.querySelector('ol').innerHTML = rows.slice(0, 10).map(function (r) { return r[1]; }).join('');
    });
  };
  fillMine();
  // search.js puts the home page back when the search is cleared, without these rows.
  d.addEventListener('pocetna', fillMine);

  /* A post's link in a topic: the click goes to it as a link does, and copies its full address. */
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-copy]');
    if (!a || !navigator.clipboard) return;
    navigator.clipboard.writeText(a.href).then(function () {
      a.textContent = 'kopirano';
      setTimeout(function () { a.textContent = 'link'; }, 1500);
    }, function () {});
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
    var links = [].slice.call(d.querySelectorAll('.fr:not([hidden]) .fr__a, .pc:not([hidden]) .pc__a, .sr:not([hidden]) .sr__a'));
    var i = links.indexOf(d.activeElement);
    if (e.key === '/') { e.preventDefault(); var q = d.getElementById('q'); q.focus(); q.select(); }
    else if ((e.key === 'j' || e.key === 'k') && links.length) {
      e.preventDefault();
      var n = e.key === 'j' ? Math.min(i + 1, links.length - 1) : Math.max(i - 1, 0);
      links[n].focus(); links[n].closest('.fr, .pc, .sr').scrollIntoView({ block: 'nearest' });
    }
  });
})();
