(async () => {
  // Moodle export: the course whose page is open (course/view.php?id=N), as one zip in Downloads: every section's
  // activities, each view page's text (page.html) and every file it links on this Moodle, the forums' discussions,
  // and index.json (sections, activities, links, labels). Read with this page's own sign-in: enrol in the course first.
  // Not a file over 95 MB (GitHub Pages' limit), nor anything outside this Moodle (a URL activity's target is listed).
  const course = new URL(location.href).searchParams.get('id');
  if (!/\/course\/view\.php$/.test(location.pathname) || !course) return console.log('Open the course page (course/view.php?id=…) first.');
  const root = location.href.slice(0, location.href.indexOf('/course/view.php'));
  const MAX = 95 * 2 ** 20;
  const clean = s => (s || '').replace(/[\\/:*?"<>|\u0000-\u001f]+/g, '_').replace(/\s+/g, ' ').trim().slice(0, 100) || '_';
  const text = el => { if (!el) return ''; const c = el.cloneNode(true); c.querySelectorAll('.accesshide, .sr-only').forEach(x => x.remove()); return c.textContent.replace(/\s+/g, ' ').trim(); };
  const page = async url => {
    const r = await fetch(url, {credentials: 'include'});
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return new DOMParser().parseFromString(await r.text(), 'text/html');
  };
  const main = doc => doc.querySelector('#region-main') || doc.body;

  const files = [], seen = new Set(), errors = [];
  const add = (name, data) => {
    let n = name, i = 1;
    while (files.some(f => f.name === n)) n = name.replace(/(\.[^./]*)?$/, ` (${++i})$1`);
    files.push({name: n, data});
  };
  // A file on this Moodle (pluginfile.php), once per address.
  const download = async (url, dir) => {
    const u = new URL(url, root);
    if (u.origin !== location.origin || !u.pathname.includes('/pluginfile.php/')) return null;
    u.searchParams.delete('forcedownload');
    const key = u.href;
    if (seen.has(key)) return null;
    seen.add(key);
    try {
      const r = await fetch(u, {credentials: 'include'});
      if (!r.ok) throw new Error(r.status);
      if (+r.headers.get('content-length') > MAX) { errors.push(`too big: ${key}`); return null; }
      const data = new Uint8Array(await r.arrayBuffer());
      if (data.length > MAX) { errors.push(`too big: ${key}`); return null; }
      const name = `${dir}/${clean(decodeURIComponent(u.pathname.split('/').pop()))}`;
      add(name, data);
      return name;
    } catch (e) { errors.push(`${e.message} ${key}`); return null; }
  };
  const linked = async (el, dir) => {
    const out = [];
    for (const a of el.querySelectorAll('a[href*="pluginfile.php"], img[src*="pluginfile.php"]')) {
      const n = await download(a.href || a.src, dir);
      if (n) out.push(n);
    }
    return out;
  };
  const save = (name, html) => add(name, new TextEncoder().encode(`<!doctype html><meta charset=utf-8>${html}`));

  // The course page, and each section's own page when the course shows one section per page.
  const first = await page(location.href);
  const docs = [first];
  const sectionLinks = [...new Set([...first.querySelectorAll(`a[href*="course/view.php?id=${course}&section="]`)].map(a => a.href))];
  for (const s of sectionLinks) docs.push(await page(s));
  const index = {course: text(first.querySelector('h1')) || document.title, url: location.href, exported: new Date().toISOString(), sections: [], errors};
  const done = new Set();
  save('course.html', main(first).innerHTML);

  let sn = 0;
  for (const doc of docs) {
    for (const sec of doc.querySelectorAll('li.section, [data-for="section"]')) {
      // An activity or section once, though the course page and a section's page both show it.
      const id = el => el.id || el.dataset.id || el.querySelector('a[href]')?.href || el.textContent;
      if (done.has('s' + id(sec))) continue;
      done.add('s' + id(sec));
      const acts = [...new Set(sec.querySelectorAll('li.activity, [data-for="cmitem"]'))].filter(a => !done.has(id(a)));
      const title = text(sec.querySelector('.sectionname, h3')) || `Sekcija ${sn}`;
      const summary = sec.querySelector('.summary, .summarytext');
      if (!acts.length && !text(summary)) continue;
      const dir = `${String(sn++).padStart(2, '0')} ${clean(title)}`;
      const section = {title, summary: summary?.innerHTML.trim() || '', activities: []};
      index.sections.push(section);
      if (summary) await linked(summary, dir);
      for (const act of acts) {
        done.add(id(act));
        const mod = (act.className.match(/modtype_(\w+)/) || [])[1] || 'unknown';
        const a = act.querySelector('a.aalink, .activityname a, .activityinstance a');
        const name = text(act.querySelector('.instancename')) || text(a) || mod;
        const item = {type: mod, name, url: a?.href || null, files: []};
        section.activities.push(item);
        const adir = `${dir}/${clean(name)}`;
        console.log(`${mod}: ${name}`);
        try {
          if (mod === 'label' || !a) {
            item.html = (act.querySelector('.contentwithoutlink, .activity-altcontent, .description') || act).innerHTML.trim();
            item.files = await linked(act, dir);
            continue;
          }
          item.files.push(...await linked(act, adir));  // the description on the course page
          if (mod === 'resource') {
            // redirect=1: straight to the file; an embedded one stays a page with the file in it.
            const r = await fetch(`${a.href}&redirect=1`, {credentials: 'include'});
            if (r.ok && r.url.includes('/pluginfile.php/')) { const n = await download(r.url, adir); if (n) item.files.push(n); continue; }
          }
          const view = await page(a.href);
          const body = main(view);
          save(`${adir}/page.html`, body.innerHTML);
          item.files.push(...await linked(body, adir));
          if (mod === 'url') item.target = (body.querySelector('.urlworkaround a, .resourcecontent a, object a') || {}).href || null;
          if (mod === 'forum') {
            // Each discussion's page (the first 100 discussions: a forum's own paging is not followed).
            item.discussions = [];
            for (const d of [...new Set([...body.querySelectorAll('a[href*="discuss.php?d="]')].map(x => x.href.replace(/#.*/, '')))]) {
              const dv = main(await page(d));
              const dt = text(dv.querySelector('h3, h2')) || d.split('d=')[1];
              save(`${adir}/${clean(dt)}.html`, dv.innerHTML);
              item.discussions.push({title: dt, url: d, files: await linked(dv, `${adir}/${clean(dt)}`)});
            }
          }
        } catch (e) { errors.push(`${mod} ${name}: ${e.message}`); }
      }
    }
  }
  add('index.json', new TextEncoder().encode(JSON.stringify(index, null, 2)));

  // A zip without compression (as teams-files.js): its parts, then its directory.
  const CRC = Array.from({length: 256}, (_, n) => { for (let k = 0; k < 8; k++) n = n & 1 ? 0xEDB88320 ^ (n >>> 1) : n >>> 1; return n >>> 0; });
  const crc32 = data => { let c = -1; for (let i = 0; i < data.length; i++) c = CRC[(c ^ data[i]) & 255] ^ (c >>> 8); return (c ^ -1) >>> 0; };
  const parts = [], dir = [];
  let offset = 0;
  for (const {name, data} of files) {
    const n = new TextEncoder().encode(name), crc = crc32(data);
    const head = (sig, extra) => {
      const b = new DataView(new ArrayBuffer(extra ? 46 : 30));
      let p = 0;
      const u32 = x => { b.setUint32(p, x, true); p += 4; }, u16 = x => { b.setUint16(p, x, true); p += 2; };
      u32(sig); if (extra) u16(20); u16(20); u16(0x0800); u16(0); u16(0); u16(0x21);  // UTF-8 names, stored, 1980-01-01
      u32(crc); u32(data.length); u32(data.length); u16(n.length); u16(0);
      if (extra) { u16(0); u16(0); u16(0); u32(0); u32(offset); }
      return b.buffer;
    };
    parts.push(head(0x04034b50, false), n, data);
    dir.push(head(0x02014b50, true), n);
    offset += 30 + n.length + data.length;
  }
  const size = dir.reduce((s, x) => s + x.byteLength, 0);
  const end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
  end.setUint32(12, size, true); end.setUint32(16, offset, true);
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([...parts, ...dir, end.buffer], {type: 'application/zip'}));
  link.download = `moodle-${location.hostname.split('.')[0]}-${course}.zip`;
  document.body.appendChild(link);
  link.click();
  console.log(`Done: ${files.length} files, ${(files.reduce((s, f) => s + f.data.length, 0) / 2 ** 20).toFixed(1)} MB` +
    (errors.length ? `; ${errors.length} problems (index.json "errors"):\n` + errors.join('\n') : ''));
})();
