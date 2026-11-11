(async () => {
  // Teams export: every channel of every class you are in, all messages (posts and replies) and each class's
  // members with their role (owner = teacher), saved as teams-export.json in Downloads. Read only; prints no tokens.
  const toks = {};
  for (const store of [localStorage, sessionStorage]) {
    for (let i = 0; i < store.length; i++) {
      let v;
      try { v = JSON.parse(store.getItem(store.key(i))); } catch { continue; }
      if (v && v.secret && v.target) for (const t of String(v.target).split(' ')) toks[t.split('/')[2] || t] = v.secret;
    }
  }
  const token = host => Object.entries(toks).find(([t]) => t.includes(host))?.[1];
  const region = 'emea', chat = `${location.origin}/api/chatsvc/${region}/v1`;
  const get = async (url, host) => {
    const r = await fetch(url, {headers: {Authorization: `Bearer ${token(host)}`}});
    if (!r.ok) throw new Error(`${r.status} ${url.slice(0, 120)}`);
    return r.json();
  };
  const out = {exported: new Date().toISOString(), errors: [], teams: []};

  // The classes and their channels: Teams' own list, else Graph.
  let teams = [];
  try {
    const csa = await get(`${location.origin}/api/csa/${region}/api/v2/teams/users/me?isPrefetch=false&enableMembershipSummary=true`, 'chatsvcagg');
    teams = (csa.teams || []).map(t => ({name: t.displayName, thread: t.id, groupId: t.teamSiteInformation?.groupId || t.groupId,
      channels: (t.channels || [{id: t.id, displayName: 'General'}]).map(c => ({id: c.id, name: c.displayName}))}));
  } catch (e) {
    out.errors.push('csa: ' + e.message);
    const joined = await get('https://graph.microsoft.com/v1.0/me/joinedTeams', 'graph.microsoft.com');
    for (const t of joined.value) {
      const chans = await get(`https://graph.microsoft.com/v1.0/teams/${t.id}/channels`, 'graph.microsoft.com');
      const general = chans.value.find(c => c.displayName === 'General') || chans.value[0];
      teams.push({name: t.displayName, thread: general?.id, groupId: t.id, channels: chans.value.map(c => ({id: c.id, name: c.displayName}))});
    }
  }
  console.log(`${teams.length} classes, ${teams.reduce((n, t) => n + t.channels.length, 0)} channels`);

  for (const t of teams) {
    // Members and roles (Admin = owner): who is a teacher.
    try {
      const th = await get(`${chat}/threads/${encodeURIComponent(t.thread)}?view=msnp24Equivalent`, 'ic3.teams.office.com');
      t.members = (th.members || []).map(m => ({id: m.id, role: m.role, name: m.friendlyName || m.userDisplayName || null}));
    } catch (e) { out.errors.push(`members ${t.name}: ${e.message}`); }
    for (const c of t.channels) {
      c.messages = [];
      let url = `${chat}/users/ME/conversations/${encodeURIComponent(c.id)}/messages?view=msnp24Equivalent|supportsMessageProperties&pageSize=200&startTime=1`;
      try {
        for (let page = 0; url && page < 200; page++) {
          const j = await get(url, 'ic3.teams.office.com');
          c.messages.push(...(j.messages || []));
          const next = j._metadata?.backwardLink;
          // The next page's link is on the chat host; the same request through this page's origin.
          url = next && (j.messages || []).length ? next.replace(/^https:\/\/[^/]+\/v1/, chat) : null;
        }
      } catch (e) { out.errors.push(`messages ${t.name} / ${c.name}: ${e.message}`); }
      console.log(`${t.name} / ${c.name}: ${c.messages.length} messages`);
    }
    out.teams.push(t);
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out)], {type: 'application/json'}));
  a.download = 'teams-export.json';
  document.body.appendChild(a);
  a.click();
  console.log('Done. Errors:', out.errors.length ? out.errors : 'none');
})();
