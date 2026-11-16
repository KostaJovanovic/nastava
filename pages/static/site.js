/* Optional enhancements of every page (base.html). Every page works without this script.
   Loaded after pismo.js, whose pismoFold it uses. */
(function () {
  var d = document;
  var fold = window.pismoFold;
  var sf = d.getElementById('sf'), q = d.getElementById('q');
  // The scrollbar's strip beside the footer in its colours (style.css --gut), while the page does not scroll.
  var ft = d.querySelector('.ft'), de = d.documentElement;
  if (ft && window.ResizeObserver) {
    var gut = function () { de.style.setProperty('--ft-h', de.scrollHeight > innerHeight ? '0px' : Math.floor(ft.getBoundingClientRect().height) + 'px'); };
    var gutRo = new ResizeObserver(gut);
    gutRo.observe(ft);
    gutRo.observe(d.body);
  }
  // The window's scrollbar width (0 where bars float, a phone's), for Firefox's right paddings (style.css --sbw).
  var sbProbe = d.createElement('div');
  sbProbe.style.cssText = 'position:absolute;top:-99px;width:50px;height:50px;overflow:scroll';
  d.body.appendChild(sbProbe);
  de.style.setProperty('--sbw-m', (sbProbe.offsetWidth - sbProbe.clientWidth) + 'px');
  sbProbe.remove();
  // The side panel's picker and the header search's lists (build.py picker).
  var izbor = window.fetch ? fetch('/izbor.json').then(function (r) { return r.json(); }) : null;
  var el = function (tag, cls, text) {
    var e = d.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  /* The header search, of everything: the matching subjects (by studije), teachers, katedre, researchers, schedule
     entries and Linkovi's links listed under the bar, the first few of each with a link to the rest on its list page; off the home page,
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
      var v = q.value.trim();
      // The matches scroll inside (scroll), so the list's rounded corners clip the scrollbar; "all results" stays under them.
      list.textContent = '';
      var scroll = list.appendChild(el('div', 'cmd__scroll'));
      asked++;
      if (!fold(v).trim()) { examples(scroll); list.hidden = !scroll.children.length; return; }
      matches(scroll, v);
      // The texts (posts, news): off the home page, their best hits as they come; the home page lists them itself.
      if (!onHome) {
        var box = scroll.appendChild(el('div', 'cmd__g'));
        var a = list.appendChild(el('a', 'cmd__all', 'Traži „' + v + '“ u postovima i vestima'));
        a.href = '/?q=' + encodeURIComponent(fold(v));
        textHits(box, a, fold(v), asked);
      }
      list.hidden = !scroll.children.length;
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
    // A teacher as on /nastavnici/: the photo (or the initials), the title (hint: in its place); one who left under
    // its own subheading, with the cards' grey corner (style.css .pc--gone).
    var person = function (t, hint) {
      var gone = t.length > 4;
      return [gone ? 'Više nisu na fakultetu' : '', t[0], hint || t[3], t[1], function (a) {
        var img = t[2] ? el('img', 'cmd__img') : el('span', 'cmd__img');
        if (t[2]) { img.src = t[2]; img.alt = ''; img.loading = 'lazy'; }
        else { img.setAttribute('aria-hidden', 'true'); img.innerHTML = '<svg class="nophoto"><use href="/static/icons.svg#i-nophoto"/></svg>'; }
        a.className = 'cmd__p' + (gone ? ' pc--gone' + (t[4] === null ? ' pc--undated' : '') : '');
        // In px, not % as on the cards: a row is wide and short, a % of it is most of the row.
        if (gone && t[4] !== null) a.style.setProperty('--p', t[4] + 'px');
        a.insertBefore(img, a.firstChild);
      }];
    };
    // The empty bar: what it finds, as three examples picked anew each time: a word of the posts, a subject's acronym
    // with a number (ME1), a teacher still at the faculty. A click searches it, as Enter would.
    var examples = function (scroll) {
      if (!data) return;
      var pick = function (a) { return a[Math.floor(Math.random() * a.length)]; };
      // A subject with an acronym with a number: that acronym, the subject's katedra's icon.
      var si = pick(data.acr.map(function (a, i) { return /\d/.test(a) ? i : -1; }).filter(function (i) { return i > -1; }));
      var acr = si == null ? '' : data.acr[si].split(' ').filter(function (a) { return /\d/.test(a); })[0];
      var who = pick(data.people.filter(function (t) { return t.length <= 4; })) || [];
      var g = scroll.appendChild(el('div', 'cmd__g'));
      g.setAttribute('role', 'group');
      g.setAttribute('aria-label', 'Primeri');
      g.appendChild(el('p', 'cmd__h', 'Na primer')).setAttribute('aria-hidden', 'true');
      var word = pick(['Rezultati', 'Kolokvijum', 'Ispitni rok', 'Konsultacije', 'Predavanja', 'Uvid u radove', 'Upis', 'Usmeni', 'Domaći zadatak', 'Prijava ispita']);
      // The word in quotes, to show an exact search (search.js readState): "Upis" finds upis, not upisa.
      // [text, hint, decorate(a)]: each with its icon as in the matches (a teacher's photo).
      [['"' + word + '"', (/ /.test(word) ? 'tačno ovaj izraz' : 'tačno ova reč') + ' u postovima i vestima', icon('msgs')],
        [acr.toUpperCase(), 'skraćenica predmeta', icon((data.ki || [])[si] || 'book')], [who[0], 'nastavnik', who[0] && person(who)[4]]].forEach(function (x) {
        if (!x[0]) return;
        var a = g.appendChild(el('a', null, x[0]));
        a.href = '/?q=' + encodeURIComponent(fold(x[0]));
        a.appendChild(el('small', null, x[1]));
        if (x[2]) x[2](a);
        a.addEventListener('click', function (e) {
          e.preventDefault();
          q.value = a.firstChild.nodeType === 3 ? a.firstChild.textContent : a.childNodes[1].textContent; // as shown: Latin or Cyrillic (pismo.js)
          list.hidden = true;
          if (sf.requestSubmit) sf.requestSubmit(); else location.href = a.href;
        });
      });
    };
    // The matches of v but the texts, by type, into scroll: the list under the bar, and the home page's results
    // after Enter (search.js, window.masinciMatches).
    // onPage: the home page's results (not the list under the bar): also who teaches the subjects found.
    var matches = function (scroll, v, onPage) {
      var w = fold(v).split(/\s+/).filter(Boolean);
      var has = function (s) { return w.every(function (x) { return s.indexOf(x) > -1; }); };
      // rows: [subgroup, name, hint, href, decorate(a)]: the first 5 of a type with a list page (3 of the katedre),
      // and a link to the rest.
      var section = function (key, title, rows) {
        var cap = ENTER[key] ? 5 : key === 'katedre' ? 3 : key === 'linkovi' ? 6 : 200, sub = null;
        if (!rows.length) return;
        var g = scroll.appendChild(el('div', 'cmd__g'));
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
      var subj = [], found = {};
      studije.forEach(function (s) {
        s[1].forEach(function (i) {
          if (!has(folded[i])) return;
          subj.push([s[0], data.subjects[i][1], '', data.subjects[i][0], icon((data.ki || [])[i] || 'book')]);
          found[i] = 1;
        });
      });
      section('predmeti', 'Predmeti', subj);
      // The home page's results: who teaches the subjects found (build.py picker teachers), with which of them.
      if (onPage) {
        var byName = {};
        data.people.forEach(function (t) { byName[t[0]] = t; });
        section('predaju', 'Predaju', (data.teachers || []).map(function (t) {
          var taught = t[1].filter(function (i) { return found[i]; });
          return taught.length && byName[t[0]] ? person(byName[t[0]], taught.map(function (i) { return data.subjects[i][1]; }).join(', ')) : null;
        }).filter(Boolean));
      }
      // The listed first, so those show where there is room.
      section('nastavnici', 'Nastavnici', data.people.filter(function (t) { return has(fold(t[0])); })
        .map(function (t) { return person(t); }));
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
      // Linkovi's cards (build.py LINKS), by name and address; the drive's keeps its data-domain (the dialog before it).
      section('linkovi', 'Linkovi', (data.linkovi || []).filter(function (r) { return has(fold(r[0] + ' ' + r[1])); })
        .map(function (r) { return ['', r[0], r[1], r[2], function (a) { icon('link')(a); if (r[3]) a.setAttribute('data-domain', r[3]); }]; }));
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
        box.setAttribute('aria-label', 'Threadovi i vesti');
        box.appendChild(el('p', 'cmd__h', 'Threadovi i vesti')).setAttribute('aria-hidden', 'true');
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
    var ready = izbor && izbor.then(function (j) {
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
      // A phone: scrolling the page (not the list) closes the list and the keyboard. Not the scroll the keyboard makes
      // as it opens (iOS brings the bar into view): only past 40px from where the focus was, once it has settled.
      var focusY = 0, focusT = 0;
      q.addEventListener('focus', function () { focusY = scrollY; focusT = Date.now(); });
      addEventListener('scroll', function () {
        if (list.hidden && d.activeElement !== q) return;
        if (!matchMedia('(max-width: 759px)').matches || Date.now() - focusT < 500 || Math.abs(scrollY - focusY) < 40) return;
        list.hidden = true;
        if (d.activeElement === q) q.blur();
      }, { passive: true });
      // Typed before the lists loaded.
      if (d.activeElement === q) show();
    });
    if (ready) ready.catch(function () {});
    // The home page's results (search.js): the same matches as the list under the bar, into box; resolves to how many
    // types matched (0 without the lists).
    window.masinciMatches = function (v, box) {
      return ready ? ready.then(function () { matches(box, v, true); return box.children.length; }, function () { return 0; }) : Promise.resolve(0);
    };
    // The home page's text search (search.js): a word of the query that is a subject's acronym (izbor.json acr: TMO,
    // ME1) is searched as the subject's name too. The queries with the word in its place, folded, at most 8; '' none.
    // Not a two-letter one without a digit ('od', 'je' are some subject's too).
    window.masinciExpand = function (v) {
      return ready ? ready.then(function () {
        var words = fold(v).split(/\s+/).filter(Boolean), alts = [], seen = {};
        words.forEach(function (w, k) {
          if (w.length < 3 && !/\d/.test(w)) return;
          data.subjects.forEach(function (s, i) {
            if ((' ' + data.acr[i] + ' ').indexOf(' ' + w + ' ') < 0) return;
            var alt = words.slice(0, k).concat([fold(s[1])], words.slice(k + 1)).join(' ');
            if (!seen[alt]) { seen[alt] = 1; alts.push(alt); }
          });
        });
        return alts.slice(0, 8);
      }, function () { return []; }) : Promise.resolve([]);
    };
  }

  /* The page links: the current page's is marked (the phone's tab bar shows it); a section's pages count as it
     (a teacher's page is under Nastavnici, an archived schedule page under Raspored, a news post under Vesti, a page
     of the faculty's site under Linkovi). */
  var here = location.pathname.replace(/^\/nastavnik\//, '/nastavnici/').replace(/^\/katedr[ae]\//, '/predmeti/').replace(/^\/studije\//, '/raspored/')
    .replace(/^\/vest\//, '/vesti/').replace(/^\/mf\//, '/link/');
  [].forEach.call(d.querySelectorAll('.snav a'), function (a) {
    if (a.pathname === '/' ? here === '/' : here.indexOf(a.pathname) === 0) a.setAttribute('aria-current', 'page');
  });

  /* The logo (a button, base.html). On a phone, where the header has no room for the name, a tap shows it over the
     rest of the bar for a few seconds (style.css .brand.is-open). */
  var brand = d.querySelector('.brand'), brandT;
  /* And on every screen, the logo drawn away and on again (style.css .brand__mark svg.rev, .play): backwards 1.65 s,
     0.1 s of nothing, forwards 1.65 s; each step when the last line of the one before ends (the ring going, the M
     coming). A tap during it changes nothing: it runs to its end. */
  var mark = brand && brand.querySelector('.brand__mark svg'), markT;
  if (mark) {
    brand.addEventListener('click', function () {
      if (window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      if (mark.classList.contains('rev') || mark.classList.contains('play')) return;
      mark.classList.add('rev');
    });
    mark.addEventListener('animationend', function (e) {
      var c = e.target.classList;
      if (e.animationName === 'brand-erase' && c.contains('brand__ring')) {
        markT = setTimeout(function () { mark.classList.replace('rev', 'play'); }, 100);
      } else if (e.animationName === 'brand-draw' && c.contains('brand__m')) mark.classList.remove('play');
    });
    // Stopped half way (the logo hidden): ready for the next tap, not stuck as running.
    mark.addEventListener('animationcancel', function () {
      clearTimeout(markT);
      mark.classList.remove('play', 'rev');
    });
  }
  // The name stays its 3 s from the first tap: another tap while it shows does not start them again.
  if (brand && window.matchMedia) {
    brand.addEventListener('click', function () {
      if (!matchMedia('(max-width: 759px)').matches || brand.classList.contains('is-open')) return;
      brand.classList.add('is-open');
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
  // h1: the card's height after the change, if measured already (at the click, before anything moves: a page-wide restyle).
  // ready: the followed subjects' rows for Najnoviji threadovi (fillMine), loading since the click when late: then its
  // new height is known only once they are in, and it moves from there, in the time left.
  var fadeStudije = function (change, h1, ready, late) {
    var card = d.querySelector('#res > .fb--forums'), ol = card && card.querySelector('.fb__rows');
    if (!ol || !ol.built || card.closest('.searching') || matchMedia('(prefers-reduced-motion: reduce)').matches) return change();
    // The card moves for all of it; the rows fade out for its first part and in for the rest, so both end together.
    var all = 400, out = { duration: 150, easing: 'ease-in', fill: 'forwards' }, k = 0;
    // The rows that stay as they are: the followed smerovi already first as built (first in both orders).
    while (k < ol.built.length && (ol.built[k].dataset.pids || '').split(' ').some(window.mojiNow.has)) k++;
    var rows = ol.built.slice(k), cards = [card];
    // Najnoviji threadovi too, when it is on the screen in place (not the peek, search.html .fade): all under its title
    // bar, as its rows swap with the followed subjects' (style.css .moji-only).
    var news = !d.documentElement.classList.contains('fade') && d.querySelector('#res > .lists > .fb:has([data-mine])');
    if (news) {
      if (!late) cards.push(news);
      rows = rows.concat([].slice.call(news.querySelectorAll(':scope > :not(.fb__h)')));
    }
    // From what is on the screen: a flip mid-way starts where the last one got to.
    var from = rows.map(function (r) { return getComputedStyle(r).opacity; });
    var h0 = cards.map(function (c) { return c.getBoundingClientRect().height; });
    studijeAnims.forEach(function (a) { a.cancel(); });
    // Else the cards' heights after the change (the new choice is saved already), now.
    var measure = function () { return cards.map(function (c) { return c.getBoundingClientRect().height; }); };
    if (h1 == null || h1.length !== cards.length) h1 = window.mojiAhead(measure);
    var moves = cards.map(function (c, i) {
      return c.animate({ height: [h0[i] + 'px', h1[i] + 'px'] }, { duration: all, easing: 'cubic-bezier(.4, 0, .2, 1)' });
    });
    var outs = rows.map(function (r, i) { return r.animate({ opacity: [from[i], 0] }, out); });
    studijeAnims = outs.concat(moves);
    // The change once the fade out has ended (not a timer: it waits for a slow phone's frames too, as the card's move
    // does). A flip mid-way cancels these, and so this.
    Promise.all(outs.map(function (a) { return a.finished; }).concat(ready || [])).then(function () {
      outs.forEach(function (a) { a.cancel(); });
      if (news && late) {
        var n0 = news.getBoundingClientRect().height, n1 = window.mojiAhead(function () { return news.getBoundingClientRect().height; });
        moves.push(news.animate({ height: [n0 + 'px', n1 + 'px'] }, { duration: all - out.duration, easing: 'cubic-bezier(.4, 0, .2, 1)' }));
      }
      change();
      // Each row to its own opacity now (a greyed smer's .45, head.js), ending with the move.
      studijeAnims = moves.concat(rows.map(function (r) {
        return r.animate({ opacity: [0, getComputedStyle(r).opacity] }, { duration: all - out.duration, easing: 'cubic-bezier(.2, .8, .2, 1)' });
      }));
    }, function () {});
  };
  // Studije's height with the switch the other way, measured ahead, a second after the page or a change has settled
  // (a page-wide restyle; at the click it stalls the first frames on a phone). Again after each change and resize;
  // null until then, and while things move (then fadeStudije measures).
  var studijeNext = null, nextWait = 0;
  var measureNext = function () {
    studijeNext = null;
    clearTimeout(nextWait);
    nextWait = setTimeout(function () {
      var card = d.querySelector('#res > .fb--forums'), cl = d.documentElement.classList;
      if (!card || !only || card.getAnimations({ subtree: true }).length || cl.contains('falling')) return;
      // As fadeStudije's cards: Najnoviji threadovi too when in place.
      var news = !cl.contains('fade') && d.querySelector('#res > .lists > .fb:has([data-mine])');
      var cards = news ? [card, news] : [card];
      studijeNext = window.mojiAhead(function () { return cards.map(function (c) { return c.getBoundingClientRect().height; }); }, only.checked ? '1' : '');
    }, 1000);
  };
  d.addEventListener('moji', measureNext);
  window.addEventListener('resize', measureNext);
  if (d.fonts) d.fonts.ready.then(measureNext);
  measureNext();
  if (only) only.addEventListener('change', function () {
    try { localStorage.setItem('sve', only.checked ? '' : '1'); } catch (e) {}
    // A search on view runs again (search.js); elsewhere the page only shows more or fewer rows. at: the click's
    // time, for what is timed from it (search.html: the lists under Studije).
    var at = performance.now(), on = only.checked, h1 = studijeNext;
    studijeNext = null;
    // On: Najnoviji threadovi's followed rows load now, while the rows fade out (late: not in yet).
    var ready = on ? fillMine(true) : null, late = on && !mineIn;
    // Off: the lists under Studije fall back to their peek first (search.html fallFirst), then Studije changes; unless
    // the switch went back on meanwhile.
    (on || !window.fallFirst ? Promise.resolve() : window.fallFirst()).then(function () {
      if (only.checked === on) fadeStudije(function () { d.dispatchEvent(new CustomEvent('moji', { detail: { at: at } })); }, h1, ready, late);
    });
  });


  /* A table filter in the page (a subject's topics, the teachers, a smer's subjects): every row is in the page.
     data-f="find": all words in the row's folded data-find (the bar's own search box, ?q=); data-f="x" on a select: the
     value is one of row data-x ("a|b"). Enter in the box: data-enter and q= when the bar has it (the texts of a
     subject's posts, of the news), else the one row left, if one is. */
  var bar = d.querySelector('[data-filter]'), runRows = null;
  if (bar) {
    var rows = [].slice.call(d.querySelectorAll('[data-rows] > li:not([data-sep])'));
    // The archive's headings between rows (its milestones, its 'no year' one): each with the row it stands above (none:
    // the list's end), to go back there once the rows are moved.
    var seps = [].map.call(d.querySelectorAll('[data-sep]'), function (s) {
      var a = s.nextElementSibling;
      while (a && a.hasAttribute('data-sep')) a = a.nextElementSibling;
      return [s, a, s.parentNode];
    });
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
      // The archive's headings back above their rows (the rows were moved to the end past them), in their order.
      seps.forEach(function (s) { if (s[1]) s[1].parentNode.insertBefore(s[0], s[1]); else s[2].appendChild(s[0]); });
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
      // Regrouped or reordered: the archive's headings and its second cards (data-dup) go.
      var arranged = !!(gsel && gsel.value) || !!(ssel && ssel.value);
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
        r.hidden = !ok || (arranged && r.hasAttribute('data-dup'));
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
      // The archive's headings, in the page's own order only: 'no year' while a row under it is on view, a milestone
      // while one above it is (it marks where they end).
      var onView = function (s, way) {
        for (var r = s[way]; r; r = r[way]) if (!r.hasAttribute('data-sep') && !r.hidden) return true;
        return false;
      };
      seps.forEach(function (s) {
        s[0].hidden = arranged || !onView(s[0], s[0].dataset.sep === 'ms' ? 'previousElementSibling' : 'nextElementSibling');
      });
      if (none) none.hidden = shown > 0 || (left && !left.hidden);
      // While a filter is set, a list with no row on view goes with its heading (a smer's subjects, its notices, its
      // subjects without posts); the one that says nothing matched stays.
      [].forEach.call(d.querySelectorAll('.fb'), function (f) {
        if (f.querySelector('[data-rows]')) f.hidden = filtering && !f.querySelector('[data-rows] > li:not([hidden])') && !(none && !none.hidden && f.contains(none));
      });
      // String(p), not p.size: Safari before 17 has no size.
      history.replaceState(history.state, '', String(p) ? '?' + p : location.pathname);
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

  /* A paged list (vesti.html, objave.html; build.py render_paged). The page has the first rows as built; every row is
     in <base>rows-<year>.json ([search text, select values, subject href, HTML]), fetched only as needed: paging
     through, the years up to the page shown (data-counts says how many each has); a search, the select or "Samo moji
     predmeti", every year in view (once; then the browser's cache). The URL keeps the view: the year as the path
     (<base><year>/), then ?q=, the select, strana=, po= (the page size, also kept in localStorage). */
  var pgBar = d.querySelector('[data-pager]');
  if (pgBar) (function () {
    var base = pgBar.dataset.base, counts = JSON.parse(pgBar.dataset.counts);
    var years = Object.keys(counts).sort().reverse(), all = years.reduce(function (s, y) { return s + counts[y]; }, 0);
    var ysel = pgBar.querySelector('[data-pg-year]'), findBox = pgBar.querySelector('[data-f="find"]');
    var sel = pgBar.querySelector('select[data-f]'), per = d.querySelector('[data-pg-per]');
    var ol = d.querySelector('[data-rows]'), navs = [].slice.call(d.querySelectorAll('[data-pg]'));
    var shown = pgBar.querySelector('[data-shown]'), none = d.querySelector('[data-none]'), h1 = d.querySelector('[data-pg-h]');
    var moji = pgBar.hasAttribute('data-moji'), data = {}, loads = {}, page = 1, asBuilt = true, ask = 0;
    // ?v=: a deploy with new rows changes the counts, so no cache keeps an old year's file.
    var load = function (y) {
      return loads[y] = loads[y] || fetch(base + 'rows-' + y + '.json?v=' + all).then(function (r) { return r.json(); }).then(function (rows) { data[y] = rows; });
    };
    var num = function (n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); };
    var size = function () { return +per.value || 50; };
    var title = d.title.indexOf(' · ') > -1 ? d.title.slice(d.title.indexOf(' · ')) : '';
    var href = function (p) {
      var q = new URLSearchParams(), y = ysel.value;
      if (findBox.value.trim()) q.set('q', findBox.value.trim());
      if (sel.value) q.set(sel.name, sel.value);
      if (p > 1) q.set('strana', p);
      if (size() !== 50) q.set('po', size());
      return base + (y ? y + '/' : '') + (String(q) ? '?' + q : '');
    };
    // The page links: first, last, and two either side of this one; ' …' between.
    var drawNav = function (pages) {
      var ks = [];
      for (var k = 1; k <= pages; k++) if (k === 1 || k === pages || Math.abs(k - page) <= 2) ks.push(k);
      var a = function (k, text, label) {
        return k < 1 || k > pages || k === page && text ? '<span class="lp__a lp__a--off" aria-hidden="true">' + text + '</span>'
          : k === page ? '<span class="lp__a" aria-current="page">' + k + '</span>'
          : '<a class="lp__a" href="' + href(k) + '" data-p="' + k + '"' + (label ? ' aria-label="' + label + '"' : '') + '>' + (text || k) + '</a>';
      };
      var html = a(page - 1, '‹', 'Prethodna strana');
      ks.forEach(function (k, i) {
        if (i && k - ks[i - 1] > 1) html += '<span class="lp__gap">…</span>';
        html += a(k);
      });
      html += a(page + 1, '›', 'Sledeća strana');
      navs.forEach(function (n) {
        n.querySelector('[data-pg-pages]').innerHTML = pages > 1 ? html : '';
        // The top one also has the page size: shown while a smaller size would page the list.
        n.hidden = n.classList.contains('lp--top') ? total <= 25 : pages < 2;
      });
    };
    var total = 0;
    var run = function (push) {
      var y = ysel.value, inView = y ? [y] : years, n = size(), start;
      var words = fold(findBox.value.trim()).split(/\s+/).filter(Boolean), v = sel.value;
      var m = moji && window.mojiNow && window.mojiNow.only ? window.mojiNow : null;
      var filtering = words.length || v || m;
      if (push) history.pushState(history.state, '', href(page));
      // Not filtering: the counts give the pages, and which years hold this one.
      if (!filtering) {
        total = y ? counts[y] : all;
        page = Math.max(1, Math.min(page, Math.ceil(total / n)));
        start = (page - 1) * n;
        history.replaceState(history.state, '', href(page));
        drawNav(Math.ceil(total / n));
        shown.textContent = total ? num(start + 1) + '–' + num(Math.min(start + n, total)) + ' od ' + num(total) : '0';
        if (asBuilt && page === 1 && n === 50) return;
      }
      asBuilt = false;
      var acc = 0, want = filtering ? inView : inView.filter(function (yy) {
        var hit = acc < start + n && acc + counts[yy] > start;
        acc += counts[yy];
        return hit;
      });
      var missing = want.filter(function (yy) { return !data[yy]; }), mine = ++ask;
      if (missing.length) {
        shown.textContent = 'učitavam…';
        Promise.all(missing.map(load)).then(function () { if (mine === ask) run(false); });
        return;
      }
      var rows;
      if (filtering) {
        rows = [].concat.apply([], inView.map(function (yy) { return data[yy]; })).filter(function (r) {
          if (!words.every(function (w) { return r[0].indexOf(w) > -1; })) return false;
          if (v && ('|' + r[1] + '|').indexOf('|' + v + '|') < 0) return false;
          return !m || m.has(r[2]);
        });
        total = rows.length;
        page = Math.max(1, Math.min(page, Math.ceil(total / n)));
        start = (page - 1) * n;
        drawNav(Math.ceil(total / n));
        shown.textContent = total ? num(start + 1) + '–' + num(Math.min(start + n, total)) + ' od ' + num(total) : '0';
        history.replaceState(history.state, '', href(page));
        rows = rows.slice(start, start + n);
      } else {
        // The years before the first one wanted, skipped by their counts.
        var skip = 0;
        for (var i = 0; inView[i] !== want[0]; i++) skip += counts[inView[i]];
        rows = [].concat.apply([], want.map(function (yy) { return data[yy]; })).slice(start - skip, start - skip + n);
      }
      ol.innerHTML = rows.map(function (r) { return r[3]; }).join('');
      markNew();
      if (none) none.hidden = total > 0;
    };
    var fromUrl = function () {
      var q = new URLSearchParams(location.search), y = location.pathname.slice(base.length).replace(/\/$/, '');
      ysel.value = counts[y] ? y : '';
      findBox.value = q.get('q') || '';
      sel.value = q.get(sel.name) || '';
      if (sel.selectedIndex < 0) sel.selectedIndex = 0;
      var po = q.get('po');
      try { po = po || localStorage.getItem('po'); } catch (e) {}
      per.value = po || '50';
      if (per.selectedIndex < 0) per.value = '50';
      page = +q.get('strana') || 1;
    };
    fromUrl();
    run(false);
    var again = function () { page = 1; run(false); };
    // The heading and the tab's title name the year (pismo.js converts them as they change).
    var named = function () {
      h1.textContent = h1.dataset.pgH + (ysel.value ? ' ' + ysel.value : '');
      d.title = h1.textContent + title;
    };
    findBox.addEventListener('input', again);
    sel.addEventListener('change', again);
    ysel.addEventListener('change', function () { page = 1; named(); run(true); });
    per.addEventListener('change', function () {
      try { localStorage.setItem('po', per.value); } catch (e) {}
      page = 1;
      run(true);
    });
    navs.forEach(function (n) {
      n.addEventListener('click', function (e) {
        var a = e.target.closest('a[data-p]');
        if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
        e.preventDefault();
        page = +a.dataset.p;
        run(true);
        // From the bottom one, back up to the list's top.
        if (!n.classList.contains('lp--top')) pgBar.scrollIntoView({ block: 'start' });
      });
    });
    window.addEventListener('popstate', function () { fromUrl(); named(); run(false); });
    if (moji) d.addEventListener('moji', again);
    // Enter in the box: the text search of the whole site (data-enter).
    findBox.addEventListener('keydown', function (e) {
      var v = findBox.value.trim();
      if (e.key !== 'Enter' || !v) return;
      e.preventDefault();
      location.href = pgBar.dataset.enter + 'q=' + encodeURIComponent(fold(v));
    });
  })();

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

  // The /mojipredmeti/ picker: moji.js (that page only), with what it shares with the rest of the site.
  window.masinci = { el: el, izbor: izbor, mine: mine, keepMine: keepMine };
  // The followed subjects whose rows are in (or coming), and that promise: the switch's click starts the load (on: the
  // fetch runs while the rows fade out, fadeStudije), and the 'moji' after it finds them there.
  var mineFor = null, mineLoad = null, mineIn = false;
  var fillMine = function (on) {
    // Najnoviji threadovi's rows of the followed subjects (rows.html topic_rows mine), shown in place of its own only while
    // "Samo moji predmeti" is on (head.js, style.css .moji-only); only then loaded. on: it is being switched on.
    var ol = d.querySelector('[data-mine]'), list = mine(), key = JSON.stringify(list.map(function (s) { return s.href; }));
    if (!ol || !(on || (window.mojiNow && window.mojiNow.only))) return Promise.resolve();
    if (key === mineFor) return mineLoad;
    var sec = ol.parentNode;
    mineFor = key;
    mineIn = false;
    // A subject with no topics on the board (followed from the plans) links its page in the subject book: no rows.
    return mineLoad = Promise.all(list.filter(function (s) { return s.href.indexOf('/predmet/') === 0; }).map(function (s) {
      return fetch(s.href + 'novo.json').then(function (r) { return r.ok ? r.json() : { rows: [] }; })
        .catch(function () { return { rows: [] }; });
    })).then(function (all) {
      // [last post time, row HTML]: the newest across the subjects first. The rows are this site's own build.
      var rows = [].concat.apply([], all.map(function (j) { return j.rows; }));
      rows.sort(function (a, b) { return a[0] < b[0] ? 1 : a[0] > b[0] ? -1 : 0; });
      ol.innerHTML = rows.slice(0, 10).map(function (r) { return r[1]; }).join('');
      sec.querySelector('.moji__none').hidden = rows.length > 0;
      if (mineFor === key) mineIn = true;
      markNew();
      measureNext();
    });
  };
  fillMine();
  // search.js puts the home page back when the search is cleared, as built: without these rows.
  d.addEventListener('pocetna', function () { mineFor = null; fillMine(); });
  d.addEventListener('pocetna', function () { window.mojiSort(); });
  d.addEventListener('moji', function () { fillMine(); });

  /* Notifications: web push of the followed subjects' new posts. static/sw.js shows them; the Worker (/push) keeps this
     browser's subscription with the subjects' pages, and ci/push.py sends after each deploy. Only a subject with topics
     (/predmet/) gets posts. An iPhone has web push only for the site opened from the home screen. */
  var PUSH_PUBLIC = 'BPumbbNmB0El3blUr_wKj4PWrpCq0b6pSakijI6H3gtrlgxAqz4abQ63IIwe9EEq50gJNhGDay-Mdb28hsUCSqE';
  // The Android app (app/, docs/PLAN-app.md): its native plugins, null in a browser. Its WebView has no web push: the
  // notifications come through Firebase (FCM) instead, and files and other sites open outside it (below).
  var app = window.Capacitor && Capacitor.isNativePlatform && Capacitor.isNativePlatform() ? Capacitor.Plugins : null;
  // The switches: the side panel's (sidebar.html) and /mojipredmeti/'s (mojipredmeti.html), kept alike. Every page
  // keeps the subscription's subjects up to date (a subject page's star changes them too).
  var pushBoxes = [].slice.call(d.querySelectorAll('[data-push]')), pushMsg = d.querySelector('[data-push-msg]');
  var pushOns = pushBoxes.map(function (b) { return b.querySelector('input'); });
  var said = function (text) { if (pushMsg) { pushMsg.textContent = text; pushMsg.hidden = !text; } };
  // Shown either way; greyed where notifications can't be made, and a click says why (the reason also on hover).
  // aria-disabled, not disabled: a disabled switch takes no click.
  var showPush = function (on, why) {
    pushBoxes.forEach(function (b, i) {
      pushOns[i].checked = on;
      if (why) { pushOns[i].setAttribute('aria-disabled', 'true'); b.title = why; }
      else { pushOns[i].removeAttribute('aria-disabled'); b.removeAttribute('title'); }
      b.hidden = false;
    });
  };
  /* How to turn them on, for this device and browser: why (the switch's title) and the steps, in the dialog below.
     kind: 'blocked' (the reader said no, or the phone's settings), 'install' (an iPhone: only from the home screen),
     'none' (a browser without web push). The menu names as the browsers show them in English, which is how most
     phones here are set. */
  var ua = navigator.userAgent;
  var ios = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var android = /Android/.test(ua);
  var inApp = /FBAN|FBAV|Instagram|Messenger|Line\/|TikTok|Snapchat/.test(ua);
  var brow = /SamsungBrowser/.test(ua) ? 'Samsung Internet' : /Edg(A|iOS)?\//.test(ua) ? 'Edge' : /OPR\/|Opera/.test(ua) ? 'Opera'
    : /Firefox|FxiOS/.test(ua) ? 'Firefox' : /Chrome|CriOS/.test(ua) ? 'Chrome' : /Safari/.test(ua) ? 'Safari' : '';
  var pushSteps = function (kind) {
    if (inApp) return ['Ova stranica je otvorena u aplikaciji (Instagram, Messenger…), koja ne prima obaveštenja sajtova.',
      'Otvori je u browseru: meni ⋯ ili ⋮ → „Open in browser”.', 'Tamo uključi Obaveštenja.'];
    if (kind === 'install') return [
      'Na iPhone-u obaveštenja stižu samo sajtu dodatom na početni ekran (iOS 16.4 ili noviji).',
      brow === 'Safari' || !brow ? 'Dodirni Share (kvadrat sa strelicom nagore), dole na ekranu.' : 'Dodirni Share (kvadrat sa strelicom nagore) u ' + brow + '-u.',
      'Izaberi „Add to Home Screen”, pa „Add”.',
      'Otvori sajt sa početnog ekrana (ikonica „Mašinci”).',
      'U panelu Obaveštenja uključi prekidač, pa dozvoli („Allow”).'];
    if (kind === 'blocked') {
      if (app) return ['Obaveštenja su isključena za aplikaciju.', 'Otvori Settings na telefonu → Apps → Mašinci → Notifications.',
        'Uključi „All Mašinci notifications”.', 'Vrati se ovde i uključi prekidač.'];
      if (ios) return ['Obaveštenja su isključena za ovaj sajt.', 'Otvori Settings na telefonu → Notifications → Mašinci.',
        'Uključi „Allow Notifications”.', 'Vrati se ovde i uključi prekidač.'];
      if (android && brow === 'Firefox') return ['Firefox je blokirao obaveštenja ovom sajtu.',
        'Dodirni katanac levo od adrese.', 'Kod „Notifications” izaberi „Allowed”.', 'Osveži stranicu i uključi prekidač.'];
      if (android) return [(brow || 'Browser') + ' je blokirao obaveštenja ovom sajtu.',
        'Dodirni ikonicu levo od adrese → „Permissions” (ili „Site settings”).',
        'Uključi „Notifications”.',
        'Ako i dalje ne radi: Settings na telefonu → Apps → ' + (brow || 'tvoj browser') + ' → Notifications → uključi.',
        'Osveži stranicu i uključi prekidač.'];
      if (brow === 'Safari') return ['Safari je blokirao obaveštenja ovom sajtu.',
        'U meniju Safari → Settings → Websites → Notifications.', 'Kod masinci.org izaberi „Allow”.',
        'Osveži stranicu i uključi prekidač.'];
      // Not the address bar: a block there doesn't always show, and the global "Block new requests" never does.
      if (brow === 'Firefox') return ['Firefox je blokirao obaveštenja ovom sajtu.',
        'Otvori meni ☰ → Settings → Privacy & Security.', 'Kod Permissions → Notifications klikni „Settings…”.',
        'Kod ' + location.hostname + ' izaberi „Allow”. Ako je štiklirano „Block new requests asking to allow notifications”, odštikliraj ga.',
        'Klikni „Save Changes”, osveži stranicu i uključi prekidač.'];
      return [(brow || 'Browser') + ' je blokirao obaveštenja ovom sajtu.',
        'Klikni ikonicu levo od adrese' + (brow === 'Edge' ? ' → „Permissions for this site”.' : ' → „Site settings”.'),
        'Kod „Notifications” izaberi „Allow”.', 'Osveži stranicu i uključi prekidač.'];
    }
    // The home screen's site on iOS before 16.4 (March 2023): an iPhone 6s, 7 or the first SE stops at iOS 15.
    if (ios) return ['Obaveštenja na iPhone-u traže iOS 16.4 ili noviji.', 'Settings → General → Software Update.',
      'Posle ažuriranja otvori sajt sa početnog ekrana i uključi prekidač.',
      'iPhone 7 i stariji ne mogu na iOS 16.4, pa na njima obaveštenja ne rade.'];
    return ['Ovaj browser ne može da prima obaveštenja.',
      android ? 'Otvori sajt u Chrome-u, Firefox-u, Edge-u ili Samsung Internet-u.' : 'Otvori sajt u Chrome-u, Edge-u, Firefox-u ili Safari-ju.',
      'Tamo uključi Obaveštenja.'];
  };
  var pushKind = 'none';
  // The reason and the steps, in a dialog like the one for leaving the archive (.leave).
  var noPush = null;
  pushBoxes.forEach(function (b, i) {
    b.addEventListener('click', function (e) {
      if (pushOns[i].getAttribute('aria-disabled') !== 'true') return;
      e.preventDefault();
      if (!noPush) {
        noPush = d.createElement('dialog');
        noPush.className = 'leave';
        noPush.setAttribute('aria-labelledby', 'nopush-h');
        noPush.innerHTML = '<div class="leave__in"><h2 id="nopush-h">Kako uključiti obaveštenja</h2><p></p><ol class="leave__steps"></ol>'
          + '<details class="leave__rss"><summary>Ili preko RSS-a</summary><div><p>U čitaču vesti (Feedly, Inoreader…) dodaj adresu, '
          + 'ili preuzmi sve predmete odjednom i uvezi ih.</p><ul></ul>'
          + '<a class="btn" data-opml download="moji-predmeti.opml">Preuzmi za čitač (OPML)</a></div></details>'
          + '<div class="leave__acts"><button type="button" class="btn" data-app-settings hidden>Otvori podešavanja</button>'
          + '<button type="button" class="btn">U redu</button></div></div>';
        d.body.appendChild(noPush);
        noPush.addEventListener('click', function (e) {
          // The app: its notification settings, straight (MainActivity's NotifySettings).
          if (e.target.closest('[data-app-settings]')) app.NotifySettings.open();
          if (e.target === noPush || e.target.closest('button')) noPush.close();
        });
      }
      noPush.querySelector('[data-app-settings]').hidden = !(app && app.NotifySettings && pushKind === 'blocked');
      var steps = pushSteps(pushKind), ol = noPush.querySelector('ol');
      noPush.querySelector('p').textContent = steps[0];
      ol.textContent = '';
      steps.slice(1).forEach(function (s) { var li = d.createElement('li'); li.textContent = s; ol.appendChild(li); });
      // RSS: each followed subject's feed (build.py write_feeds), else the whole board's; the OPML only for subjects.
      var feeds = withPosts().map(function (s) { return [s.name, location.origin + s.href + 'feed.xml']; });
      var ul = noPush.querySelector('.leave__rss ul');
      ul.textContent = '';
      (feeds.length ? feeds : [['Svi novi postovi', location.origin + '/feed.xml']]).forEach(function (f) {
        var li = d.createElement('li'), a = d.createElement('a');
        li.textContent = f[0];
        a.href = a.textContent = f[1];
        a.className = 'leave__url';
        li.appendChild(a);
        ul.appendChild(li);
      });
      noPush.querySelector('[data-opml]').hidden = !feeds.length;
      noPush.querySelector('.leave__rss').open = false;
      noPush.showModal();
      noPush.querySelector('button').focus();
    });
  });
  var blocked = 'Browser ne dozvoljava obaveštenja ovom sajtu (podešavanja sajta).';
  var withPosts = function () {
    return mine().filter(function (s) { return s.href.indexOf('/predmet/') === 0; });
  };
  if (app) {
    /* In the app: FCM. Its token (from register()) goes to the Worker as {fcm, s, t}, cached and queued as a
       browser's subscription is below; "off" empties its subjects and unregisters. The token can change (FCM
       renews them): each start registers again, and a new one is saved; ci/push.py drops the old when FCM says
       it is gone. */
    var P = app.PushNotifications;
    var stored = function () { try { return localStorage.getItem('fcm'); } catch (e) { return null; } };
    var gotToken = null;
    P.addListener('registration', function (r) {
      try { localStorage.setItem('fcm', r.value); } catch (e) {}
      if (gotToken) gotToken.ok(r.value);
    });
    P.addListener('registrationError', function (r) { if (gotToken) gotToken.no(new Error(r.error)); });
    // No answer in 20 s (a phone without Google's services): failed, so the switch's queue goes on.
    var register = function () {
      return new Promise(function (ok, no) {
        gotToken = { ok: ok, no: no };
        P.register().catch(no);
        setTimeout(function () { no(new Error('fcm')); }, 20000);
      });
    };
    // A tap on a notification: its post (ci/push.py message's url), in the app.
    P.addListener('pushNotificationActionPerformed', function (a) {
      var u = a.notification && a.notification.data && a.notification.data.url;
      // The post's path on the app's own host: the same page live, and a LAN test build stays on the PC's server.
      if (u && /^https:\/\/masinci\.org\//.test(u)) location.href = u.slice('https://masinci.org'.length);
    });
    var appSave = function (token, list) {
      var o = { fcm: token, s: list.map(function (m) { return m.href; }) }, t = {}, was = null;
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
    var appBlocked = 'Uređaj ne dozvoljava notifikacije od ove aplikacije.';
    var appQueue = P.checkPermissions().then(function (p) {
      var on = p.receive === 'granted' && !!stored();
      if (p.receive === 'denied') pushKind = 'blocked';
      showPush(on, p.receive === 'denied' ? appBlocked : '');
      if (on) return register().then(function (token) { return appSave(token, withPosts()); });
    }).catch(function () {});
    // Back from the phone's settings (the dialog's "Otvori podešavanja"): allowed there, the switch is no longer grey.
    if (app.App) app.App.addListener('resume', function () {
      if (pushKind !== 'blocked') return;
      P.checkPermissions().then(function (p) {
        if (p.receive !== 'granted') return;
        pushKind = 'none';
        showPush(!!stored(), '');
        said('');
      });
    });
    var appTimer, autoTried = false;
    d.addEventListener('moji', function () {
      // The first subject with posts chosen in the app: notifications on by themselves (the permission asked), unless
      // the reader turned them off before ('push-off'); once a page, so a failed try doesn't ask at every star.
      var off = null;
      try { off = localStorage.getItem('push-off'); } catch (e) {}
      if (!autoTried && !stored() && !off && withPosts().length && pushOns.length && !pushOns[0].checked) {
        autoTried = true;
        pushOns[0].checked = true;
        pushOns[0].dispatchEvent(new Event('change'));
      }
      clearTimeout(appTimer);
      appTimer = setTimeout(function () {
        appQueue = appQueue.then(function () { if (stored()) return appSave(stored(), withPosts()); }).catch(function () {});
      }, 3000);
    });
    pushOns.forEach(function (pushOn) { pushOn.addEventListener('change', function (e) {
      var on = pushOn.checked, own = e.isTrusted;
      // A reader's own "off" (not the automatic "on" above): the next subject doesn't turn them on again.
      try { if (e.isTrusted) { if (on) localStorage.removeItem('push-off'); else localStorage.setItem('push-off', '1'); } } catch (err) {}
      showPush(on, '');
      said('');
      appQueue = appQueue.then(function () {
        if (!on) {
          var token = stored();
          return (token ? appSave(token, []) : Promise.resolve()).then(function () {
            try { localStorage.removeItem('fcm'); } catch (e) {}
            return P.unregister();
          });
        }
        return P.requestPermissions().then(function (p) {
          if (p.receive !== 'granted') throw new Error('dozvola');
          return register();
        }).then(function (token) { return appSave(token, withPosts()); }).then(function () {
          said('Stižu kad arhiva preuzme nove threadove sa foruma. Sajt čuva samo adresu obaveštenja ovog telefona i spisak predmeta.');
        });
      }).catch(function (e) {
        if (on && e.message === 'dozvola') pushKind = 'blocked';
        // Registered but not kept by the Worker: undone, so the switch shows the truth next time.
        if (on) {
          try { localStorage.removeItem('fcm'); } catch (err) {}
          P.unregister().catch(function () {});
        }
        showPush(!on && !!stored(), on && e.message === 'dozvola' ? appBlocked : '');
        said(e.message === 'dozvola' ? appBlocked : 'Nije uspelo, pokušaj ponovo.');
        // Refused at the reader's own tap: the steps and the settings button at once (the grey switch's click opens
        // them); not after the automatic "on", which the reader didn't ask for.
        if (own && on && e.message === 'dozvola') pushBoxes[pushOns.indexOf(pushOn)].click();
      });
    }); });
  } else if (window.PushManager && window.Notification && navigator.serviceWorker) {
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
    // Every write to the Worker waits for the one before it (the switch's, below): a resave between an "off"'s write
    // and its unsubscribe would keep the subscription.
    var queue = resave(), want;
    var timer;
    d.addEventListener('moji', function () {
      // Picking subjects is many clicks: one write a few seconds after the last.
      clearTimeout(timer);
      timer = setTimeout(function () { queue = queue.then(resave); }, 3000);
    });
    var denied = function () {
      if (Notification.permission !== 'denied') return '';
      pushKind = 'blocked';
      return blocked;
    };
    current().then(function (sub) {
      showPush(!!sub && Notification.permission === 'granted', denied());
    }).catch(function () {});
    // One change at a time, each for the switch as it is when its turn comes: clicks faster than the network left
    // the Worker a subscription the browser had dropped (an "off" unsubscribing after an "on" saved it), and the
    // count one too high until a notification to it failed.
    pushOns.forEach(function (pushOn) { pushOn.addEventListener('change', function () {
      want = pushOn.checked;
      showPush(want, '');
      said('');
      // The prompt is asked in the click itself, not when its turn in the queue comes: Firefox and Safari show it
      // only right after a click, and a write still going (the page's own resave) would make it fail unasked.
      if (want && Notification.permission === 'default') asked = Notification.requestPermission();
      queue = queue.then(applyPush);
    }); });
    var asked;
    var applyPush = function () {
      var on = want;
      return (on ? Promise.resolve(Notification.permission === 'granted' ? 'granted' : asked).then(function (p) {
        if (p !== 'granted') throw new Error('dozvola');
        var key = Uint8Array.from(atob(PUSH_PUBLIC.replace(/-/g, '+').replace(/_/g, '/')), function (c) { return c.charCodeAt(0); });
        return reg.then(function (r) { return r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }); });
      }).then(function (sub) { return save(sub, withPosts()); }).then(function () {
        said('Stižu kad arhiva preuzme nove threadove sa foruma. Sajt čuva samo adresu obaveštenja ovog browsera i spisak predmeta.');
      }) : current().then(function (sub) {
        if (sub) return save(sub, []).then(function () { return sub.unsubscribe(); });
      })).catch(function (e) {
        // A newer click is queued: it decides what the switch shows.
        if (on !== want) return;
        showPush(!on, denied());
        said(e.message === 'dozvola' ? blocked : 'Nije uspelo, pokušaj ponovo.');
        // Subscribed in the browser but not kept by the Worker: undone, so the switch shows the truth next time.
        if (on) return current().then(function (sub) { if (sub) return sub.unsubscribe(); }).catch(function () {});
      });
    };
  } else {
    var iphone = navigator.standalone === false;
    pushKind = iphone ? 'install' : 'none';
    showPush(false, iphone ? 'Na iPhone-u: Deli → Dodaj na početni ekran, pa otvori sajt odatle.' : 'Ovaj browser ne može da prima obaveštenja.');
    if (iphone) said('Obaveštenja na iPhone-u: Deli → Dodaj na početni ekran, pa otvori sajt odatle.');
  }

  /* "Skini aplikaciju" (sidebar.html): in an Android browser, not in the app itself; the i explains, in a dialog like
     the notifications' one (.leave). */
  var appGet = d.querySelector('[data-app-get]'), appInfo = null;
  if (appGet && android && !app && !inApp) {
    appGet.hidden = false;
    appGet.querySelector('[data-app-info]').addEventListener('click', function () {
      if (!appInfo) {
        appInfo = d.createElement('dialog');
        appInfo.className = 'leave';
        appInfo.setAttribute('aria-labelledby', 'app-h');
        appInfo.innerHTML = '<div class="leave__in"><h2 id="app-h">Aplikacija za Android</h2>'
          + '<p>Browser na telefonu ponekad propusti obaveštenja: Android ga uspava kad ga ne koristiš, pa stignu kasno ili ne uopšte. '
          + 'Aplikacija nema taj problem.</p>'
          + '<ol class="leave__steps"><li>Dodirni „Skini aplikaciju”.</li><li>Otvori preuzeti fajl (masinci.apk).</li>'
          + '<li>Ako telefon pita, dozvoli instalaciju iz browsera, pa se vrati.</li><li>Dodirni „Install”.</li></ol>'
          + '<p>Telefon može da upozori da aplikacija nije sa Google Play-a: ona je ovaj sajt, iz iste arhive.</p>'
          + '<div class="leave__acts"><button type="button" class="btn">U redu</button></div></div>';
        d.body.appendChild(appInfo);
        appInfo.addEventListener('click', function (e) {
          if (e.target === appInfo || e.target.closest('button')) appInfo.close();
        });
      }
      appInfo.showModal();
      appInfo.querySelector('button').focus();
    });
  }

  /* The followed subjects' feeds as one OPML file, which a feed reader imports. Made on the click, from the list now. */
  // Delegated: the notifications dialog (noPush) is made on its first click, after this.
  d.addEventListener('click', function (e) {
    var opml = e.target.closest && e.target.closest('[data-opml]');
    if (!opml) return;
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
    // Paused while off the screen (style.css .wave--off), all at once, so the letters stay in step: their animations
    // cost the main thread every frame, which a phone needs for what does move (the home page's switch).
    if (window.IntersectionObserver) new IntersectionObserver(function (es) {
      wave.classList.toggle('wave--off', !es[es.length - 1].isIntersecting);
    }).observe(wave);
  }

  /* The Android app (app/, docs/PLAN-app.md): a file opens in the phone's app for it (a PDF reader, Word…), another
     site in the phone's browser, without the dialog below. A WebView neither downloads nor opens files itself. */
  var FILE = /\.(pdf|docx?|xlsx?|pptx?|odt|ods|odp|rtf|txt|csv|zip|rar|7z|dwg|dxf|stp|step|jpe?g|png)$/i;
  var inBrowser = function (url) { return app.AppLauncher.openUrl({ url: url }); };
  // Downloaded into the app's cache (Android clears it when space runs low), then opened from there; a folder per
  // address, so two files of one name stay apart and a second tap opens the first download. No app for the type, or
  // no download: the browser, which can still save it.
  var openFile = function (a) {
    if (a.getAttribute('aria-busy') === 'true') return;
    var url = a.href, h = 5381;
    for (var i = 0; i < url.length; i++) h = (h * 33 + url.charCodeAt(i)) >>> 0;
    var name = a.pathname.split('/').pop();
    try { name = decodeURIComponent(name); } catch (err) {}
    var path = 'f/' + h.toString(36) + '/' + (name.replace(/[\\/:*?"<>|\x00-\x1f]/g, '_') || 'fajl');
    var where = { directory: 'CACHE', path: path };
    a.setAttribute('aria-busy', 'true');
    // An empty file is a download that went wrong (a redirect from http to https, which Android doesn't follow): it
    // goes, and the browser gets the address.
    var full = function () { return app.Filesystem.stat(where).then(function (s) { if (!(s.size > 0)) throw 0; }); };
    full().catch(function () {
      return app.Filesystem.mkdir({ directory: 'CACHE', path: path.replace(/\/[^/]*$/, ''), recursive: true }).catch(function () {})
        .then(function () { return app.Filesystem.getUri(where); })
        .then(function (r) { return app.FileTransfer.downloadFile({ url: url, path: r.uri }); })
        .then(full);
    }).then(function () { return app.Filesystem.getUri(where); })
      .then(function (r) { return app.FileOpener.openFile({ path: r.uri }); })
      .catch(function () { app.Filesystem.deleteFile(where).catch(function () {}); return inBrowser(url); })
      .then(function () { a.removeAttribute('aria-busy'); }, function () { a.removeAttribute('aria-busy'); });
  };

  /* The app's overscroll (docs/PLAN-app.md): Android's own stretch is off (MainActivity), as it pulled the header and
     tab bar too; a pull past the top or bottom stretches the content alone and springs back on release. Each block
     between the header and the tab bar scales around the same point (the pulled edge): a common wrapper can't take
     the transform, as the fixed tab bar inside it would move with it. */
  if (app && !matchMedia('(prefers-reduced-motion: reduce)').matches) (function () {
    var y0 = null, edge = 0, parts = [];
    var set = function (s, back) {
      parts.forEach(function (el) {
        el.style.transition = back ? 'transform .35s cubic-bezier(.2,.8,.2,1)' : 'none';
        el.style.transform = s === 1 ? '' : 'scaleY(' + s + ')';
      });
    };
    d.addEventListener('touchstart', function (e) {
      y0 = e.touches.length === 1 && !e.target.closest('dialog, .hd, .snav') ? e.touches[0].clientY : null;
      edge = 0;
    }, { passive: true });
    d.addEventListener('touchmove', function (e) {
      if (y0 === null) return;
      var y = e.touches[0].clientY, root = d.scrollingElement;
      var top = root.scrollTop <= 0, bottom = root.scrollTop + innerHeight >= root.scrollHeight - 1;
      var dir = y > y0 && top ? 1 : y < y0 && bottom ? -1 : 0;
      if (!dir) { if (edge) set(1); edge = 0; y0 = y; return; }
      if (dir !== edge) {
        // The anchor, in each block's own box: the page's top or bottom.
        edge = dir;
        parts = [].slice.call(d.querySelectorAll('.main, .side > .filters:not([hidden]), .ft'));
        var at = dir > 0 ? 0 : root.scrollHeight;
        parts.forEach(function (el) {
          el.style.transformOrigin = '50% ' + (at - el.getBoundingClientRect().top - root.scrollTop) + 'px';
        });
      }
      // Damped: grows fast at first, never past 6 %.
      set(1 + .06 * (1 - Math.exp(-Math.abs(y - y0) / 220)));
    }, { passive: true });
    var end = function () { if (edge) set(1, true); edge = 0; y0 = null; };
    d.addEventListener('touchend', end);
    d.addEventListener('touchcancel', end);
  })();

  var leave = null;
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
    if (!/^https?:$/.test(a.protocol) || a.hasAttribute('data-leave-go')) return;
    var out = a.host !== location.host;
    if (app && (FILE.test(a.pathname) || a.pathname.indexOf('/files/') === 0)) { e.preventDefault(); openFile(a); return; }
    if (app && out) { e.preventDefault(); inBrowser(a.href); return; }
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
    say.innerHTML = named ? 'Ovaj link vodi na <b></b>' : 'Link vodi na <b></b>, sajt van ove arhive. Otvoriće se u novom tabu.';
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

  /* "Podeli" under a post or topic (detail.html, tema.html): the phone's share sheet, else the link copied. */
  [].forEach.call(d.querySelectorAll('[data-share]'), function (b) {
    if (!navigator.share && !navigator.clipboard) return;
    b.hidden = false;
    var label = b.querySelector('span');
    b.addEventListener('click', function () {
      var url = (d.querySelector('link[rel="canonical"]') || location).href.split('#')[0];
      if (navigator.share) return navigator.share({ title: d.title, url: url }).catch(function () {});
      navigator.clipboard.writeText(url).then(function () {
        label.textContent = 'Link kopiran';
        setTimeout(function () { label.textContent = 'Podeli'; }, 1500);
      }, function () {});
    });
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

  /* The 404 page (error.html): the words of the address as a search, '/predmet/oas-mi/termodinamika-x/' as
     'termodinamika x': without the first part (the route), a subject's smer, ids and file endings. */
  var q404 = d.querySelector('[data-404q]');
  if (q404) {
    var parts404 = decodeURIComponent(location.pathname).split('/').filter(Boolean);
    parts404.splice(0, parts404.length > 1 ? (parts404[0] === 'predmet' ? 2 : 1) : 0);
    var words404 = parts404.join(' ').split(/[\s\-_.+]+/).filter(function (w) {
      return w.length > 1 && !/^([a-z]?\d+|html?|php|pdf|cent)$/i.test(w);
    }).join(' ');
    if (words404) {
      q404.querySelector('a').href = '/?q=' + encodeURIComponent(words404);
      q404.querySelector('span').textContent = words404;
      q404.hidden = false;
    }
  }

  /* New since the last visit: a row whose last post (rows.html last, data-t) is newer than the visit before this one
     gets a dot (style.css .fr--new). A visit ends after 30 minutes without a page, so the pages of one visit, and its
     tabs, keep the same mark. The first visit marks nothing. A row whose last post's page was opened after that post
     ('procitano': path → when) has none; nor, on the home page while only "Moji predmeti" show, one whose last post
     (data-p) is in a subject not followed.
     shortcut: a smer row goes by its last post only, so a followed subject's new post under a newer one of another
     subject gets no dot; carry each subject's last time if that matters. */
  var since = 0, read = {};
  try {
    var visits = JSON.parse(localStorage.getItem('poseta')) || {}, nowMs = Date.now();
    if (visits.seen && nowMs - visits.seen > 30 * 60e3) visits.mark = visits.seen;
    since = visits.mark || 0;
    visits.seen = nowMs;
    localStorage.setItem('poseta', JSON.stringify(visits));
    read = JSON.parse(localStorage.getItem('procitano')) || {};
    // Opened before the mark: no post it could hide is new any more.
    for (var k in read) if (read[k] < since) delete read[k];
    read[location.pathname] = nowMs;
    localStorage.setItem('procitano', JSON.stringify(read));
  } catch (e) {}
  function markNew() {
    if (!since) return;
    try { read = JSON.parse(localStorage.getItem('procitano')) || {}; } catch (e) {}
    var m = window.mojiNow;
    [].forEach.call(d.querySelectorAll('.fr__last time[data-t]'), function (t) {
      var row = t.closest('.fr'), at = Date.parse(t.getAttribute('data-t')), last = row.querySelector('.lt') || row.querySelector('.fr__a');
      var on = at > since && !(last && read[last.pathname] > at) && !(m && m.only && t.closest('#res') && !m.has(t.dataset.p));
      if (row.classList.contains('fr--new') === on) return;
      row.classList.toggle('fr--new', on);
      var a = row.querySelector('.fr__a');
      if (on && a) a.insertAdjacentHTML('beforeend', '<span class="vh"> (novo)</span>');
      else if (a && a.querySelector('.vh')) a.querySelector('.vh').remove();
    });
    // A box with dots: a button in its title bar that clears them all, on every page (the mark moves to now).
    [].forEach.call(d.querySelectorAll('.fb'), function (fb) {
      var h = fb.querySelector('.fb__h h2'), b = h && h.querySelector('.fb__clear'), any = !!fb.querySelector('.fr--new');
      if (!h || !!b === any) return;
      if (b) return b.remove();
      b = h.appendChild(el('button', 'fb__clear', 'Pročitano'));
      b.type = 'button';
      b.title = 'Skloni sve oznake novog';
      b.addEventListener('click', function () {
        since = Date.now();
        try {
          var v = JSON.parse(localStorage.getItem('poseta')) || {};
          v.mark = since;
          localStorage.setItem('poseta', JSON.stringify(v));
        } catch (e) {}
        markNew();
      });
    });
  }
  markNew();
  d.addEventListener('pocetna', markNew);
  d.addEventListener('moji', markNew);
  // Back from a post (the page from the cache): its row has been read since.
  addEventListener('pageshow', function (e) { if (e.persisted) markNew(); });

  /* Back up the crumbs to where you were: each page's scroll is kept for the tab (sessionStorage) as it is left, and a
     page opened from the crumbs goes back to it. Other links open a page at the top, as usual. 'crumb': the page the
     crumb leads to, so a stale one (a crumb opened in a new tab) does not move another page. */
  var here = location.pathname + location.search;
  addEventListener('pagehide', function () { try { sessionStorage.setItem('y' + here, scrollY); } catch (e) {} });
  d.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('.crumbs a, .back');
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
  /* "Nazad" under the crumbs (base.html): the page this one was opened from, {u, t}. Kept in this page's history entry
     (history.state.back), so a reload, the browser's back and forward and its page cache all keep each page's own; a
     list of the pages last seen would point back at the page the browser's back came from (a circle: teacher, list,
     another teacher). A new page takes 'cur' (sessionStorage): the page the tab showed last, its address as it was
     left (the home page's search changes it) and its title (the tab's first part, Latin: pismo.js converts the link);
     only when that page is the referrer, so a page opened in a new tab or from a typed address has none. It opens at
     the place it was left (the crumbs' scroll above); a page reached by the browser's own back goes back the same way.
     The other replaceState and pushState calls keep history.state, and with it this. */
  var pageTitle = function () {
    var sq = new URLSearchParams(location.search).get('q');
    return location.pathname === '/' ? (location.search ? 'Pretraga' + (sq ? ' „' + sq + '“' : '') : 'Početna') : d.title.split(' · ')[0];
  };
  var keepCur = function () {
    try { sessionStorage.setItem('cur', JSON.stringify({ u: location.pathname + location.search, t: pageTitle() })); } catch (e) {}
  };
  var showBack = function () {
    var a = d.querySelector('[data-back]'), st = history.state || {}, prev = st.back, left = null, ref = null;
    if (!prev) {
      try { left = JSON.parse(sessionStorage.getItem('cur')); ref = d.referrer && new URL(d.referrer); } catch (e) {}
      var from = left && left.u.split('?')[0];
      if (ref && ref.origin === location.origin && from === ref.pathname && from !== location.pathname) {
        prev = left;
        history.replaceState(Object.assign({}, st, { back: prev }), '');
      }
    }
    keepCur();
    if (!a || !prev) return;
    a.href = prev.u;
    a.querySelector('b').textContent = prev.t;
    a.hidden = false;
    a.addEventListener('click', function (e) {
      if (e.button || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || d.referrer !== location.origin + prev.u) return;
      e.preventDefault();
      history.back();
    });
  };
  addEventListener('pagehide', keepCur);
  if (d.prerendering) d.addEventListener('prerenderingchange', showBack, { once: true }); else showBack();
  // Nor does it go to its #fragment once shown (a topic opened at its newest post, rows.html topic_row): there it goes.
  if (d.prerendering) d.addEventListener('prerenderingchange', function () {
    var t = location.hash && d.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (t) t.scrollIntoView();
  }, { once: true });

  /* "Profesor dana" (sidebar.html): one of /izbor.json dana (load_teachers.of_the_day), the same all day (the
     browser's date). The days since DANA_START go through the list in rounds, each round in its own shuffled order:
     no one comes again before everyone has had a day. /profdana/ shows every day's.
     shortcut: picked from today's list: a past day's changes when the list does (a teacher added, gone, a new
     photo); store each day's pick if the calendar must stay as it was. */
  var DANA_START = new Date(2026, 10, 16);
  // Birthdays, every year: [month from 0, day, the page]. That day is theirs, an extra one: it is left out of the
  // rounds' count, so no one else loses a day.
  var DANA_BDAY = [[9, 23, '/nastavnik/milosav-ognjanovic/']];
  var pickDay = function (list, n) {
    var day = new Date(n.getFullYear(), n.getMonth(), n.getDate());
    var days = Math.round((day - DANA_START) / 864e5);
    for (var b = 0; b < DANA_BDAY.length; b++) {
      var bd = DANA_BDAY[b];
      if (day.getMonth() === bd[0] && day.getDate() === bd[1]) {
        var who = list.filter(function (t) { return t[2] === bd[2]; })[0];
        if (who) return who;
      }
      for (var y = DANA_START.getFullYear(); y <= day.getFullYear(); y++) {
        var on = new Date(y, bd[0], bd[1]);
        if (on >= DANA_START && on < day) days--;
      }
    }
    var len = list.length, round = Math.floor(days / len), order = list.map(function (_, i) { return i; });
    // mulberry32, seeded by the round: the same order in every browser. Another constant: another order.
    var s = round + 0x27d4eb2f;
    var rnd = function () {
      s = s + 0x6d2b79f5 | 0;
      var t = Math.imul(s ^ s >>> 15, 1 | s);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
    for (var i = len - 1; i > 0; i--) {
      var k = Math.floor(rnd() * (i + 1)), x = order[i];
      order[i] = order[k]; order[k] = x;
    }
    return list[order[days - round * len]];
  };
  var dana = d.querySelector('[data-dana]');
  // Not on a phone under a post, a topic or a news item, nor the board's lists of threads: the same as style.css
  // .frame:has(article.post, [data-nodana]), for a browser without :has().
  if (dana && window.matchMedia && matchMedia('(max-width: 899px)').matches && d.querySelector('.frame :is(article.post, [data-nodana])')) dana = null;
  if (dana && izbor) izbor.then(function (j) {
    var list = j.dana || [];
    if (!list.length) return;
    var t = pickDay(list, new Date());
    var a = dana.querySelector('.dana__b');
    a.href = t[2];
    dana.querySelector('.sec').textContent = t[0];
    a.querySelector('img').src = t[3];
    a.querySelector('b').textContent = t[1];
    a.querySelector('small').textContent = t[4] || '';
    // The katedra's icon, as on /nastavnici/'s cards (cards.html .pc__ki).
    if (t[5]) {
      a.querySelector('use').setAttribute('href', '/static/icons.svg#i-' + t[5]);
      a.querySelector('.dana__ki').removeAttribute('hidden');
    }
    // The Studentska lista badge, the same text as cards.html sp_badge.
    if (t[6]) {
      var sp = dana.querySelector('.dana__sp'), tip = 'Studentska lista „Studenti pobeđuju“, parlamentarni izbori 2026: ' + t[6] + '. na listi';
      sp.setAttribute('aria-label', tip);
      sp.querySelector('.sp__tip').textContent = tip;
      sp.hidden = false;
    }
    dana.hidden = false;
  }).catch(function () {});

  /* /profdana/ (profdana.html): every day's pick from DANA_START to today (+ data-ahead days, dev mode), newest
     first (the latest top left), a section per month. */
  var pd = d.querySelector('[data-profdana]');
  if (pd && izbor) izbor.then(function (j) {
    var list = j.dana || [];
    if (!list.length) return;
    var MES = ['januar', 'februar', 'mart', 'april', 'maj', 'jun', 'jul', 'avgust', 'septembar', 'oktobar', 'novembar', 'decembar'];
    var DAN = ['ned', 'pon', 'uto', 'sre', 'čet', 'pet', 'sub'];
    var now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var day = new Date(today), ol = null, month = -1;
    day.setDate(day.getDate() + (+pd.dataset.ahead || 0));
    for (; day >= DANA_START; day.setDate(day.getDate() - 1)) {
      if (day.getMonth() !== month) {
        month = day.getMonth();
        var sec = el('section', 'st');
        sec.appendChild(el('h2', 'st__h', MES[month] + ' ' + day.getFullYear()));
        ol = sec.appendChild(el('ol', 'pd__days'));
        pd.appendChild(sec);
      }
      var t = pickDay(list, day), li = el('li', 'pd__d' + (day > today ? ' pd__d--next' : day.getTime() === today.getTime() ? ' pd__d--today' : ''));
      var a = li.appendChild(el('a'));
      a.href = t[2];
      a.appendChild(el('span', 'pd__when', DAN[day.getDay()] + ' ' + day.getDate() + '.'));
      var img = a.appendChild(el('img', 'pc__img'));
      img.src = t[3]; img.alt = ''; img.loading = 'lazy';
      a.appendChild(el('b', null, t[1]));
      a.appendChild(el('small', null, t[0]));
      ol.appendChild(li);
    }
  }).catch(function () {});

  /* Visitor counter: every page tells the Worker (/visit, each IP once in three days); only /statistika/ shows the
     total, and asks (?push) for the browsers with notifications on too. A prerendered page counts once shown. */
  var visit = function () {
    if (!window.fetch) return;
    var stats = d.getElementById('posete');
    fetch(stats ? '/visit?push' : '/visit', { method: 'POST' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (v) {
      if (!stats || !v) return;
      [['posete', v.n], ['pretplate', v.push]].forEach(function (p) {
        var li = d.getElementById(p[0]);
        if (!li || typeof p[1] !== 'number') return;
        li.firstChild.textContent = p[1].toLocaleString('de-DE'); // 23.692, as build.py's n filter
        li.hidden = false;
      });
    }).catch(function () {});
  };
  if (d.prerendering) d.addEventListener('prerenderingchange', visit, { once: true }); else visit();
})();
