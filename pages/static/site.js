/* Optional enhancements of every page (base.html). Every page works without this script.
   Loaded after pismo.js, whose pismoFold it uses. */
(function () {
  var d = document;
  var fold = window.pismoFold;
  var sf = d.getElementById('sf'), q = d.getElementById('q');
  // The page's context for the header search (see below); null on a page without one, or once it is left.
  var scope = q && sf && d.querySelector('[data-scope]'), leaveScope = null;
  // The side panel's picker and the header search on a teacher's page (build.py picker).
  var izbor = window.fetch ? fetch('/izbor.json').then(function (r) { return r.json(); }) : null;

  /* The page links: the current page's is marked (the phone's tab bar shows it); a section's pages count as it
     (a teacher's page is under Nastavnici, an archived schedule page under Raspored). */
  var here = location.pathname.replace(/^\/nastavnik\//, '/nastavnici/').replace(/^\/studije\//, '/raspored/');
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

  /* Apply filters right away when a choice changes. On a page other than search, this opens the search
     of the whole archive: the header's text was for the page's list, so it goes. */
  d.addEventListener('change', function (e) {
    if (!e.target.matches('.filters input[form=sf]') || !sf) return;
    if (scope) { leaveScope(); q.value = ''; }
    sf.requestSubmit ? sf.requestSubmit() : sf.submit();
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
        r.hidden = !ok;
        // Counted once per subject, among the rows on view.
        if (ok && (!made || made.contains(r))) ids[r.dataset.id || i] = 1;
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
      if (n) n.textContent = shown;
      if (none) none.hidden = shown > 0;
      history.replaceState(null, '', p.size ? '?' + p : location.pathname);
    };
    // The header search left for the whole archive: the list shows all again.
    var dropFind = function () {
      var i = ctl.indexOf(q);
      if (i < 0) return;
      ctl.splice(i, 1);
      delete q.dataset.f;
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
    if (p.size) { arrange(); runRows(); }
  }

  /* The header search in the page's context: [data-scope] names it and has the bar's placeholder (data-ph). On a
     list page ([data-filter], above) the bar filters the list; data-people lists matching teachers under the bar;
     data-enter is where Enter goes, with q= appended. A chip after the text names the context: its ×, or Backspace
     in an empty bar, leaves it for the search of the whole archive. */
  if (scope) {
    var attr = window.pismoAttr || function (el, a, v) { return v === undefined ? el.getAttribute(a) : el.setAttribute(a, v); };
    var ph = attr(q, 'placeholder'), chip = d.createElement('button'), list = null;
    chip.type = 'button';
    chip.className = 'cmd__scope';
    chip.title = 'Pretraži celu arhivu';
    chip.setAttribute('aria-label', scope.dataset.scope + ': ukloni, pretraži celu arhivu');
    chip.innerHTML = '<span></span><svg class="i" aria-hidden="true"><use href="/static/icons.svg#i-x"></use></svg>';
    chip.firstChild.textContent = scope.dataset.scope;
    q.after(chip);
    sf.classList.add('is-scoped');
    attr(q, 'placeholder', scope.dataset.ph);
    leaveScope = function () {
      scope = null;
      chip.remove();
      sf.classList.remove('is-scoped');
      if (list) list.hidden = true;
      attr(q, 'placeholder', ph);
      if (dropFind) dropFind();
    };
    chip.addEventListener('click', function () { leaveScope(); q.focus(); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'Backspace' && !q.value && scope) leaveScope();
    });
    sf.addEventListener('submit', function (e) {
      if (!scope) return;
      e.preventDefault();
      var a = list && !list.hidden && list.querySelector('a'), v = q.value.trim();
      if (a) location.href = a.href;
      else if (scope.dataset.enter && v) location.href = scope.dataset.enter + 'q=' + encodeURIComponent(fold(v));
    });
    if ('people' in scope.dataset && izbor) izbor.then(function (data) {
      list = d.createElement('ul');
      list.className = 'cmd__list';
      list.id = 'q-list';
      list.hidden = true;
      sf.appendChild(list);
      q.setAttribute('aria-controls', 'q-list');
      var show = function () {
        var w = fold(q.value.trim()).split(/\s+/).filter(Boolean);
        list.textContent = '';
        if (scope && w.length) data.people.filter(function (t) {
          var n = fold(t[0]);
          return w.every(function (x) { return n.indexOf(x) > -1; });
        }).slice(0, 8).forEach(function (t) {
          var li = d.createElement('li'), a = d.createElement('a');
          a.href = t[1];
          a.textContent = t[0];
          li.appendChild(a);
          list.appendChild(li);
        });
        list.hidden = !list.children.length;
      };
      q.addEventListener('input', show);
      q.addEventListener('focus', show);
      // Arrow keys move between the bar and the names; Escape or a click elsewhere closes the list.
      sf.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { list.hidden = true; return; }
        if (list.hidden || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
        var links = [].slice.call(list.querySelectorAll('a')), i = links.indexOf(d.activeElement);
        e.preventDefault();
        i = e.key === 'ArrowDown' ? Math.min(i + 1, links.length - 1) : i - 1;
        (i < 0 ? q : links[i]).focus();
      });
      d.addEventListener('click', function (e) { if (!sf.contains(e.target)) list.hidden = true; });
      // Typed before the list loaded.
      if (d.activeElement === q) show();
    }).catch(function () {});
  }

  /* My subjects: the subjects this browser follows, [{href, name}] in localStorage. A subject's page has the star;
     the home page shows their newest topics, merged from each subject's novo.json (build.py, rows as the home page's).
     shortcut: a followed subject whose URL changes (a rename) shows no rows until it is followed again. */
  var mine = function () { try { return JSON.parse(localStorage.getItem('moji')) || []; } catch (e) { return []; } };
  // 'moji': the list changed (the star, the side panel's picker, a chip); each view of it redraws, search.js too.
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

  /* The followed subjects as chips, each a link with its × (the home page's "Moji predmeti", the side panel). */
  var chipsOf = function (box) {
    box.textContent = '';
    mine().forEach(function (s) {
      var chip = d.createElement('span'), a = d.createElement('a'), x = d.createElement('button');
      chip.className = 'chip';
      a.href = s.href;
      a.textContent = s.name;
      x.type = 'button';
      x.setAttribute('aria-label', 'Ne prati: ' + s.name);
      x.innerHTML = '<svg class="i" aria-hidden="true"><use href="/static/icons.svg#i-x"></use></svg>';
      x.addEventListener('click', function () {
        keepMine(mine().filter(function (m) { return m.href !== s.href; }));
      });
      chip.appendChild(a);
      chip.appendChild(x);
      box.appendChild(chip);
    });
  };

  /* "Moji predmeti": the side panel lists the followed subjects, and its button opens a dialog to pick them
     (sidebar.html; /izbor.json from build.py picker). The dialog has a tab per program, a row of chips per level under
     it (a master's module, a year), and the year's subjects as cards: the required ones, then each elective block.
     Each tab and chip counts the followed subjects under it. Text in its box shows the matching teachers and subjects
     instead. A card follows its subject; a teacher's card follows all their subjects (pressed: all, mixed: some). */
  var iz = d.querySelector('[data-izbor]'), mp = d.querySelector('[data-mp]');
  if (iz && mp && mp.showModal && izbor) izbor.then(function (data) {
    var subj = data.subjects, path = [], badges = [];
    var nav = mp.querySelector('[data-mp-nav]'), body = mp.querySelector('[data-mp-body]'), mq = mp.querySelector('[data-mp-q]');
    var el = function (tag, cls, text) {
      var e = d.createElement(tag);
      if (cls) e.className = cls;
      if (text != null) e.textContent = text;
      return e;
    };
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
        hint = (hint ? hint + ' · ' : '') + 'nema tema na forumu';
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
    // Nothing is picked at first; once one is, the row shows only it, and pressing it again brings the others back.
    var row = function (level, depth) {
      var r = el('div', depth ? 'mp__chips' : 'mp__tabs'), on = path[depth] < level.length;
      level.forEach(function (n, i) {
        if (on && i !== path[depth]) return;
        var b = el('button', 'mp__tab'), parts = depth ? [n.n] : n.n.split(' — ');
        b.type = 'button';
        b.setAttribute('aria-pressed', on);
        if (parts[1]) b.appendChild(el('small', null, parts[0]));
        b.appendChild(el('span', null, parts[1] || parts[0]));
        badges.push([b.appendChild(el('i', 'mp__badge')), n]);
        b.addEventListener('click', function () {
          path.length = depth;
          if (!on) path[depth] = i;
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
          if (!node) return sync();
          level = node.c;
        }
        level.forEach(function (g) {
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
      chipsOf(iz.querySelector('[data-moji-list]'));
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
    chipsOf(sec.querySelector('.moji__s'));
    // A subject with no topics on the board (followed from the plans) links its page in the subject book: no rows.
    Promise.all(list.filter(function (s) { return s.href.indexOf('/predmet/') === 0; }).map(function (s) {
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
  d.addEventListener('moji', fillMine);

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
