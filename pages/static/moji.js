/* The picker of /mojipredmeti/: mojipredmeti.html loads it (defer: after site.js, which every page has). What it
   shares with the rest of the site, site.js hands over as window.masinci. */
(function () {
  var d = document, m = window.masinci;
  if (!m) return;
  var el = m.el, izbor = m.izbor, mine = m.mine, keepMine = m.keepMine, fold = window.pismoFold;

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
        hint = (hint ? hint + ' · ' : '') + 'bez threadova';
      }
      b.type = 'button';
      b.dataset.ids = ids.join(',');
      b.appendChild(el('span', 'mp__check')).setAttribute('aria-hidden', 'true');
      var t = b.appendChild(el('span', 'mp__name', name));
      if (hint) t.appendChild(el('small', null, hint));
      return b;
    };
    // Each group folds under its heading: open in a search, or where a subject in it is followed.
    var searching = false;
    var group = function (title, list) {
      var sec = el('details', 'mp__group'), grid = el('div', 'mp__cards'), o = followed();
      sec.open = searching || list.some(function (c) { return c.dataset.ids && c.dataset.ids.split(',').some(function (i) { return o[subj[i][0]]; }); });
      sec.appendChild(el('summary', null, title)).appendChild(el('span', null, ' · ' + list.length));
      list.forEach(function (c) { grid.appendChild(c); });
      sec.appendChild(grid);
      body.appendChild(sec);
    };
    // One row of choices: the programs as tabs (the level small, above the program), the rest as chips.
    // Nothing is picked at first; a pick filters the cards, and pressing it again undoes it (phones then show only it).
    // A program as the schedule's tabs (build.py, 'OAS - MI'): 'Основне академске студије — МИ' -> 'ОАС - МИ'
    // (pismo.js writes it in Latin), 'Мастер … — Индустрија 4.0' -> 'МАС - ИНД4.0', the doctoral studies 'ДАС'.
    var short = function (name) {
      var p = name.split(' — '), lv = { 'основне': 'ОАС', 'мастер': 'МАС', 'докторске': 'ДАС' }[p[0].split(' ')[0].toLowerCase()];
      if (!lv || !p[1]) return name;
      if (lv === 'ДАС') return lv;
      return lv + ' - ' + (/^индустрија 4/i.test(p[1]) ? 'ИНД4.0' : p[1]);
    };
    var row = function (level, depth) {
      var r = el('div', depth ? 'mp__chips' : 'mp__tabs'), on = path[depth] < level.length;
      level.forEach(function (n, i) {
        var b = el('button', 'mp__tab');
        b.type = 'button';
        b.setAttribute('aria-pressed', on && i === path[depth]);
        b.appendChild(el('span', null, depth ? n.n : short(n.n)));
        if (!depth) b.title = n.n;
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
      searching = w.length > 0;
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
      } else if (!path.length) {
        // Nothing picked nor searched: no list, a program first (all of them at once were a thousand cards).
        body.appendChild(el('p', 'mp__none', 'Izaberi studijski program ili potraži predmet.'));
      } else if (level.length && level[0].c.length) {
        // A row left unpicked: each choice in it (a year; a module's years) under its heading, its subjects by group
        // as when picked: the required ones, then each elective block on its own. A choice of one unnamed group (Stari
        // predmeti) is that group alone. By name (folded: Edge's 'sr' collation put Avionika before Adaptivne).
        var byName = function (a, b) { return fold(subj[a][1]).localeCompare(fold(subj[b][1])); };
        var show = function (n, pre) {
          var name = pre ? pre + ' › ' + n.n : n.n;
          if (n.c.length && n.c[0].c.length) return n.c.forEach(function (c) { show(c, name); });
          var gs = n.c.length ? n.c : [n];
          if (gs.length === 1 && !gs[0].n) {
            var one = gs[0].s.filter(hit).sort(byName);
            if (one.length) group(name, one.map(function (i) { return card([i], subj[i][1]); }));
            return;
          }
          var head = body.appendChild(el('h3', 'mp__year', name)), any = false;
          gs.forEach(function (g) {
            var ids = g.s.filter(hit).sort(byName);
            if (!ids.length) return;
            any = true;
            group(g.n || 'Obavezni predmeti', ids.map(function (i) { return card([i], subj[i][1]); }));
          });
          if (!any) head.remove();
        };
        level.forEach(function (n) { show(n, ''); });
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
          var n = x[1], one = n % 10 === 1 && n % 100 !== 11, few = n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14);
          // The title without the katedra (people's "title · katedra"): the subject says where they teach.
          var b = grid.appendChild(card([], p[0], [(p[3] || '').split(' · ')[0], n + (one ? ' thread' : few ? ' threada' : ' threadova')].filter(Boolean).join(' · ')));
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
      // Step 1 with nothing picked: no foot on a phone (style.css), where it is a bar over the list.
      mp.querySelector('[data-mp-foot]').classList.toggle('mp__foot--idle', !two && !n);
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
})();
