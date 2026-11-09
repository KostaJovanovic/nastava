/* Optional enhancements of every page (base.html). Every page works without this script.
   Loaded after pismo.js, whose pismoFold it uses. */
(function () {
  var d = document;
  var fold = window.pismoFold;
  var sf = d.getElementById('sf'), q = d.getElementById('q');
  // The page's context for the header search (see below); null on a page without one.
  var scope = q && sf && d.querySelector('[data-scope]');
  // The side panel's picker and the header search's lists (build.py picker).
  var izbor = window.fetch ? fetch('/izbor.json').then(function (r) { return r.json(); }) : null;
  var el = function (tag, cls, text) {
    var e = d.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  /* The header search's scope: the select after the text (base.html #qk, the form's kind), what the bar searches.
     '' (Sve): the matching subjects (by studije), teachers and schedule entries listed under the bar, Enter searches
     all the texts; a text's kind (posts, news): Enter searches those (search.js); nastavnici, predmeti: the matching
     ones under the bar, Enter opens their list page.
     A page with [data-scope] (its label; data-ph, the placeholder) starts in it: a list page's own list
     ([data-filter], below) is filtered by the bar; a label that is no option (a subject's topics, a smer's subjects)
     is an option of its own. data-enter: where Enter goes in it, with q= appended. The home page starts in the URL's
     kind, else in the scope last picked on it. sf.data-u: the scope, for search.js. */
  var qk = d.getElementById('qk'), u = '', pageU = null, list = null, data = null, findOn = null, setScope = null;
  var ENTER = { nastavnici: '/nastavnici/?', predmeti: '/predmeti/?' };
  if (qk) {
    var attr = window.pismoAttr || function (el, a, v) { return v === undefined ? el.getAttribute(a) : el.setAttribute(a, v); };
    var PH = { '': 'Pretraži sve…', obavestenje: 'Pretraži objave…', vest: 'Pretraži vesti…', dokument: 'Pretraži dokumente…',
      nastavnici: 'Ime nastavnika…', predmeti: 'Naziv predmeta…' };
    // A scope whose Enter searches the texts (search.js): every one but the lists and a page's own.
    var texts = function (v) { return !ENTER[v] && v !== 'ovde'; };
    var onHome = location.pathname === '/', saved = null;
    if (scope) {
      var mine0 = [].filter.call(qk.options, function (o) { return fold(o.text) === fold(scope.dataset.scope); })[0];
      if (!mine0) qk.add(mine0 = new Option(scope.dataset.scope, 'ovde'), 0);
      pageU = mine0.value;
      PH[pageU] = scope.dataset.ph;
    }
    try { saved = localStorage.getItem('trazi'); } catch (e) {}
    var kind = new URLSearchParams(location.search).get('kind') || '';
    // A search in the URL is of the texts, which a teachers' or subjects' scope would hide.
    if (onHome && location.search) u = kind in PH && texts(kind) ? kind : '';
    else if (onHome && saved !== null && saved in PH) u = saved;
    else if (pageU) u = pageU;
    else if (saved === null) u = 'predmeti'; // A new visitor (nothing picked yet) starts in the subjects.
    var studije = [], folded = [];
    setScope = function (v) {
      u = qk.value = sf.dataset.u = v;
      attr(q, 'placeholder', PH[v]);
      if (findOn) findOn(v === pageU);
    };
    var show = function () {
      if (!list) return;
      var v = q.value.trim(), w = fold(v).split(/\s+/).filter(Boolean);
      var has = function (s) { return w.every(function (x) { return s.indexOf(x) > -1; }); };
      list.textContent = '';
      asked++;
      // The page's own list filtered by the bar (q.dataset.f, below): nothing under the bar.
      if (!w.length || q.dataset.f || u === 'ovde') { list.hidden = true; return; }
      if (!u || ENTER[u]) {
        // rows: [subgroup, name, hint, href]. In Sve, the first 5 of a type with a list page, and a link to the rest.
        var section = function (key, title, rows) {
          var cap = !u && ENTER[key] ? 5 : 200, sub = null;
          if (!rows.length || (u && u !== key)) return;
          var g = list.appendChild(el('div', 'cmd__g'));
          g.setAttribute('role', 'group');
          g.setAttribute('aria-label', title);
          if (!u) g.appendChild(el('p', 'cmd__h', title)).setAttribute('aria-hidden', 'true');
          rows.slice(0, cap).forEach(function (r) {
            if (r[0] && r[0] !== sub) g.appendChild(el('p', 'cmd__s', sub = r[0])).setAttribute('aria-hidden', 'true');
            var a = g.appendChild(el('a', null, r[1]));
            a.href = r[3];
            if (r[2]) a.appendChild(el('small', null, r[2]));
          });
          if (rows.length > cap) {
            var m = g.appendChild(el('a', 'cmd__more', 'Još ' + (rows.length - cap) + ' →'));
            m.href = ENTER[key] + 'q=' + encodeURIComponent(v);
            m.dataset.u = key;
          }
        };
        var subj = [];
        studije.forEach(function (s) {
          s[1].forEach(function (i) { if (has(folded[i])) subj.push([s[0], data.subjects[i][1], '', data.subjects[i][0]]); });
        });
        section('predmeti', 'Predmeti', subj);
        section('nastavnici', 'Nastavnici', data.people.filter(function (t) { return has(fold(t[0])); })
          .map(function (t) { return ['', t[0], '', t[1]]; }));
        section('raspored', 'Raspored', (data.raspored || []).filter(function (r) { return has(fold(r[0] + ' ' + r[1])); })
          .map(function (r) { return ['', r[0], r[1], r[2]]; }));
      }
      // The texts (posts, news): off the home page, their best hits as they come; the home page lists them itself.
      if (texts(u) && !onHome) {
        var box = list.appendChild(el('div', 'cmd__g'));
        var a = list.appendChild(el('a', 'cmd__all', 'Traži „' + v + '“ u ' + (TEXTS[u] || 'postovima i vestima')));
        a.href = '/?q=' + encodeURIComponent(fold(v)) + (u ? '&kind=' + u : '');
        textHits(box, a, fold(v), asked);
      }
      list.hidden = !list.children.length;
    };
    // The texts' first 5 hits in Pagefind (loaded at the first word), as search.js would find them: the followed
    // subjects only while "Samo moji predmeti" is on, except in the news. my: the show() that asked; a later one wins.
    var TEXTS = { obavestenje: 'objavama', vest: 'vestima', dokument: 'dokumentima' }, pagefind = null, asked = 0;
    var textHits = function (box, all, query, my) {
      pagefind = pagefind || import('/pagefind/pagefind.js');
      pagefind.then(function (pf) {
        var f = u ? { vrsta: { any: [u] } } : {}, m = window.mojiNow;
        if (m && m.only && u !== 'vest') f.pid = { any: mine().map(function (s) { return s.href; }) };
        return pf.debouncedSearch(query, { filters: f }, 150);
      }).then(function (r) {
        if (!r || my !== asked) return null;
        return Promise.all(r.results.slice(0, 5).map(function (x) { return x.data(); })).then(function (rows) { return [r.results.length, rows]; });
      }).then(function (got) {
        if (!got || my !== asked || !got[0]) return;
        box.setAttribute('role', 'group');
        box.setAttribute('aria-label', u ? qk.options[qk.selectedIndex].text : 'Objave i vesti');
        if (!u) box.appendChild(el('p', 'cmd__h', 'Objave i vesti')).setAttribute('aria-hidden', 'true');
        got[1].forEach(function (x) {
          var a = box.appendChild(el('a', null, x.meta.title));
          a.href = x.url;
          var where = x.meta.predmet || x.meta.smer || x.meta.kategorija, day = (x.meta.datum || '').slice(0, 10).split('-').reverse().join('.');
          a.appendChild(el('small', null, [where, day && day + '.'].filter(Boolean).join(' · ')));
        });
        all.textContent = 'Svi rezultati (' + got[0] + ') →';
      }).catch(function () {});
    };
    qk.addEventListener('change', function () {
      setScope(qk.value);
      if (onHome) try { localStorage.setItem('trazi', u); } catch (e) {}
      // The page's list, the list under the bar and search.js redraw for the text in the new scope.
      q.dispatchEvent(new Event('input'));
      q.focus();
    });
    sf.addEventListener('submit', function (e) {
      var v = q.value.trim(), hits = list && !list.hidden ? list.querySelectorAll('a:not(.cmd__more)') : [];
      if (list) list.hidden = true;
      if (texts(u)) return;
      e.preventDefault();
      if (hits.length === 1) location.href = hits[0].href;
      else if (v && u === pageU && scope.dataset.enter) location.href = scope.dataset.enter + 'q=' + encodeURIComponent(fold(v));
      else if (v && !q.dataset.f && ENTER[u]) location.href = ENTER[u] + 'q=' + encodeURIComponent(v);
    });
    if (izbor) izbor.then(function (j) {
      data = j;
      folded = j.subjects.map(function (s) { return fold(s[1]); });
      // Each program's subjects once, by name (folded: Edge's 'sr' collation put Avionika before Adaptivne).
      studije = j.tree.map(function (n) {
        var o = {};
        (function walk(x) { x.s.forEach(function (i) { o[i] = 1; }); x.c.forEach(walk); })(n);
        return [n.n, Object.keys(o).sort(function (a, b) { return folded[a].localeCompare(folded[b]); })];
      });
      list = el('div', 'cmd__list');
      list.id = 'q-list';
      list.hidden = true;
      sf.appendChild(list);
      q.setAttribute('aria-controls', 'q-list');
      q.addEventListener('input', show);
      q.addEventListener('focus', show);
      // A "još N" link narrows the bar to its type.
      list.addEventListener('click', function (e) {
        var m = e.target.closest('.cmd__more');
        if (!m) return;
        e.preventDefault();
        qk.value = m.dataset.u;
        qk.dispatchEvent(new Event('change'));
      });
      // Arrow keys move between the bar and the list's links; Escape or a click elsewhere closes the list.
      sf.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { list.hidden = true; return; }
        if (list.hidden || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') || e.target === qk) return;
        var links = [].slice.call(list.querySelectorAll('a')), i = links.indexOf(d.activeElement);
        e.preventDefault();
        i = e.key === 'ArrowDown' ? Math.min(i + 1, links.length - 1) : i - 1;
        (i < 0 ? q : links[i]).focus();
      });
      d.addEventListener('click', function (e) { if (!sf.contains(e.target)) list.hidden = true; });
      // Typed before the lists loaded.
      if (d.activeElement === q) show();
    }).catch(function () {});
    setScope(u);
    qk.hidden = false;
  }

  /* The page links: the current page's is marked (the phone's tab bar shows it); a section's pages count as it
     (a teacher's page is under Nastavnici, an archived schedule page under Raspored, a news post under Vesti). */
  var here = location.pathname.replace(/^\/nastavnik\//, '/nastavnici/').replace(/^\/studije\//, '/raspored/')
    .replace(/^\/vest\//, '/vesti/');
  [].forEach.call(d.querySelectorAll('.snav a'), function (a) {
    if (a.pathname === '/' ? here === '/' : here.indexOf(a.pathname) === 0) a.setAttribute('aria-current', 'page');
  });

  /* The logo on a phone, where the header has no room for the word: the first tap shows "nastava" over the rest of
     the bar for a few seconds, a tap while it shows goes home (style.css .brand.is-open). */
  var brand = d.querySelector('.brand'), brandT;
  if (brand && window.matchMedia) {
    brand.addEventListener('click', function (e) {
      if (!matchMedia('(max-width: 759px)').matches || brand.classList.contains('is-open')) return;
      e.preventDefault();
      brand.classList.add('is-open');
      clearTimeout(brandT);
      brandT = setTimeout(function () { brand.classList.remove('is-open'); }, 3000);
    });
  }

  /* The lecture schedule (/raspored/): a program at a time, picked by its tab; the choice is kept for the next visit
     and in the URL (#program). Without this, the tabs are links to the programs one under the other. */
  var rs = d.querySelector('[data-rs]'), progs = rs ? [].slice.call(rs.querySelectorAll('[data-prog]')) : [];
  if (progs.length) {
    var tabs = [].slice.call(rs.querySelectorAll('[data-rs-tab]'));
    var pick = function (key, keep) {
      if (!progs.some(function (p) { return p.id === key; })) key = progs[0].id;
      progs.forEach(function (p) { p.hidden = p.id !== key; });
      tabs.forEach(function (t) { t.setAttribute('aria-current', t.hash === '#' + key); });
      if (!keep) return;
      try { localStorage.setItem('raspored', key); } catch (e) {}
      history.replaceState(null, '', '#' + key);
    };
    tabs.forEach(function (t) {
      t.addEventListener('click', function (e) { e.preventDefault(); pick(t.hash.slice(1), true); });
    });
    var saved = null;
    try { saved = localStorage.getItem('raspored'); } catch (e) {}
    rs.classList.add('rs--tabs');
    pick(decodeURIComponent(location.hash.slice(1)) || saved, false);
    // A link to another program on the same page changes only the #.
    window.addEventListener('hashchange', function () { pick(decodeURIComponent(location.hash.slice(1)), true); });
  }

  /* The side panel's switch "Samo moji predmeti": on, the site shows only the followed subjects (head.js) and
     searches only them (search.js); off ("sve" = '1' in localStorage), all. 'moji' redraws what depends on it;
     registered first, so the others see the new state. */
  var only = d.querySelector('[data-moji-only]');
  d.addEventListener('moji', function () {
    if (window.moji) window.mojiNow = window.moji();
    var all = false;
    try { all = localStorage.getItem('sve') === '1'; } catch (e) {}
    if (only) only.checked = !all;
  });
  d.dispatchEvent(new Event('moji'));
  if (only) only.addEventListener('change', function () {
    try { localStorage.setItem('sve', only.checked ? '' : '1'); } catch (e) {}
    // A search on view runs again (search.js); elsewhere the page only shows more or fewer rows.
    d.dispatchEvent(new Event('moji'));
  });


  /* A table filter in the page (a subject's topics, the teachers, a smer's subjects): every row is in the page.
     data-f="find": all words in the row's folded data-find; data-f="x" on a select: the value is one of row data-x ("a|b").
     With data-scope on it, the header search is its text box (?q=). */
  var bar = d.querySelector('[data-filter]'), runRows = null;
  if (bar) {
    var rows = [].slice.call(d.querySelectorAll('[data-rows] > li'));
    var ctl = [].slice.call(bar.querySelectorAll('[data-f]'));
    if (bar === scope) { q.dataset.f = 'find'; ctl.unshift(q); }
    /* Grouping and order (the teachers, the subjects): [data-group] groups by a row's data-<value> ('-': one group),
       '' is the page's own grouping; [data-sort] orders each group by data-<value>, '-x' by the number x, highest first.
       The rows are moved, not copied (pismo.js keeps each text's original). A row with the data-id of an earlier one
       (a subject in two plans) is only in the page's own grouping. */
    var box = d.querySelector('[data-groups]'), gsel = bar.querySelector('[data-group]'), ssel = bar.querySelector('[data-sort]');
    // Grouped and ordered: the rows in [data-groups] only (the teachers who left keep their own list).
    var own = box ? [].slice.call(box.children) : [], made = null;
    var home = rows.filter(function (r) { return !box || box.contains(r); }).map(function (r) { return [r, r.parentNode]; });
    var left = d.querySelector('[data-left]');
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
        // A named group folds (open at first); one without a name ('-') is a plain list.
        Object.keys(groups).sort(function (a, b) { return !a - !b || label(g, a).localeCompare(label(g, b), 'sr'); }).forEach(function (v) {
          var sec = d.createElement(g === '-' ? 'section' : 'details'), ol = d.createElement('ol');
          sec.className = 'sg';
          if (g !== '-') {
            var h = d.createElement('summary');
            h.className = 'sg__h';
            h.textContent = label(g, v);
            h.appendChild(d.createElement('span')).className = 'sg__n';
            sec.appendChild(h);
            sec.open = true;
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
        // A subject not followed while only the followed show (head.js hides it too).
        var m = window.mojiNow;
        if (m && m.only && r.dataset.pid !== undefined && !m.has(r.dataset.pid)) ok = false;
        r.hidden = !ok;
        // Counted once per subject, among the rows on view.
        if (ok && (!made || made.contains(r)) && (!left || !left.contains(r))) ids[r.dataset.id || i] = 1;
      });
      // A group, semester or elective slot with no row left is hidden; while a filter is set, a folded group with
      // rows opens, so no result is hidden inside one.
      var filtering = ctl.some(function (c) { return c.value.trim(); });
      if (box) [].forEach.call(box.querySelectorAll('.sg, .sg__s, .sg__slot'), function (g) {
        var shownRows = g.querySelectorAll('[data-rows] > li:not([hidden])').length, n = g.querySelector(':scope > summary .sg__n');
        var empty = !shownRows;
        if (n) n.textContent = shownRows;
        g.classList.toggle('is-empty', empty);
        if (filtering && !empty && g.tagName === 'DETAILS') g.open = true;
      });
      var shown = Object.keys(ids).length, n = bar.querySelector('[data-shown]'), none = d.querySelector('[data-none]');
      var gone = left ? left.querySelectorAll('[data-rows] > li:not([hidden])').length : 0;
      if (left) left.querySelector('[data-left-n]').textContent = gone;
      if (n) n.textContent = shown;
      if (none) none.hidden = shown + gone > 0;
      history.replaceState(null, '', p.size ? '?' + p : location.pathname);
    };
    // The header search's scope: the page's own (its text filters the list) or another (the list shows all).
    if (bar === scope) findOn = function (on) {
      var i = ctl.indexOf(q);
      if (on === (i > -1)) return;
      if (on) { q.dataset.f = 'find'; ctl.unshift(q); } else { ctl.splice(i, 1); delete q.dataset.f; }
      runRows();
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
    if (p.size) arrange();
    if (p.size || (window.mojiNow && window.mojiNow.only)) runRows();
    d.addEventListener('moji', runRows);
  }

  /* My subjects: the subjects this browser follows, [{href, name}] in localStorage. A subject's page has the star;
     the home page shows their newest topics, merged from each subject's novo.json (build.py, rows as the home page's).
     shortcut: a followed subject whose URL changes (a rename) shows no rows until it is followed again. */
  var mine = function () { try { return JSON.parse(localStorage.getItem('moji')) || []; } catch (e) { return []; } };
  // 'moji': the list changed (the star, the side panel's picker); each view of it redraws, search.js too.
  var keepMine = function (list) {
    try { localStorage.setItem('moji', JSON.stringify(list)); } catch (e) {}
    d.dispatchEvent(new Event('moji'));
  };
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
    });
    star.hidden = false;
    showStar();
    d.addEventListener('moji', showStar);
  }


  /* "Moji predmeti": the side panel lists the followed subjects, and its button opens a dialog to pick them
     (sidebar.html; /izbor.json from build.py picker). The dialog has a tab per program, a row of chips per level under
     it (a master's module, a year), and the year's subjects as cards: the required ones, then each elective block.
     Each tab and chip counts the followed subjects under it. Text in its box shows the matching teachers and subjects
     instead. A card follows its subject; a teacher's card follows all their subjects (pressed: all, mixed: some). */
  var iz = d.querySelector('[data-izbor]'), mp = d.querySelector('[data-mp]');
  if (iz && mp && mp.showModal && izbor) izbor.then(function (data) {
    var subj = data.subjects, path = [], badges = [];
    var nav = mp.querySelector('[data-mp-nav]'), body = mp.querySelector('[data-mp-body]'), mq = mp.querySelector('[data-mp-q]');
    var followed = function () { var o = {}; mine().forEach(function (s) { o[s.href] = 1; }); return o; };
    // The followed subjects under a node, each once (a subject can be in several of its groups).
    var count = function (node, o) {
      var seen = {};
      (function walk(x) {
        x.s.forEach(function (i) { if (o[subj[i][0]]) seen[i] = 1; });
        x.c.forEach(walk);
      })(node);
      return Object.keys(seen).length;
    };
    // A search hit's place, under its name: the subject's first place in the plans.
    var where = {};
    (function walk(nodes, names) {
      nodes.forEach(function (n) {
        var p = n.n ? names.concat([n.n]) : names;
        n.s.forEach(function (i) { where[i] = where[i] || p.join(' › '); });
        walk(n.c, p);
      });
    })(data.tree, []);
    var card = function (ids, name, hint) {
      var b = el('button', 'mp__card');
      // A plan's subject with no topics on the board yet: it can be followed, it is shown muted.
      if (ids.length === 1 && subj[ids[0]][2] === 0) {
        b.classList.add('mp__card--none');
        hint = (hint ? hint + ' · ' : '') + 'nema objava na forumu';
      }
      b.type = 'button';
      b.dataset.ids = ids.join(',');
      b.appendChild(el('span', 'mp__check')).setAttribute('aria-hidden', 'true');
      var t = b.appendChild(el('span', 'mp__name', name));
      if (hint) t.appendChild(el('small', null, hint));
      return b;
    };
    var group = function (title, list) {
      var sec = el('section', 'mp__group'), grid = el('div', 'mp__cards');
      sec.appendChild(el('h3', null, title)).appendChild(el('span', null, ' · ' + list.length));
      list.forEach(function (c) { grid.appendChild(c); });
      sec.appendChild(grid);
      body.appendChild(sec);
    };
    // One row of choices: the programs as tabs (the level small, above the program), the rest as chips.
    // Nothing is picked at first; a pick filters the cards, and pressing it again undoes it (phones then show only it).
    var row = function (level, depth) {
      var r = el('div', depth ? 'mp__chips' : 'mp__tabs'), on = path[depth] < level.length;
      level.forEach(function (n, i) {
        var b = el('button', 'mp__tab'), parts = depth ? [n.n] : n.n.split(' — ');
        b.type = 'button';
        b.setAttribute('aria-pressed', on && i === path[depth]);
        if (parts[1]) b.appendChild(el('small', null, parts[0]));
        b.appendChild(el('span', null, parts[1] || parts[0]));
        badges.push([b.appendChild(el('i', 'mp__badge')), n]);
        b.addEventListener('click', function () {
          var was = path[depth];
          path.length = depth;
          if (i !== was) path[depth] = i;
          render();
        });
        r.appendChild(b);
      });
      nav.appendChild(r);
      return on ? level[path[depth]] : null;
    };
    var render = function () {
      var w = fold(mq.value.trim()).split(/\s+/).filter(Boolean);
      var has = function (s) { s = fold(s); return w.every(function (x) { return s.indexOf(x) > -1; }); };
      nav.textContent = '';
      body.textContent = '';
      badges = [];
      nav.hidden = !!w.length;
      if (w.length) {
        // shortcut: the first 12 teachers and 48 subjects only; a longer word narrows them.
        var ts = data.teachers.filter(function (t) { return has(t[0]); }).slice(0, 12).map(function (t) {
          var n = t[1].length;
          return card(t[1], t[0], n + (n % 10 === 1 && n % 100 !== 11 ? ' predmet' : ' predmeta'));
        });
        var ss = [];
        subj.forEach(function (s, i) { if (ss.length < 48 && has(s[1])) ss.push(card([i], s[1], where[i])); });
        if (ts.length) group('Nastavnici', ts);
        if (ss.length) group('Predmeti', ss);
        if (!ts.length && !ss.length) body.appendChild(el('p', 'mp__none', 'Nema takvog predmeta ni nastavnika.'));
      } else {
        // A row per level down to the groups, whose nodes have no children.
        var level = data.tree, depth = 0, node = null;
        while (level.length && level[0].c.length) {
          node = row(level, depth++);
          if (!node) break;
          level = node.c;
        }
        // A row left unpicked: every subject under it, each once, by name (folded: Edge's 'sr' collation put Avionika before Adaptivne).
        if (level.length && level[0].c.length) {
          var all = {};
          (function walk(x) { x.s.forEach(function (i) { all[i] = 1; }); x.c.forEach(walk); })({ s: [], c: level });
          group('Svi predmeti', Object.keys(all).sort(function (a, b) { return fold(subj[a][1]).localeCompare(fold(subj[b][1])); })
            .map(function (i) { return card([+i], subj[i][1], where[i]); }));
        } else level.forEach(function (g) {
          var title = g.n || (/godina$/.test(node.n) ? 'Obavezni predmeti' : 'Predmeti');
          group(title, g.s.map(function (i) { return card([i], subj[i][1]); }));
        });
      }
      sync();
    };
    var sync = function () {
      var o = followed(), n = mine().length;
      [].forEach.call(mp.querySelectorAll('[data-ids]'), function (b) {
        var ids = b.dataset.ids.split(','), k = ids.filter(function (i) { return o[subj[i][0]]; }).length;
        b.setAttribute('aria-pressed', k === ids.length ? 'true' : k ? 'mixed' : 'false');
      });
      badges.forEach(function (x) { x[0].textContent = count(x[1], o) || ''; });
      mp.querySelector('[data-mp-n]').textContent = n || '';
      iz.querySelector('[data-moji-n]').textContent = n || '';
      iz.querySelector('[data-moji-scope]').hidden = !n;
      // The followed subjects are not listed here: the button says that some are, and opens them.
      var open = iz.querySelector('[data-moji-open]');
      open.classList.toggle('is-set', n > 0);
      open.querySelector('span').textContent = n ? 'Izmeni predmete' : 'Izaberi predmete';
    };
    mp.addEventListener('click', function (e) {
      var b = e.target.closest('[data-ids]');
      // The dialog itself is the target only on its backdrop: its parts cover all of it.
      if (!b) { if (e.target === mp || e.target.closest('[data-mp-close]')) mp.close(); return; }
      var ids = b.dataset.ids.split(','), hrefs = ids.map(function (i) { return subj[i][0]; });
      var list = mine().filter(function (s) { return hrefs.indexOf(s.href) < 0; });
      keepMine(b.getAttribute('aria-pressed') === 'true' ? list
        : list.concat(ids.map(function (i) { return { href: subj[i][0], name: subj[i][1] }; })));
    });
    mq.addEventListener('input', render);
    iz.querySelector('[data-moji-open]').addEventListener('click', function () {
      render();
      mp.showModal();
    });
    iz.hidden = false;
    sync();
    d.addEventListener('moji', sync);
  }).catch(function () {});
  var fillMine = function () {
    var sec = d.getElementById('moji'), list = mine();
    if (!sec) return;
    sec.hidden = !list.length;
    // A subject with no topics on the board (followed from the plans) links its page in the subject book: no rows.
    Promise.all(list.filter(function (s) { return s.href.indexOf('/predmet/') === 0; }).map(function (s) {
      return fetch(s.href + 'novo.json').then(function (r) { return r.ok ? r.json() : { rows: [] }; })
        .catch(function () { return { rows: [] }; });
    })).then(function (all) {
      // [last post time, row HTML]: the newest across the subjects first. The rows are this site's own build.
      var rows = [].concat.apply([], all.map(function (j) { return j.rows; }));
      rows.sort(function (a, b) { return a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0; });
      sec.querySelector('ol').innerHTML = rows.slice(0, 10).map(function (r) { return r[1]; }).join('');
      sec.querySelector('.moji__none').hidden = rows.length > 0;
    });
  };
  fillMine();
  // search.js puts the home page back when the search is cleared, without these rows.
  d.addEventListener('pocetna', fillMine);
  d.addEventListener('moji', fillMine);

  /* Notifications: web push of the followed subjects' new posts. static/sw.js shows them; the Worker (/push) keeps this
     browser's subscription with the subjects' pages, and ci/push.py sends after each deploy. Only a subject with topics
     (/predmet/) gets posts. An iPhone has web push only for the site opened from the home screen. */
  var PUSH_PUBLIC = 'BPumbbNmB0El3blUr_wKj4PWrpCq0b6pSakijI6H3gtrlgxAqz4abQ63IIwe9EEq50gJNhGDay-Mdb28hsUCSqE';
  var pushBox = d.querySelector('[data-push]'), pushMsg = d.querySelector('[data-push-msg]');
  var said = function (text) { pushMsg.textContent = text; pushMsg.hidden = !text; };
  var withPosts = function () {
    return mine().map(function (s) { return s.href; }).filter(function (h) { return h.indexOf('/predmet/') === 0; });
  };
  if (pushBox && window.PushManager && window.Notification && navigator.serviceWorker) {
    var reg = navigator.serviceWorker.register('/static/sw.js'), pushOn = pushBox.querySelector('input');
    var current = function () { return reg.then(function (r) { return r.pushManager.getSubscription(); }); };
    // What the Worker has, kept here so an unchanged list is not written again (KV has a daily write limit).
    var save = function (sub, s) {
      var j = sub.toJSON(), body = JSON.stringify({ endpoint: j.endpoint, keys: j.keys, s: s }), was = null;
      try { was = localStorage.getItem('push'); } catch (e) {}
      if (body === was) return Promise.resolve();
      return fetch('/push', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        try { localStorage.setItem('push', body); } catch (e) {}
      });
    };
    // Also a change made just before leaving a page: the next page sends it.
    var resave = function () { return current().then(function (sub) { if (sub) return save(sub, withPosts()); }).catch(function () {}); };
    current().then(function (sub) {
      pushOn.checked = !!sub && Notification.permission === 'granted';
      pushBox.hidden = false;
      resave();
    }).catch(function () {});
    var timer;
    d.addEventListener('moji', function () {
      // Picking subjects is many clicks: one write a few seconds after the last.
      clearTimeout(timer);
      timer = setTimeout(resave, 3000);
    });
    pushOn.addEventListener('change', function () {
      var on = pushOn.checked;
      said('');
      (on ? Notification.requestPermission().then(function (p) {
        if (p !== 'granted') throw new Error('dozvola');
        var key = Uint8Array.from(atob(PUSH_PUBLIC.replace(/-/g, '+').replace(/_/g, '/')), function (c) { return c.charCodeAt(0); });
        return reg.then(function (r) { return r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }); });
      }).then(function (sub) { return save(sub, withPosts()); }).then(function () {
        said('Stižu kad arhiva preuzme nove objave sa foruma. Sajt čuva samo adresu obaveštenja ovog pregledača i spisak predmeta.');
      }) : current().then(function (sub) {
        if (sub) return save(sub, []).then(function () { return sub.unsubscribe(); });
      })).catch(function (e) {
        pushOn.checked = !on;
        said(e.message === 'dozvola' ? 'Pregledač ne dozvoljava obaveštenja ovom sajtu (podešavanja sajta).' : 'Nije uspelo, pokušaj ponovo.');
        // Subscribed in the browser but not kept by the Worker: undone, so the switch shows the truth next time.
        if (on) current().then(function (sub) { if (sub) sub.unsubscribe(); }).catch(function () {});
      });
    });
  } else if (pushMsg && navigator.standalone === false) {
    said('Obaveštenja na iPhone-u: Deli → Dodaj na početni ekran, pa otvori sajt odatle.');
  }

  /* The followed subjects' feeds as one OPML file, which a feed reader imports. Made on the click, from the list now. */
  var opml = d.querySelector('[data-opml]');
  if (opml) opml.addEventListener('click', function () {
    var x = function (s) { return s.replace(/[&<>"]/g, function (c) { return '&#' + c.charCodeAt(0) + ';'; }); };
    var rows = mine().filter(function (s) { return s.href.indexOf('/predmet/') === 0; }).map(function (s) {
      var page = location.origin + s.href;
      return '<outline type="rss" text="' + x(s.name) + '" xmlUrl="' + x(page + 'feed.xml') + '" htmlUrl="' + x(page) + '"/>';
    });
    if (opml.href.indexOf('blob:') === 0) URL.revokeObjectURL(opml.href);
    opml.href = URL.createObjectURL(new Blob(['<?xml version="1.0" encoding="utf-8"?>\n<opml version="2.0"><head><title>Moji predmeti'
      + ' · arhiva nastave</title></head><body>' + rows.join('') + '</body></opml>\n'], { type: 'text/x-opml' }));
  });

  /* Links: a PDF opens in a new tab; a link off this site (the board, the faculty's site) first says so in a dialog,
     and opens in a new tab. A click with a modifier key (a new tab or window asked for) goes on as the browser does. */
  var leave = null;
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    if (!/^https?:$/.test(a.protocol) || a.hasAttribute('data-leave-go')) return;
    var out = a.host !== location.host;
    if (!out && !/\.pdf$/i.test(a.pathname)) return;
    e.preventDefault();
    if (!out) { window.open(a.href, '_blank', 'noopener'); return; }
    if (!leave) {
      leave = d.createElement('dialog');
      leave.className = 'leave';
      leave.setAttribute('aria-labelledby', 'leave-h');
      leave.innerHTML = '<div class="leave__in"><h2 id="leave-h">Napuštate arhivu</h2>'
        + '<p>Link vodi na <b data-leave-host></b>, sajt van ove arhive. Otvoriće se u novoj kartici.</p>'
        + '<p class="leave__url" data-leave-url data-notx></p><div class="leave__acts">'
        + '<button type="button" class="btn" data-leave-stay>Ostani</button>'
        + '<a class="btn btn--pri" data-leave-go target="_blank" rel="noopener noreferrer">Nastavi</a></div></div>';
      d.body.appendChild(leave);
      // The dialog itself is the target only on its backdrop.
      leave.addEventListener('click', function (e) {
        if (e.target === leave || e.target.closest('[data-leave-stay], [data-leave-go]')) leave.close();
      });
    }
    leave.querySelector('[data-leave-host]').textContent = a.hostname;
    leave.querySelector('[data-leave-url]').textContent = a.href;
    leave.querySelector('[data-leave-go]').href = a.href;
    leave.showModal();
    leave.querySelector('[data-leave-go]').focus();
  });

  /* A post's link in a topic: the click goes to it as a link does, and copies its full address. */
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-copy]');
    if (!a || !navigator.clipboard) return;
    navigator.clipboard.writeText(a.href).then(function () {
      a.textContent = 'kopirano';
      setTimeout(function () { a.textContent = 'link'; }, 1500);
    }, function () {});
  });

  /* Theme button: light ↔ dark. Light until the first click; head.js applies the saved one before the first paint. */
  var root = d.documentElement, tb = d.getElementById('tema');
  var THEMES = { light: ['sun', 'svetla'], dark: ['moon', 'tamna'] };
  var theme = function () { return THEMES[root.dataset.tema] ? root.dataset.tema : 'light'; };
  var showTheme = function () {
    var v = THEMES[theme()];
    tb.querySelector('use').setAttribute('href', '/static/icons.svg#i-' + v[0]);
    tb.setAttribute('aria-label', 'Tema: ' + v[1]);
  };
  if (tb) {
    tb.addEventListener('click', function () {
      var t = theme() === 'dark' ? 'light' : 'dark';
      root.dataset.tema = t;
      d.querySelector('meta[name="theme-color"]').content = t === 'dark' ? '#011321' : '#0076b1';
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
