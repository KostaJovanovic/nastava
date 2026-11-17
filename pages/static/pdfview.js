/* The site's PDF viewer (docs/PLAN-pdf.md): our own PDFs, on every device and in the app, drawn by PDF.js
   (static/pdf/, pdfjs-dist 6.5.438's legacy build: Android's older WebViews, loaded with the first PDF). site.js imports this module and calls open(). */
const BASE = '/static/pdf/';
const V = '?v=6.5.438-legacy';  // a new PDF.js gets a new one: no cache keeps the old
const d = document;
let lib = null;
const load = () => lib || (lib = (async () => {
  const css = d.createElement('link');
  css.rel = 'stylesheet';
  css.href = BASE + 'pdf_viewer.css' + V;
  d.head.append(css);
  const pdfjs = await import(BASE + 'pdf.js' + V);
  pdfjs.GlobalWorkerOptions.workerSrc = BASE + 'pdf.worker.js' + V;
  globalThis.pdfjsLib = pdfjs;  // pdf_viewer.js reads the library from here
  return { pdfjs, v: await import(BASE + 'pdf_viewer.js' + V) };
})().catch((e) => { lib = null; throw e; }));

const svg = (path) => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
const ICON = {
  x: '<svg class="i" aria-hidden="true"><use href="/static/icons.svg#i-x"/></svg>',
  find: svg('<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>'),
  toc: svg('<path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/>'),
  up: svg('<path d="m6 15 6-6 6 6"/>'),
  down: svg('<path d="m6 9 6 6 6-6"/>'),
};

let cur = null;  // the open viewer

/* open(url, name, how): how.openWith() for "Otvori u aplikaciji" (the app; on the web the button downloads),
   how.fallback() for a PDF PDF.js can't show (a password, damaged): it opens the way it did before the viewer. */
