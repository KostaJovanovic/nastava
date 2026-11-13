/* Optional enhancements of every page (base.html). Every page works without this script.
   Loaded after pismo.js, whose pismoFold it uses. */
(function () {
  var d = document;
  var fold = window.pismoFold;
  var sf = d.getElementById('sf'), q = d.getElementById('q');
  // The side panel's picker and the header search's lists (build.py picker).
  var izbor = window.fetch ? fetch('/izbor.json').then(function (r) { return r.json(); }) : null;
  var el = function (tag, cls, text) {
    var e = d.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  /* The header search, of everything: the matching subjects (by studije), teachers, katedre, researchers and schedule
     entries listed under the bar, the first few of each with a link to the rest on its list page; off the home page,
     the texts' best hits too. Enter searches all the texts (search.js on the home page). A list page filters its own
     list with its own box (below). */
  var list = null, data = null;
  // The types with a list page ("Još N" goes there, with ?q=).
  var ENTER = { nastavnici: '/nastavnici/?', predmeti: '/predmeti/?', istrazivaci: '/nastavnici/istrazivaci/?' };
  if (q && sf) {
    var onHome = location.pathname === '/';
    var studije = [], folded = [];
    var show = function () {
      if (!list) return;
      var v = q.value.trim(), w = fold(v).split(/\s+/).filter(Boolean);
      var has = function (s) { return w.every(function (x) { return s.indexOf(x) > -1; }); };
      list.textContent = '';
      asked++;
      if (!w.length) { list.hidden = true; return; }
      // rows: [subgroup, name, hint, href, decorate(a)]: the first 5 of a type with a list page (3 of the katedre),
      // and a link to the rest.
      var section = function (key, title, rows) {
        var cap = ENTER[key] ? 5 : key === 'katedre' ? 3 : 200, sub = null;
        if (!rows.length) return;
        var g = list.appendChild(el('div', 'cmd__g'));
        g.setAttribute('role', 'group');
        g.setAttribute('aria-label', title);
        g.appendChild(el('p', 'cmd__h', title)).setAttribute('aria-hidden', 'true');
        rows.slice(0, cap).forEach(function (r) {
          if (r[0] && r[0] !== sub) g.appendChild(el('p', 'cmd__s', sub = r[0])).setAttribute('aria-hidden', 'true');
          var a = g.appendChild(el('a', null, r[1]));
          a.href = r[3];
          if (r[2]) a.appendChild(el('small', null, r[2]));
          if (r[4]) r[4](a);
        });
        if (rows.length > cap && ENTER[key]) {
          var m = g.appendChild(el('a', 'cmd__more', 'Još ' + (rows.length - cap) + ' →'));
          m.href = ENTER[key] + 'q=' + encodeURIComponent(v);
        }
      };
      // A katedra's icon (icons.svg) left of the row: a katedra's, and a subject's katedra's (build.py picker ki), else the book.
      var icon = function (id) {
        return id && function (a) {
          var svg = d.createElementNS('http://www.w3.org/2000/svg', 'svg'), use = d.createElementNS('http://www.w3.org/2000/svg', 'use');
          svg.setAttribute('class', 'i cmd__img');
          svg.setAttribute('aria-hidden', 'true');
          use.setAttribute('href', '/static/icons.svg#i-' + id);
          a.className = 'cmd__p';
          a.insertBefore(svg, a.firstChild).appendChild(use);
        };
      };
      var subj = [];
      studije.forEach(function (s) {
        s[1].forEach(function (i) {
          if (has(folded[i])) subj.push([s[0], data.subjects[i][1], '', data.subjects[i][0], icon((data.ki || [])[i] || 'book')]);
        });
      });
      section('predmeti', 'Predmeti', subj);
      // A teacher as on /nastavnici/: the photo (or the initials), the title; one who left under its own subheading,
      // with the cards' grey corner (style.css .pc--gone). The listed first, so those show where there is room.
      section('nastavnici', 'Nastavnici', data.people.filter(function (t) { return has(fold(t[0])); })
        .map(function (t) {
          var gone = t.length > 4;
          return [gone ? 'Više nisu na fakultetu' : '', t[0], t[3], t[1], function (a) {
            var w = t[0].split(' '), img = t[2] ? el('img', 'cmd__img') : el('span', 'cmd__img', w[0][0] + w[w.length - 1][0]);
            if (t[2]) { img.src = t[2]; img.alt = ''; img.loading = 'lazy'; } else img.setAttribute('aria-hidden', 'true');
            a.className = 'cmd__p' + (gone ? ' pc--gone' + (t[4] === null ? ' pc--undated' : '') : '');
            // In px, not % as on the cards: a row is wide and short, a % of it is most of the row.
            if (gone && t[4] !== null) a.style.setProperty('--p', t[4] + 'px');
            a.insertBefore(img, a.firstChild);
          }];
        }));
      // A katedra: its icon, and its teachers' list.
      // Found by its short name's initials too ('omk': Opšte mašinske konstrukcije).
      section('katedre', 'Katedre', (data.katedre || []).filter(function (k) {
        return has(fold(k[0]) + ' ' + fold(k[1]).split(/\s+/).map(function (x) { return x[0]; }).join(''));
      })
        .map(function (k) {
          var n = k[3] % 10 === 1 && k[3] % 100 !== 11 ? ' nastavnik' : ' nastavnika';
          return ['', k[1], k[3] + n, k[4] || '/nastavnici/?katedra=' + k[2], icon(k[2])];
        }));
      // A researcher or demonstrator (build.py OTHER_TEACHERS, aside): their page, with their title.
      section('istrazivaci', 'Istraživači i demonstratori',(data.istrazivaci || []).filter(function (r) { return has(fold(r[0])); })
        .map(function (r) { return ['', r[0], r[2], r[1]]; }));
      section('raspored', 'Raspored', (data.raspored || []).filter(function (r) { return has(fold(r[0] + ' ' + r[1])); })
        .map(function (r) { return ['', r[0], r[1], r[2]]; }));
      // The texts (posts, news): off the home page, their best hits as they come; the home page lists them itself.
      if (!onHome) {
        var box = list.appendChild(el('div', 'cmd__g'));
        var a = list.appendChild(el('a', 'cmd__all', 'Traži „' + v + '“ u postovima i vestima'));
        a.href = '/?q=' + encodeURIComponent(fold(v));
        textHits(box, a, fold(v), asked);
      }
      list.hidden = !list.children.length;
    };
    // The texts' first 5 hits in Pagefind (loaded at the first word), as search.js would find them: the followed
    // subjects only while "Samo moji predmeti" is on. my: the show() that asked; a later one wins.
    var pagefind = null, asked = 0;
    var textHits = function (box, all, query, my) {
      pagefind = pagefind || import('/pagefind/pagefind.js');
      pagefind.then(function (pf) {
        var f = {}, m = window.mojiNow;
        if (m && m.only) f.pid = { any: mine().map(function (s) { return s.href; }) };
        return pf.debouncedSearch(query, { filters: f }, 150);
      }).then(function (r) {
        if (!r || my !== asked) return null;
        return Promise.all(r.results.slice(0, 5).map(function (x) { return x.data(); })).then(function (rows) { return [r.results.length, rows]; });
      }).then(function (got) {
        if (!got || my !== asked || !got[0]) return;
        box.setAttribute('role', 'group');
        box.setAttribute('aria-label', 'Objave i vesti');
        box.appendChild(el('p', 'cmd__h', 'Objave i vesti')).setAttribute('aria-hidden', 'true');
        got[1].forEach(function (x) {
          var a = box.appendChild(el('a', null, x.meta.title));
          a.href = x.url;
          var where = x.meta.predmet || x.meta.smer || x.meta.kategorija, day = (x.meta.datum || '').slice(0, 10).split('-').reverse().join('.');
          a.appendChild(el('small', null, [where, day && day + '.'].filter(Boolean).join(' · ')));
        });
        all.textContent = 'Svi rezultati (' + got[0] + ') →';
      }).catch(function () {});
    };
    // Enter: the texts (the form's own submit); the list under the bar closes.
    sf.addEventListener('submit', function () { if (list) list.hidden = true; });
    if (izbor) izbor.then(function (j) {
      data = j;
      // A subject is found by its acronyms too (build.py acronyms: OOK, ME1).
      folded = j.subjects.map(function (s, i) { return fold(s[1]) + ' ' + j.acr[i]; });
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
      // Arrow keys move between the bar and the list's links; Escape or a click elsewhere closes the list.
      sf.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { list.hidden = true; return; }
        if (list.hidden || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
        var links = [].slice.call(list.querySelectorAll('a')), i = links.indexOf(d.activeElement);
        e.preventDefault();
        i = e.key === 'ArrowDown' ? Math.min(i + 1, links.length - 1) : i - 1;
        (i < 0 ? q : links[i]).focus();
      });
      d.addEventListener('click', function (e) { if (!sf.contains(e.target)) list.hidden = true; });
      // Typed before the lists loaded.
      if (d.activeElement === q) show();
    }).catch(function () {});
  }

  /* The page links: the current page's is marked (the phone's tab bar shows it); a section's pages count as it
     (a teacher's page is under Nastavnici, an archived schedule page under Raspored, a news post under Vesti). */
  var here = location.pathname.replace(/^\/(nastavnik|katedra)\//, '/nastavnici/').replace(/^\/studije\//, '/raspored/')
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

  /* The lecture schedule (/raspored/): a program at a time, picked by its tab (head.js rsPick; raspored.html picks the
     first before the first frame). */
  var rs = d.querySelector('[data-rs]');
  if (rs && rs.querySelector('[data-prog]')) {
    [].forEach.call(rs.querySelectorAll('[data-rs-tab]'), function (t) {
      t.addEventListener('click', function (e) { e.preventDefault(); window.rsPick(t.hash.slice(1), true); });
    });
    // A link to another program on the same page changes only the #.
    window.addEventListener('hashchange', function () { window.rsPick(decodeURIComponent(location.hash.slice(1)), true); });
  }

  /* The word cloud (/statistika/, stats.html): the biggest word in the middle, each next one at the first place on a
     spiral out of it that overlaps none placed before. Laid out again when a word's size changes (the font loads, the
     page turns Cyrillic) or the card's width does. Without this, a centred list (style.css .wc). */
  var wc = d.querySelector('.wc');
  if (wc && window.ResizeObserver) {
    var wcLis = [].slice.call(wc.children), wcRaf;
    var wcS = function (li) { return +li.firstChild.style.getPropertyValue('--s'); };
    wcLis.sort(function (a, b) { return wcS(b) - wcS(a); });
    var wcLay = function () {
      var W = wc.clientWidth, put = [], lo = Infinity, hi = -Infinity;
      wcLis.forEach(function (li) {
        var w = li.offsetWidth + 8, h = li.offsetHeight, t = 0, r = 0, x, y;
        var hits = function (p) { return x < p.x + p.w && p.x < x + w && y < p.y + p.h && p.y < y + h; };
        // An ellipse twice as wide as high: the card is wide. Steps of ~5px along the spiral; r grows 2px a radian.
        for (; r < 2000; t += Math.min(0.3, 5 / (2 * r + 1)), r = 2 * t) {
          x = W / 2 + 2 * r * Math.cos(t) - w / 2;
          y = r * Math.sin(t) - h / 2;
          if (x >= 0 && x + w <= W && !put.some(hits)) break;
        }
        put.push({ x: x, y: y, w: w, h: h });
        lo = Math.min(lo, y); hi = Math.max(hi, y + h);
      });
      wcLis.forEach(function (li, i) { li.style.left = put[i].x + 4 + 'px'; li.style.top = put[i].y - lo + 'px'; });
      wc.style.height = hi - lo + 'px';
    };
    wc.classList.add('wc--cloud');
    var wcRo = new ResizeObserver(function () { cancelAnimationFrame(wcRaf); wcRaf = requestAnimationFrame(wcLay); });
    wcRo.observe(wc);
    wcLis.forEach(function (li) { wcRo.observe(li); });
  }

  /* The side panel's switch "Samo moji predmeti": on, the site shows only the followed subjects (head.js) and
     searches only them (search.js); off ("sve" = '1' in localStorage), all. 'moji' redraws what depends on it;
     registered first, so the others see the new state. */
  var only = d.querySelector('[data-moji-only]');
  // The side panel shows the new state too (head.js showSaved: the count, the switch, the picker's link).
  d.addEventListener('moji', function () {
    if (window.moji) window.mojiNow = window.moji();
    if (window.mojiSort) window.mojiSort();
    window.showSaved();
  });
  d.dispatchEvent(new Event('moji'));
  /* The home page's Studije as the switch flips: the rows that will change (moved by head.js mojiSort, or greyed and
     made one short line by head.js) fade out whole, backgrounds too, while the card takes its new height; unseen, they
     are rearranged (change()) and fade in where they land. Nothing slides past anything, and the card is never shorter
     or taller than what shows in it for long: its bottom moves one way, with the fade out. A flip mid-way starts from
     what is on the screen. Elsewhere, or with reduced motion, change() at once. */
  var studijeAnims = [];
  var fadeStudije = function (change) {
    var card = d.querySelector('#res > .fb--forums'), ol = card && card.querySelector('.fb__rows');
    if (!ol || !ol.built || card.closest('.searching') || matchMedia('(prefers-reduced-motion: reduce)').matches) return change();
    // The card moves for all of it; the rows fade out for its first part and in for the rest, so both end together.
    var all = 400, out = { duration: 150, easing: 'ease-in', fill: 'forwards' }, k = 0;
    // The rows that stay as they are: the followed smerovi already first as built (first in both orders).
    while (k < ol.built.length && (ol.built[k].dataset.pids || '').split(' ').some(window.mojiNow.has)) k++;
    var rows = ol.built.slice(k);
    // From what is on the screen: a flip mid-way starts where the last one got to.
    var from = rows.map(function (r) { return getComputedStyle(r).opacity; }), h0 = card.getBoundingClientRect().height;
    studijeAnims.forEach(function (a) { a.cancel(); });
    // The card's height after the change, now: head.js's style for the new choice (already saved), a layout, the old
    // style back; nothing is painted between.
    var st = d.getElementById('moji-css'), css0 = st.textContent, only0 = d.documentElement.classList.contains('moji-only');
    window.moji();
    var h1 = card.getBoundingClientRect().height;
    st.textContent = css0;
    d.documentElement.classList.toggle('moji-only', only0);
    var move = card.animate({ height: [h0 + 'px', h1 + 'px'] }, { duration: all, easing: 'cubic-bezier(.4, 0, .2, 1)' });
    var outs = rows.map(function (r, i) { return r.animate({ opacity: [from[i], 0] }, out); });
    studijeAnims = outs.concat(move);
    // The change once the fade out has ended (not a timer: it waits for a slow phone's frames too, as the card's move
    // does). A flip mid-way cancels these, and so this.
    Promise.all(outs.map(function (a) { return a.finished; })).then(function () {
      outs.forEach(function (a) { a.cancel(); });
      change();
      // Each row to its own opacity now (a greyed smer's .45, head.js), ending with the move.
      studijeAnims = [move].concat(rows.map(function (r) {
        return r.animate({ opacity: [0, getComputedStyle(r).opacity] }, { duration: all - out.duration, easing: 'cubic-bezier(.2, .8, .2, 1)' });
      }));
    }, function () {});
  };
  if (only) only.addEventListener('change', function () {
    try { localStorage.setItem('sve', only.checked ? '' : '1'); } catch (e) {}
    // A search on view runs again (search.js); elsewhere the page only shows more or fewer rows.
    fadeStudije(function () { d.dispatchEvent(new Event('moji')); });
  });


  /* A table filter in the page (a subject's topics, the teachers, a smer's subjects): every row is in the page.
     data-f="find": all words in the row's folded data-find (the bar's own search box, ?q=); data-f="x" on a select: the
     value is one of row data-x ("a|b"). Enter in the box: data-enter and q= when the bar has it (the texts of a
     subject's posts, of the news), else the one row left, if one is. */
  var bar = d.querySelector('[data-filter]'), runRows = null;
  if (bar) {
    var rows = [].slice.call(d.querySelectorAll('[data-rows] > li:not([data-sep])')), sep = d.querySelector('[data-sep]');
    var ctl = [].slice.call(bar.querySelectorAll('[data-f]'));
    // The subjects' list keeps each subject's search text once (predmeti.html #finds), by the row's id before any '-'.
    var finds = d.getElementById('finds');
    finds = finds ? JSON.parse(finds.textContent) : null;
    var field = function (r, f) {
      var v = r.dataset[f] || '';
      return f === 'find' && finds ? v + ' ' + (finds[r.dataset.id.split('-')[0]] || '') : v;
    };
    var findBox = bar.querySelector('[data-f="find"]');
    if (findBox) findBox.addEventListener('keydown', function (e) {
      var v = findBox.value.trim();
      if (e.key !== 'Enter' || !v) return;
      e.preventDefault();
      if (bar.dataset.enter) { location.href = bar.dataset.enter + 'q=' + encodeURIComponent(fold(v)); return; }
      // The list filtered down to one row (a subject in two plans is two): its page, a subject on the forum (data-pid:
      // its board page, or its book page when it has no topics).
      var one = [].filter.call(d.querySelectorAll('[data-rows] > li:not([hidden]):not([data-sep])'), function (r) { return r.offsetParent; })
        .map(function (r) { return r.dataset.pid || (r.querySelector('a') || {}).href; }).filter(Boolean);
      if (one.length && one.every(function (h) { return h === one[0]; })) location.href = one[0];
    });
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
      // The archive's 'no year' heading back before its first row (the rows were moved to the end past it).
      var u = sep && box.querySelector('.pc--undated');
      if (u) u.parentNode.insertBefore(sep, u);
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
        // No data-n (the subjects): the name is the row's link text.
        var val = function (r) { return r.dataset[key] || (key === 'n' ? r.querySelector('a').textContent : ''); };
        var cmp = s[0] === '-' ? function (a, b) { return b.dataset[key] - a.dataset[key]; }
          : function (a, b) { return val(a).localeCompare(val(b), 'sr'); };
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
          var v = c.value.trim(), have = field(r, c.dataset.f);
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
      // "Samo moji predmeti" counts as a filter too: the followed subjects would be hidden in a folded program.
      var filtering = ctl.some(function (c) { return c.value.trim(); }) || !!(window.mojiNow && window.mojiNow.only);
      // .filtering: a long elective slot shows all its rows (style.css .sg__slot--short).
      if (box) box.classList.toggle('filtering', filtering);
      if (box) [].forEach.call(box.querySelectorAll('.sg, .sg__s, .sg__slot'), function (g) {
        var shownRows = g.querySelectorAll('[data-rows] > li:not([hidden])').length, n = g.querySelector(':scope > summary .sg__n');
        var empty = !shownRows;
        if (n) n.textContent = shownRows;
        g.classList.toggle('is-empty', empty);
        if (filtering && !empty && g.tagName === 'DETAILS') g.open = true;
      });
      var shown = Object.keys(ids).length, n = bar.querySelector('[data-shown]'), none = d.querySelector('[data-none]');
      var gone = left ? left.querySelectorAll('[data-rows] > li:not([hidden])').length : 0;
      if (left) {
        left.querySelector('[data-left-n]').textContent = gone;
        // The departed show under the current teachers only for a text search (the archive page lists them all).
        left.hidden = !gone || !ctl.some(function (c) { return c.tagName !== 'SELECT' && c.value.trim(); });
      }
      if (n) n.textContent = shown;
      // The archive's 'no year' heading: in the page's own order only, while a row under it is on view.
      if (sep) sep.hidden = !!(gsel && gsel.value) || !!(ssel && ssel.value) || !d.querySelector('[data-sep] ~ li:not([hidden])');
      if (none) none.hidden = shown > 0 || (left && !left.hidden);
      // While a filter is set, a list with no row on view goes with its heading (a smer's subjects, its notices, its
      // subjects without posts); the one that says nothing matched stays.
      [].forEach.call(d.querySelectorAll('.fb'), function (f) {
        if (f.querySelector('[data-rows]')) f.hidden = filtering && !f.querySelector('[data-rows] > li:not([hidden])') && !(none && !none.hidden && f.contains(none));
      });
      // String(p), not p.size: Safari before 17 has no size.
      history.replaceState(null, '', String(p) ? '?' + p : location.pathname);
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
    if (String(p)) arrange();
    if (String(p) || (window.mojiNow && window.mojiNow.only)) runRows();
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
    star.addEventListener('click', function () {
      var list = mine(), rest = list.filter(function (s) { return s.href !== star.dataset.star; });
      keepMine(rest.length < list.length ? rest : list.concat([{ href: star.dataset.star, name: star.dataset.name }]));
      star.classList.toggle('star--pop', rest.length === list.length);
    });
    star.addEventListener('animationend', function () { star.classList.remove('star--pop'); });
    // Shown and set before the first frame (predmet.html, head.js showStar); again when the list changes.
    d.addEventListener('moji', window.showStar);
  }

  var mp = d.querySelector('[data-mp]');

  /* The picker, /mojipredmeti/ (mojipredmeti.html; /izbor.json from build.py picker), in two steps.
     1, the subjects: a tab per program, a row of chips per level under it (a master's module, a year), and the year's
     subjects as cards: the required ones, then each elective block. Each tab and chip counts the followed subjects
     under it. Text in its box narrows the subjects shown to those whose name, acronym or teacher matches; with
     nothing picked it searches all of them, and the teachers as cards too. A card follows its subject; a
     teacher's card follows all their subjects (pressed: all, mixed: some).
     2 (#nastavnici), the notifications: their switch, then each followed subject with the teachers who posted in it, as cards with their
     photos; the picked ones are the subject's t (slugs of their pages), whose posts alone notify (ci/push.py). None
     picked ("Svi nastavnici"): every post. A subject no teacher posted in is only named. */
  if (mp && izbor) izbor.then(function (data) {
    var subj = data.subjects, path = [], badges = [];
    var nav = mp.querySelector('[data-mp-nav]'), body = mp.querySelector('[data-mp-body]'), mq = mp.querySelector('[data-mp-q]');
    var tbox = mp.querySelector('[data-mp-teachers]'), at = {}, taught = {};
    data.teachers.forEach(function (t) { t[1].forEach(function (i) { taught[i] = (taught[i] || '') + ' ' + t[0]; }); });
    subj.forEach(function (s, i) { at[s[0]] = i; });
    var posters = function (href) { return at[href] === undefined ? [] : data.posters[at[href]] || []; };
    var slugOf = function (p) { return p[1].split('/')[2]; };
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
      // A row per level down to the groups, whose nodes have no children; shown in a search too, which stays within them.
      var level = data.tree, depth = 0, node = null;
      while (level.length && level[0].c.length) {
        node = row(level, depth++);
        if (!node) break;
        level = node.c;
      }
      // A subject matches by its name, its acronyms or a teacher's name.
      var hit = function (i) { return has(subj[i][1] + ' ' + data.acr[i] + ' ' + (taught[i] || '')); };
      if (w.length && !path.length) {
        // Nothing picked: the teachers too, whose cards follow all their subjects.
        // shortcut: the first 12 teachers and 48 subjects only; a longer word narrows them.
        var ts = data.teachers.filter(function (t) { return has(t[0]); }).slice(0, 12).map(function (t) {
          var n = t[1].length;
          return card(t[1], t[0], n + (n % 10 === 1 && n % 100 !== 11 ? ' predmet' : ' predmeta'));
        });
        var ss = [];
        subj.forEach(function (s, i) { if (ss.length < 48 && has(s[1] + ' ' + data.acr[i])) ss.push(card([i], s[1], where[i])); });
        if (ts.length) group('Nastavnici', ts);
        if (ss.length) group('Predmeti', ss);
      } else if (level.length && level[0].c.length) {
        // A row left unpicked: every subject under it, each once, by name (folded: Edge's 'sr' collation put Avionika before Adaptivne).
        var all = {};
        (function walk(x) { x.s.forEach(function (i) { all[i] = 1; }); x.c.forEach(walk); })({ s: [], c: level });
        var ids = Object.keys(all).filter(function (i) { return hit(+i); });
        if (ids.length) group(w.length ? 'Predmeti' : 'Svi predmeti', ids.sort(function (a, b) { return fold(subj[a][1]).localeCompare(fold(subj[b][1])); })
          .map(function (i) { return card([+i], subj[i][1], where[i]); }));
      } else level.forEach(function (g) {
        var title = g.n || (/godina$/.test(node.n) ? 'Obavezni predmeti' : 'Predmeti'), ids = g.s.filter(hit);
        if (ids.length) group(title, ids.map(function (i) { return card([i], subj[i][1]); }));
      });
      if (w.length && !body.firstChild) body.appendChild(el('p', 'mp__none', path.length ? 'Ovde nema takvog predmeta ni nastavnika.' : 'Nema takvog predmeta ni nastavnika.'));
      sync();
    };
    // Step 2: a section per followed subject that teachers posted in, a card per teacher (posts, most first).
    var renderTeachers = function () {
      var list = mine(), none = [];
      tbox.textContent = '';
      list.forEach(function (m) {
        var ps = posters(m.href);
        if (!ps.length) { none.push(m.name); return; }
        var sec = tbox.appendChild(el('section', 'mp__group')), grid = el('div', 'mp__cards');
        sec.dataset.href = m.href;
        sec.appendChild(el('h3', null, m.name)).appendChild(el('span', null, ''));
        var all = grid.appendChild(card([], 'Svi nastavnici', 'sva obaveštenja predmeta'));
        all.dataset.t = '';
        ps.forEach(function (x) {
          var p = data.people[x[0]], w = p[0].split(' ');
          var few = x[1] % 10 >= 2 && x[1] % 10 <= 4 && (x[1] % 100 < 12 || x[1] % 100 > 14);
          // The title without the katedra (people's "title · katedra"): the subject says where they teach.
          var b = grid.appendChild(card([], p[0], [(p[3] || '').split(' · ')[0], x[1] + (few ? ' objave' : ' objava')].filter(Boolean).join(' · ')));
          var img = p[2] ? el('img', 'mp__ph') : el('span', 'mp__ph', w[0][0] + w[w.length - 1][0]);
          if (p[2]) { img.src = p[2]; img.alt = ''; img.loading = 'lazy'; } else img.setAttribute('aria-hidden', 'true');
          b.classList.add('mp__card--t');
          b.insertBefore(img, b.querySelector('.mp__name'));
          b.dataset.t = slugOf(p);
        });
        sec.appendChild(grid);
      });
      if (none.length) tbox.appendChild(el('p', 'mp__none', 'Nijedan nastavnik još nije pisao u: ' + none.join(', ') + '. Za njih stižu sva obaveštenja.'));
      if (!list.length) tbox.appendChild(el('p', 'mp__none', 'Prvo izaberi predmete.'));
      mp.querySelector('[data-mp-hint]').hidden = !tbox.querySelector('[data-href]');
      sync();
    };
    var sync = function () {
      var o = followed(), list = mine(), n = list.length, by = {};
      list.forEach(function (m) { by[m.href] = m.t || []; });
      [].forEach.call(mp.querySelectorAll('[data-ids]:not([data-t])'), function (b) {
        var ids = b.dataset.ids ? b.dataset.ids.split(',') : [], k = ids.filter(function (i) { return o[subj[i][0]]; }).length;
        b.setAttribute('aria-pressed', ids.length && k === ids.length ? 'true' : k ? 'mixed' : 'false');
      });
      [].forEach.call(tbox.querySelectorAll('[data-href]'), function (sec) {
        var t = by[sec.dataset.href] || [];
        [].forEach.call(sec.querySelectorAll('[data-t]'), function (b) {
          b.setAttribute('aria-pressed', b.dataset.t ? t.indexOf(b.dataset.t) > -1 : !t.length);
        });
        sec.querySelector('h3 span').textContent = t.length ? ' · ' + t.length + (t.length === 1 ? ' nastavnik' : ' nastavnika') : ' · svi';
      });
      badges.forEach(function (x) { x[0].textContent = count(x[1], o) || ''; });
      mp.querySelector('[data-mp-n]').textContent = n || '';
      // The foot: "Dalje" to the notifications once a subject is followed.
      var two = location.hash === '#nastavnici';
      mp.querySelector('[data-mp-sum]').textContent = two ? '' : n ? 'Izabrano: ' + n : 'Klikni predmete koje pratiš.';
      mp.querySelector('[data-mp-reset]').hidden = !n;
      mp.querySelector('[data-mp-back]').hidden = !two;
      mp.querySelector('[data-mp-next]').hidden = two || !n;
      mp.querySelector('[data-mp-done]').hidden = !two && n > 0;
    };
    // A step is the address's hash, so the back button goes from the teachers to the subjects.
    var step = function () {
      var two = location.hash === '#nastavnici';
      mp.querySelector('[data-mp-1]').hidden = two;
      mp.querySelector('[data-mp-2]').hidden = !two;
      [].forEach.call(mp.querySelectorAll('[data-step]'), function (a) {
        if ((a.dataset.step === '2') === two) a.setAttribute('aria-current', 'step'); else a.removeAttribute('aria-current');
      });
      if (two) renderTeachers(); else render();
      window.scrollTo(0, 0);
    };
    mp.addEventListener('click', function (e) {
      var b = e.target.closest('[data-ids]');
      if (!b) return;
      if (b.dataset.t !== undefined) {
        // A teacher's card adds them to the subject's or takes them out; "Svi nastavnici" empties it.
        var href = b.closest('[data-href]').dataset.href, slug = b.dataset.t;
        keepMine(mine().map(function (m) {
          if (m.href !== href) return m;
          var t = slug ? (m.t || []).filter(function (x) { return x !== slug; }) : [];
          if (slug && t.length === (m.t || []).length) t.push(slug);
          return t.length ? { href: m.href, name: m.name, t: t } : { href: m.href, name: m.name };
        }));
      } else {
        var ids = b.dataset.ids.split(','), hrefs = ids.map(function (i) { return subj[i][0]; });
        var list = mine().filter(function (s) { return hrefs.indexOf(s.href) < 0; });
        keepMine(b.getAttribute('aria-pressed') === 'true' ? list
          : list.concat(ids.map(function (i) { return { href: subj[i][0], name: subj[i][1] }; })));
      }
      // keepMine's 'moji' event has run sync(): the card is marked; only a click pops its check (style.css).
      b.classList.toggle('mp__card--pop', b.getAttribute('aria-pressed') !== 'false');
    });
    // Unfollows everything, teachers' picks too, after asking: it cannot be undone. Back to step 1.
    mp.querySelector('[data-mp-reset]').addEventListener('click', function () {
      if (!confirm('Poništiti izbor svih predmeta i nastavnika?')) return;
      keepMine([]);
      if (location.hash) location.hash = ''; else step();
    });
    mq.addEventListener('input', render);
    window.addEventListener('hashchange', step);
    mp.querySelector('[data-mp-foot]').hidden = false;
    step();
    d.addEventListener('moji', sync);
  }).catch(function () {});
  var fillMine = function () {
    // Najnovije objave's rows of the followed subjects (rows.html topic_rows mine), shown in place of its own only while
    // "Samo moji predmeti" is on (head.js, style.css .moji-only).
    var ol = d.querySelector('[data-mine]'), list = mine();
    if (!ol || !(window.mojiNow && window.mojiNow.only)) return;
    var sec = ol.parentNode;
    // A subject with no topics on the board (followed from the plans) links its page in the subject book: no rows.
    Promise.all(list.filter(function (s) { return s.href.indexOf('/predmet/') === 0; }).map(function (s) {
      return fetch(s.href + 'novo.json').then(function (r) { return r.ok ? r.json() : { rows: [] }; })
        .catch(function () { return { rows: [] }; });
    })).then(function (all) {
      // [last post time, row HTML]: the newest across the subjects first. The rows are this site's own build.
      var rows = [].concat.apply([], all.map(function (j) { return j.rows; }));
      rows.sort(function (a, b) { return a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0; });
      ol.innerHTML = rows.slice(0, 10).map(function (r) { return r[1]; }).join('');
      sec.querySelector('.moji__none').hidden = rows.length > 0;
    });
  };
  fillMine();
  // search.js puts the home page back when the search is cleared, as built: without these rows.
  d.addEventListener('pocetna', fillMine);
  d.addEventListener('pocetna', function () { window.mojiSort(); });
  d.addEventListener('moji', fillMine);

  /* Notifications: web push of the followed subjects' new posts. static/sw.js shows them; the Worker (/push) keeps this
     browser's subscription with the subjects' pages, and ci/push.py sends after each deploy. Only a subject with topics
     (/predmet/) gets posts. An iPhone has web push only for the site opened from the home screen. */
  var PUSH_PUBLIC = 'BPumbbNmB0El3blUr_wKj4PWrpCq0b6pSakijI6H3gtrlgxAqz4abQ63IIwe9EEq50gJNhGDay-Mdb28hsUCSqE';
  // The switch is on /mojipredmeti/ (mojipredmeti.html); every page keeps the subscription's subjects up to date (a
  // subject page's star changes them too).
  var pushBox = d.querySelector('[data-push]'), pushMsg = d.querySelector('[data-push-msg]');
  var said = function (text) { pushMsg.textContent = text; pushMsg.hidden = !text; };
  var withPosts = function () {
    return mine().filter(function (s) { return s.href.indexOf('/predmet/') === 0; });
  };
  if (window.PushManager && window.Notification && navigator.serviceWorker) {
    var reg = navigator.serviceWorker.register('/static/sw.js');
    var current = function () { return reg.then(function (r) { return r.pushManager.getSubscription(); }); };
    // What the Worker has, kept here so an unchanged list is not written again (KV has a daily write limit).
    // list: the followed subjects with posts; t, only when some subject has teachers picked: {href: [their slugs]}.
    var save = function (sub, list) {
      var j = sub.toJSON(), o = { endpoint: j.endpoint, keys: j.keys, s: list.map(function (m) { return m.href; }) }, t = {}, was = null;
      list.forEach(function (m) { if (m.t && m.t.length) t[m.href] = m.t; });
      if (Object.keys(t).length) o.t = t;
      var body = JSON.stringify(o);
      try { was = localStorage.getItem('push'); } catch (e) {}
      if (body === was) return Promise.resolve();
      return fetch('/push', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        try { localStorage.setItem('push', body); } catch (e) {}
      });
    };
    // Also a change made just before leaving a page: the next page sends it.
    var resave = function () { return current().then(function (sub) { if (sub) return save(sub, withPosts()); }).catch(function () {}); };
    resave();
    var timer;
    d.addEventListener('moji', function () {
      // Picking subjects is many clicks: one write a few seconds after the last.
      clearTimeout(timer);
      timer = setTimeout(resave, 3000);
    });
    var pushOn = pushBox && pushBox.querySelector('input');
    if (pushOn) current().then(function (sub) {
      pushOn.checked = !!sub && Notification.permission === 'granted';
      pushBox.hidden = false;
    }).catch(function () {});
    if (pushOn) pushOn.addEventListener('change', function () {
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
  /* The footer's first link: the part of the faculty's sites this page copies (base.html data-origin). */
  var orig = d.querySelector('[data-origin]'), ftOrig = d.querySelector('[data-ft-origin]');
  if (orig && ftOrig) { ftOrig.href = orig.href; ftOrig.textContent = orig.hostname.replace(/^www\./, ''); }
  // "Provereno": the build's time (UTC) in the reader's own.
  var built = d.querySelector('.ft time'), bt = built && new Date(built.dateTime);
  if (bt && !isNaN(bt)) {
    var p2 = function (n) { return (n < 10 ? '0' : '') + n; };
    built.textContent = 'u ' + p2(bt.getHours()) + ':' + p2(bt.getMinutes()) + ', ' + p2(bt.getDate()) + '.' + p2(bt.getMonth() + 1) + '.' + bt.getFullYear() + '.';
  }
  /* The credit's wave (as valjdakosta.com's header): each letter a span, its delay one step behind the one before;
     the words stay whole (nowrap), an emoji with its variation selector one letter. The name is there in both scripts
     (base.html), one shown: the steps are counted along the shown one, again when pismo.js switches (html lang), so
     the hump runs on through the name and past it. The hidden one keeps animating (style.css), so a switch shows
     letters already in step. */
  var wave = d.querySelector('[data-wave]');
  if (wave) {
    var waveText = [], walker = d.createTreeWalker(wave, NodeFilter.SHOW_TEXT), tn;
    while ((tn = walker.nextNode())) waveText.push(tn);
    var waveSteps = []; // [letter span or null (a plain space), script: 'cyr', 'lat' or '' (shown in both)]
    waveText.forEach(function (t) {
      var p = t.parentNode, s = p.hasAttribute('data-cyr') ? 'cyr' : p.hasAttribute('data-lat') ? 'lat' : '';
      var frag = d.createDocumentFragment();
      t.data.split(/(\s+)/).forEach(function (word) {
        if (!word) return;
        // A space is a step of the wave too, so the hump doesn't skip between words. In the link it is lifted as well:
        // its underline would be the link's own, flat under the letters' waving ones.
        if (/^\s+$/.test(word)) {
          waveSteps.push([p.closest('a') ? frag.appendChild(el('span', 'wave wave--sp', word)) : null, s]);
          if (!p.closest('a')) frag.appendChild(d.createTextNode(word));
          return;
        }
        var w = frag.appendChild(el('span'));
        w.style.whiteSpace = 'nowrap';
        word.match(/.️?/g).forEach(function (ch) { waveSteps.push([w.appendChild(el('span', 'wave', ch)), s]); });
      });
      p.replaceChild(frag, t);
    });
    var waveSync = function () {
      var hidden = d.documentElement.lang === 'sr-Cyrl' ? 'lat' : 'cyr'; // as style.css hides the name
      var steps = waveSteps.filter(function (x) { return x[1] !== hidden; });
      steps.forEach(function (x, i) { if (x[0]) x[0].style.animationDelay = -((steps.length - 1 - i) * 0.15) + 's'; });
    };
    waveSync();
    new MutationObserver(waveSync).observe(d.documentElement, { attributes: true, attributeFilter: ['lang'] });
  }

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
        + '<p data-leave-say></p>'
        + '<p class="leave__url" data-leave-url data-notx></p><div class="leave__acts">'
        + '<button type="button" class="btn" data-leave-stay>Ostani</button>'
        + '<a class="btn btn--pri" data-leave-go target="_blank" rel="noopener noreferrer">Nastavi</a></div></div>';
      d.body.appendChild(leave);
      // The dialog itself is the target only on its backdrop.
      leave.addEventListener('click', function (e) {
        if (e.target === leave || e.target.closest('[data-leave-stay], [data-leave-go]')) leave.close();
      });
    }
    // A link with data-domain (the footer's drive) says only that name, in masinci.org's words and buttons.
    var named = a.getAttribute('data-domain'), say = leave.querySelector('[data-leave-say]');
    say.innerHTML = named ? 'Ovaj link vodi na <b></b>' : 'Link vodi na <b></b>, sajt van ove arhive. Otvoriće se u novoj kartici.';
    say.querySelector('b').textContent = named || a.hostname;
    leave.querySelector('h2').hidden = leave.querySelector('[data-leave-url]').hidden = !!named;
    leave.querySelector('[data-leave-stay]').textContent = named ? 'Nazad' : 'Ostani';
    leave.querySelector('[data-leave-go]').textContent = named ? 'Potvrdi' : 'Nastavi';
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
  // The button's icon and label (head.js showSaved; sidebar.html set them before the first frame).
  var showTheme = window.showSaved;
  var setTheme = function (t) {
    root.dataset.tema = t;
    d.querySelector('meta[name="theme-color"]').content = t === 'dark' ? '#011321' : '#0076b1';
    try { localStorage.setItem('tema', t); } catch (e) {}
    showTheme();
  };
  var vtNow = null;
  if (tb) {
    /* The switch as a big circle the size of the screen, on a valley's path: dark comes down from the upper left to
       cover it; light shows again as the dark goes on up to the upper right (a view transition; style.css puts the
       dark page on top). Where the browser has no view transitions, or motion is reduced, the theme changes at once. */
    tb.addEventListener('click', function () {
      var t = theme() === 'dark' ? 'light' : 'dark', dark = t === 'dark';
      if (!d.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) return setTheme(t);
      var w = innerWidth, h = innerHeight, r = Math.hypot(w, h) / 2, frames = [];
      // s: 0 → 1 along the way. Its height is a parabola, level at the centre: it comes down into it and goes up out.
      for (var i = 0, s; i <= 24; i++) {
        s = i / 24;
        frames.push({ clipPath: 'circle(' + r + 'px at ' + (dark ? -r + s * (w / 2 + r) : w / 2 + s * (w / 2 + r)) + 'px '
          + (h / 2 - r * (dark ? (1 - s) * (1 - s) : s * s)) + 'px)' });
      }
      // The page's scrollbar is not in the transition's pictures: it keeps the old theme's colours (style.css --sb-*)
      // until the circle's edge crosses it (the screen's right edge, half way down), at that point of the 650 ms.
      var cs = getComputedStyle(root), SB = ['scroll', 'paper', 'head', 'head-line'];
      SB.forEach(function (n) {
        var m = /^light-dark\(\s*([^,]+),\s*(.+)\)$/.exec(cs.getPropertyValue('--' + n).trim());
        if (m) root.style.setProperty('--sb-' + n, m[dark ? 1 : 2]);
      });
      var unpin = function () { if (vtNow === vt) SB.forEach(function (n) { root.style.removeProperty('--sb-' + n); }); };
      var cross = 1, u = 0, cx, cy;
      for (i = 0; i <= 96; i++) {
        s = i / 96;
        cx = dark ? -r + s * (w / 2 + r) : w / 2 + s * (w / 2 + r);
        cy = h / 2 - r * (dark ? (1 - s) * (1 - s) : s * s);
        if ((Math.hypot(w - cx, h / 2 - cy) < r) === dark) { cross = s; break; }
      }
      // The easing below, cubic-bezier(.65, 0, .35, 1): the time at which the way reaches cross.
      while (u < 1 && 3 * (1 - u) * u * u + u * u * u < cross) u += .01;
      var at = 650 * (3 * (1 - u) * (1 - u) * u * .65 + 3 * (1 - u) * u * u * .35 + u * u * u);
      root.dataset.vt = t;
      var vt = vtNow = d.startViewTransition(function () { setTheme(t); }), anim = null;
      vt.ready.then(function () { setTimeout(unpin, at); }, unpin);
      vt.finished.then(unpin, unpin);
      vt.ready.then(function () {
        // fill both: no frame without the clip at either end (that was a flash of the whole dark page).
        anim = root.animate(frames, { duration: 650, easing: 'cubic-bezier(.65, 0, .35, 1)', fill: 'both',
          pseudoElement: dark ? '::view-transition-new(root)' : '::view-transition-old(root)' });
      }, function () {});
      // A second click cuts this one short and sets its own data-vt first: only the latest clears it. The animation
      // goes too: kept (fill both), iOS put its last frame (the whole dark page) on the next switch's picture.
      vt.finished.then(function () {
        if (anim) anim.cancel();
        if (vtNow === vt) delete root.dataset.vt;
      });
    });
  }

  /* Font menu: the Konami code (↑↑↓↓←→←→BA) opens it at the bottom right. While it is open, localStorage 'font' holds
     the font picked (its --sans; '' for the site's own, IBM Plex Sans, the first): head.js sets it before the first
     paint and each page opens the menu again. Closing it (×, or the code again) removes 'font': back to Plex Sans. */
  var KONAMI = 'arrowup,arrowup,arrowdown,arrowdown,arrowleft,arrowright,arrowleft,arrowright,b,a', keys = [], fl = null;
  var FONTS = [
    'Sans',
    ['IBM Plex Sans', '"IBM Plex Sans", system-ui, sans-serif'],
    ['Geist', '"Geist", system-ui, sans-serif'],
    ['Golos Text', '"Golos Text", system-ui, sans-serif'],
    ['Onest', '"Onest", system-ui, sans-serif'],
    ['Manrope', '"Manrope", system-ui, sans-serif'],
    ['Geologica', '"Geologica", system-ui, sans-serif'],
    ['Wix Madefor Text', '"Wix Madefor Text", system-ui, sans-serif'],
    ['Rubik', '"Rubik", system-ui, sans-serif'],
    ['Roboto', '"Roboto Lab", system-ui, sans-serif'],
    ['Inter', '"Inter", system-ui, sans-serif'],
    ['Montserrat', '"Montserrat", system-ui, sans-serif'],
    ['LT Wave Text', '"LT Wave Text", system-ui, sans-serif'],
    ['Mint Spirit No2', '"Mint Spirit No2", system-ui, sans-serif'],
    ['Unbounded', '"Unbounded", system-ui, sans-serif'],
    'IBM',
    ['IBM Plex Mono', '"IBM Plex Mono", ui-monospace, monospace'],
    ['IBM Plex Math', '"IBM Plex Math", Georgia, serif'],
    ['3270', '"3270", ui-monospace, monospace'],
    ['IBM VGA 8x16', '"IBM VGA 8x16", monospace'],
    ['IBM BIOS', '"IBM BIOS", monospace'],
    'Serif',
    ['Literata', '"Literata", Georgia, serif'],
    ['Source Serif 4', '"Source Serif 4", Georgia, serif'],
    ['LT Remark', '"LT Remark", Georgia, serif'],
    // Latin only: Cyrillic in Plex Sans.
    'Latinica, sans',
    ['Satoshi', '"Satoshi", "IBM Plex Sans", system-ui, sans-serif'],
    ['Space Grotesk', '"Space Grotesk", "IBM Plex Sans", system-ui, sans-serif'],
    ['Bricolage Grotesque', '"Bricolage Grotesque", "IBM Plex Sans", system-ui, sans-serif'],
    ['DM Sans', '"DM Sans", "IBM Plex Sans", system-ui, sans-serif'],
    ['Plus Jakarta Sans', '"Plus Jakarta Sans", "IBM Plex Sans", system-ui, sans-serif'],
    ['Figtree', '"Figtree", "IBM Plex Sans", system-ui, sans-serif'],
    ['Outfit', '"Outfit", "IBM Plex Sans", system-ui, sans-serif'],
    ['Instrument Sans', '"Instrument Sans", "IBM Plex Sans", system-ui, sans-serif'],
    ['Barlow', '"Barlow", "IBM Plex Sans", system-ui, sans-serif'],
    ['Human Sans', '"Human Sans", "IBM Plex Sans", system-ui, sans-serif'],
    ['Claris Sans', '"Claris Sans", "IBM Plex Sans", system-ui, sans-serif'],
    'Latinica, serif',
    ['Fraunces', '"Fraunces", "IBM Plex Sans", Georgia, serif'],
    ['Wittgenstein', '"Wittgenstein", "IBM Plex Sans", Georgia, serif'],
    ['Faustina', '"Faustina", "IBM Plex Sans", Georgia, serif'],
    ['Redaction', '"Redaction", "IBM Plex Sans", Georgia, serif'],
    ['Zina', '"Zina", "IBM Plex Sans", Georgia, serif']
  ];
  var saveFont = function (s) {
    try { if (s === null) localStorage.removeItem('font'); else localStorage.setItem('font', s); } catch (e) {}
  };
  var openFonts = function (now) {
    saveFont(now);
    fl = d.createElement('div');
    fl.className = 'fl';
    fl.setAttribute('role', 'group');
    fl.setAttribute('aria-label', 'Font');
    fl.setAttribute('data-notx', '');
    fl.innerHTML = '<div class="fl__h">Font<button type="button" class="fl__x" aria-label="Zatvori">×</button></div>'
      + '<div class="fl__l"></div>';
    var list = fl.lastChild, on = null;
    FONTS.forEach(function (f) {
      if (typeof f === 'string') return list.insertAdjacentHTML('beforeend', '<div class="fl__g">' + f + '</div>');
      var l = d.createElement('label'), r = d.createElement('input'), own = f === FONTS[1];
      r.type = 'radio'; r.name = 'fl'; r.checked = own ? !now : f[1] === now;
      if (r.checked) on = l;
      r.addEventListener('change', function () {
        if (own) root.style.removeProperty('--sans'); else root.style.setProperty('--sans', f[1]);
        saveFont(own ? '' : f[1]);
      });
      l.style.fontFamily = f[1];
      l.append(r, f[0]);
      list.append(l);
    });
    fl.querySelector('.fl__x').addEventListener('click', closeFonts);
    d.body.append(fl);
    // The font picked in view, as the menu was on the page before.
    if (on) list.scrollTop = on.offsetTop - list.offsetTop - list.clientHeight / 2;
  };
  var closeFonts = function () {
    fl.remove();
    fl = null;
    root.style.removeProperty('--sans');
    saveFont(null);
  };
  d.addEventListener('keydown', function (e) {
    keys = keys.concat(e.key.toLowerCase()).slice(-10);
    if (keys.join() !== KONAMI) return;
    keys = [];
    if (fl) closeFonts(); else openFonts('');
  });
  var fontNow = null;
  try { fontNow = localStorage.getItem('font'); } catch (e) {}
  if (fontNow !== null) openFonts(fontNow);

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

  /* Back up the crumbs to where you were: each page's scroll is kept for the tab (sessionStorage) as it is left, and a
     page opened from the crumbs goes back to it. Other links open a page at the top, as usual. 'crumb': the page the
     crumb leads to, so a stale one (a crumb opened in a new tab) does not move another page. */
  var here = location.pathname + location.search;
  addEventListener('pagehide', function () { try { sessionStorage.setItem('y' + here, scrollY); } catch (e) {} });
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('.crumbs a');
    if (a) try { sessionStorage.setItem('crumb', a.pathname + a.search); } catch (e) {}
  });
  var back = function () {
    try {
      var to = sessionStorage.getItem('crumb');
      sessionStorage.removeItem('crumb');
      if (to === here) scrollTo(0, +sessionStorage.getItem('y' + here));
    } catch (e) {}
  };
  // A page prerendered on hover (base.html's speculation rules) sees the tab's sessionStorage only once shown.
  if (d.prerendering) d.addEventListener('prerenderingchange', back, { once: true }); else back();
  // Nor does it go to its #fragment once shown (a topic opened at its newest post, rows.html topic_row): there it goes.
  if (d.prerendering) d.addEventListener('prerenderingchange', function () {
    var t = location.hash && d.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (t) t.scrollIntoView();
  }, { once: true });

  /* Visitor counter: every page tells the Worker (/visit, each IP once in three days); only /statistika/ shows the
     total. A prerendered page counts once shown. */
  var visit = function () {
    if (!window.fetch) return;
    fetch('/visit', { method: 'POST' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (v) {
      var li = d.getElementById('posete');
      if (!li || !v) return;
      li.firstChild.textContent = v.n.toLocaleString('de-DE'); // 23.692, as build.py's n filter
      li.hidden = false;
    }).catch(function () {});
  };
  if (d.prerendering) d.addEventListener('prerenderingchange', visit, { once: true }); else visit();
})();
