(async () => {
  // Teams files, every class you are in: each one's SharePoint library as one zip in Downloads ("<name> (<group>).zip"),
  // read with this page's own sign-in. teams-files.js, but for all your classes, not only teams.py's CLASSES. The
  // sign-in stays in the page: only the files are saved. Not the recordings, nor a file over 95 MB (GitHub Pages' limit).
  const MAX = 95 * 2 ** 20, SKIP = /(^|\/)(Recordings|Snimci)\//i, GRAPH = 'https://graph.microsoft.com/v1.0';

  const toks = {};
  let token;
  for (const store of [localStorage, sessionStorage]) {
    for (let i = 0; i < store.length; i++) {
      let v;
      try { v = JSON.parse(store.getItem(store.key(i))); } catch { continue; }
      if (!v || !v.secret || !v.target) continue;
      for (const t of String(v.target).split(' ')) toks[t.split('/')[2] || t] = v.secret;
      if (/\b(Files|Sites)\.Read(Write)?\.All\b/.test(v.target) && /graph\.microsoft\.com|AppCatalog/.test(v.target)) token = v.secret;
    }
  }
  // Teams asks for the files' sign-in only once a Files tab is opened.
  if (!token) return console.log('No sign-in for files in this page yet: open any class, its Files tab (Datoteke), wait for the list, then run this again.');
  const get = async url => {
    const r = await fetch(url, {headers: {Authorization: `Bearer ${token}`}});
    if (!r.ok) throw new Error(`${r.status} ${url.slice(0, 120)}`);
    return r.json();
  };

  // The classes you are in: Teams' own list (as teams-export.js), else Graph's.
  let classes = [];
  try {
    const agg = Object.entries(toks).find(([t]) => t.includes('chatsvcagg'))?.[1];
    const r = await fetch(`${location.origin}/api/csa/emea/api/v2/teams/users/me?isPrefetch=false&enableMembershipSummary=true`,
      {headers: {Authorization: `Bearer ${agg}`}});
    if (!r.ok) throw new Error(r.status);
    classes = ((await r.json()).teams || []).map(t => ({name: t.displayName, group: t.teamSiteInformation?.groupId || t.groupId}));
  } catch (e) {
    classes = (await get(`${GRAPH}/me/joinedTeams`)).value.map(t => ({name: t.displayName, group: t.id}));
  }
  classes = classes.filter(c => c.group);
  console.log(`${classes.length} classes`);

  // A zip without compression (the PDFs barely shrink): its parts, then its directory.
  const CRC = Array.from({length: 256}, (_, n) => { for (let k = 0; k < 8; k++) n = n & 1 ? 0xEDB88320 ^ (n >>> 1) : n >>> 1; return n >>> 0; });
  const crc32 = data => { let c = -1; for (let i = 0; i < data.length; i++) c = CRC[(c ^ data[i]) & 255] ^ (c >>> 8); return (c ^ -1) >>> 0; };
  const zip = files => {
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
    return new Blob([...parts, ...dir, end.buffer], {type: 'application/zip'});
  };

  for (const {name, group} of classes) {
    try {
      const drive = (await get(`${GRAPH}/groups/${group}/drive`)).id;
      const files = [], folders = [['', `${GRAPH}/drives/${drive}/root/children`]];
      while (folders.length) {
        let [prefix, url] = folders.pop();
        while (url) {
          const page = await get(url);
          for (const item of page.value) {
            const path = prefix + item.name;
            if (item.folder) folders.push([path + '/', `${GRAPH}/drives/${drive}/items/${item.id}/children`]);
            else if (SKIP.test(path) || item.size > MAX) console.log(`  skipped ${path} (${(item.size / 2 ** 20).toFixed(0)} MB)`);
            else {
              // The file's own pre-signed address (Graph's /content redirects, which a page cannot follow with its sign-in).
              const r = await fetch(item['@microsoft.graph.downloadUrl']);
              if (!r.ok) throw new Error(`${r.status} ${path}`);
              files.push({name: path, data: new Uint8Array(await r.arrayBuffer())});
            }
          }
          url = page['@odata.nextLink'];
        }
      }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(zip(files));
      a.download = `${name.replace(/[\\/:*?"<>|]+/g, '_').slice(0, 80)} (${group.slice(0, 8)}).zip`;
      document.body.appendChild(a);
      a.click();
      console.log(`${name}: ${files.length} files, ${(files.reduce((s, f) => s + f.data.length, 0) / 2 ** 20).toFixed(1)} MB`);
    } catch (e) { console.log(`${name}: ${e.message}`); }
  }
  console.log('Done.');
})();