export function open(url, name, how) {
  if (cur) return;
  const app = !!how.app;
  const el = d.createElement('div');
  el.className = 'pv';
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-modal', 'true');
  el.setAttribute('aria-label', name);
  el.innerHTML =
    '<div class="pv__bar">' +
      `<button type="button" class="pv__b" data-close aria-label="Zatvori" title="Zatvori">${ICON.x}</button>` +
      '<span class="pv__name"></span>' +
      '<div class="pv__ctl">' +
      '<label class="pv__page" hidden><input inputmode="numeric" enterkeyhint="go" aria-label="Idi na stranu" title="Idi na stranu"><span></span></label>' +
      `<button type="button" class="pv__b" data-toc aria-label="Sadržaj" title="Sadržaj" hidden>${ICON.toc}</button>` +
      `<button type="button" class="pv__b" data-find aria-label="Pretraži" title="Pretraži" aria-expanded="false">${ICON.find}</button>` +
      (app ? '<button type="button" class="btn pv__open" data-open>Otvori u aplikaciji</button>'
           : '<a class="btn pv__open" data-open>Preuzmi</a>') +
    '</div></div>' +
    '<form class="pv__find" hidden role="search">' +
      '<input type="search" placeholder="Pretraži dokument" aria-label="Pretraži dokument" enterkeyhint="search">' +
      '<span class="pv__count" aria-live="polite"></span>' +
      `<button type="button" class="pv__b" data-prev aria-label="Prethodni" title="Prethodni">${ICON.up}</button>` +
      `<button type="button" class="pv__b" data-next aria-label="Sledeći" title="Sledeći">${ICON.down}</button>` +
    '</form>' +
    '<div class="pv__load" role="progressbar" aria-label="Učitavanje…"><i></i></div>' +
    '<div class="pv__main"><nav class="pv__toc" hidden aria-label="Sadržaj"></nav>' +
    '<div class="pv__box" tabindex="-1"><div class="pdfViewer"></div></div></div>';
  const $ = (s) => el.querySelector(s);
  $('.pv__name').textContent = name;
  const openBtn = $('[data-open]');
  if (app) openBtn.onclick = () => how.openWith();
  else { openBtn.href = url; openBtn.download = name; }

  const back = d.activeElement;
  const box = $('.pv__box'), bar = $('.pv__load > i');
  d.body.append(el);
  d.documentElement.classList.add('pv-on');
  // Back (Android's, the browser's) closes the viewer: it has a history entry of its own.
  history.pushState({ pv: 1 }, '');
  const v = cur = { el, task: null, closed: false };

  let viewer, bus, link;
  const key = 'pdf:' + new URL(url, location.href).pathname;

  const teardown = () => {
    if (v.closed) return;
    v.closed = true;
    cur = null;
    removeEventListener('popstate', onPop);
    if (v.task) v.task.destroy();
    el.remove();
    d.documentElement.classList.remove('pv-on');
    if (back && back.focus) back.focus({ preventScroll: true });
    if (v.after) v.after();
  };
  const onPop = () => teardown();
  addEventListener('popstate', onPop);
  const close = () => { if (!v.closed) history.back(); };
  // After the Back that closes the viewer: a navigation started before it would race it.
  const fail = () => { if (v.closed) return; v.after = how.fallback; close(); };
  $('[data-close]').onclick = close;

  // Find: every match highlighted, the current one stronger (PDF.js's "selected") and scrolled to.
  const findForm = $('.pv__find'), findIn = findForm.querySelector('input'), count = $('.pv__count');
  const find = (type, prev) => {
    if (!bus) return;
    bus.dispatch('find', { source: v, type, query: findIn.value, caseSensitive: false, entireWord: false,
      highlightAll: true, findPrevious: !!prev, matchDiacritics: false });
  };
  const showFind = (on) => {
    findForm.hidden = !on;
    $('[data-find]').setAttribute('aria-expanded', on);
    if (on) { findIn.focus(); findIn.select(); }
    else { findIn.value = ''; count.textContent = ''; find(''); box.focus({ preventScroll: true }); }
  };
  $('[data-find]').onclick = () => showFind(findForm.hidden);
  findIn.addEventListener('input', () => find(''));
  findForm.addEventListener('submit', (e) => e.preventDefault());
  findIn.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); find('again', e.shiftKey); }
  });
  $('[data-prev]').onclick = () => find('again', true);
  $('[data-next]').onclick = () => find('again', false);

  const toc = $('.pv__toc');
  $('[data-toc]').onclick = () => {
    toc.hidden = !toc.hidden;
    $('[data-toc]').setAttribute('aria-expanded', !toc.hidden);
  };

  const pageIn = $('.pv__page input'), pageOf = $('.pv__page span');
  const go = () => {
    const n = parseInt(pageIn.value, 10);
    if (viewer && n >= 1 && n <= viewer.pagesCount) viewer.currentPageNumber = n;
    else if (viewer) pageIn.value = viewer.currentPageNumber;
    pageIn.blur();
  };
  pageIn.addEventListener('change', go);
  pageIn.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); go(); } });
  pageIn.addEventListener('focus', () => pageIn.select());

  // Keys, kept from the site's own (/ j k): Esc closes the find, then the viewer; Ctrl+F finds; arrows turn pages.
  const onKey = (e) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(e.target.tagName);
    if (e.key === 'Escape') {
      e.preventDefault();
      if (!findForm.hidden) showFind(false); else if (!toc.hidden) toc.hidden = true; else close();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault(); showFind(true);
    } else if (!typing && viewer && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); viewer.nextPage(); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); viewer.previousPage(); }
      else if (e.key === 'Home') { e.preventDefault(); viewer.currentPageNumber = 1; }
      else if (e.key === 'End') { e.preventDefault(); viewer.currentPageNumber = viewer.pagesCount; }
    }
    e.stopPropagation();
  };
  el.addEventListener('keydown', onKey);
  box.focus({ preventScroll: true });

  // Zoom: pinch and Ctrl+wheel (a laptop's touchpad pinch too) around the fingers or the pointer, drawn sharp again
  // when it stops; a double tap toggles between the page's width and twice it.
  const zoom = (f, x, y) => viewer && viewer.updateScale({ scaleFactor: f, origin: [x, y], drawingDelay: 300 });
  box.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    zoom(Math.exp(-e.deltaY / (e.deltaMode ? 10 : 300)), e.clientX, e.clientY);
  }, { passive: false });
  let pinch = 0, tap = 0;
  const dist = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
  box.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) { pinch = dist(e.touches); e.preventDefault(); return; }
    if (e.touches.length !== 1 || !viewer) return;
    const now = Date.now(), t = e.touches[0];
    if (now - tap < 300) {
      e.preventDefault();
      tap = 0;
      if (viewer.currentScaleValue === 'page-width') zoom(2, t.clientX, t.clientY);
      else viewer.currentScaleValue = 'page-width';
    } else tap = now;
  }, { passive: false });
  box.addEventListener('touchmove', (e) => {
    if (e.touches.length !== 2 || !pinch) return;
    e.preventDefault();
    const now = dist(e.touches);
    zoom(now / pinch, (e.touches[0].clientX + e.touches[1].clientX) / 2, (e.touches[0].clientY + e.touches[1].clientY) / 2);
    pinch = now;
  }, { passive: false });
  box.addEventListener('touchend', (e) => { if (e.touches.length < 2) pinch = 0; });

  load().then(async ({ pdfjs, v: V }) => {
    if (v.closed) return;
    bus = new V.EventBus();
    link = new V.PDFLinkService({ eventBus: bus, externalLinkTarget: V.LinkTarget.BLANK, externalLinkRel: 'noopener' });
    const findController = new V.PDFFindController({ eventBus: bus, linkService: link });
    viewer = new V.PDFViewer({ container: box, eventBus: bus, linkService: link, findController,
      removePageBorders: false });
    link.setViewer(viewer);

    bus.on('pagesinit', () => {
      viewer.currentScaleValue = 'page-width';
      let last = 0;
      try { last = +localStorage.getItem(key) || 0; } catch (e) {}
      if (last > 1 && last <= viewer.pagesCount) viewer.currentPageNumber = last;
      pageOf.textContent = '/ ' + viewer.pagesCount;
      pageIn.value = viewer.currentPageNumber;
      pageIn.closest('label').hidden = false;
    });
    bus.on('pagechanging', ({ pageNumber }) => {
      pageIn.value = pageNumber;
      pageIn.closest('label').setAttribute('aria-label', `Strana ${pageNumber} od ${viewer.pagesCount}`);
      try { localStorage.setItem(key, pageNumber); } catch (e) {}
    });
    const counted = ({ matchesCount: m, state }) => {
      if (!findIn.value) { count.textContent = ''; return; }
      if (state === V.FindState?.NOT_FOUND || (m && !m.total)) { count.textContent = 'Nema rezultata'; return; }
      if (m && m.total) count.textContent = `${m.current} od ${m.total}`;
    };
    bus.on('updatefindmatchescount', counted);
    bus.on('updatefindcontrolstate', counted);

    const task = v.task = pdfjs.getDocument({ url, wasmUrl: BASE + 'wasm/', standardFontDataUrl: BASE + 'standard_fonts/',
      isEvalSupported: false });
    task.onPassword = () => fail();
    task.onProgress = ({ loaded, total }) => { if (total) bar.style.width = Math.min(100, loaded / total * 100) + '%'; };
    const doc = await task.promise;
    if (v.closed) return;
    $('.pv__load').hidden = true;
    viewer.setDocument(doc);
    link.setDocument(doc);

    const outline = await doc.getOutline().catch(() => null);
    if (v.closed || !outline || !outline.length) return;
    const list = (items) => {
      const ul = d.createElement('ul');
      for (const it of items) {
        const li = d.createElement('li'), b = d.createElement('button');
        b.type = 'button';
        b.textContent = it.title;
        b.onclick = () => {
          if (it.dest) link.goToDestination(it.dest);
          else if (it.url) window.open(it.url, '_blank', 'noopener');
          toc.hidden = true;
        };
        li.append(b);
        if (it.items && it.items.length) li.append(list(it.items));
        ul.append(li);
      }
      return ul;
    };
    toc.append(list(outline));
    $('[data-toc]').hidden = false;
  }).catch(() => fail());
}
