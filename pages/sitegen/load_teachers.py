"""The teachers: the faculty's list, their history, photos, biographies, bibliographies, departments."""

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from html import unescape
from nastavnici import photo_urls
from translit import fold
from .clean import clean_html
from .known import BIB_KINDS, FORUM_ACCOUNT, OTHER_TEACHERS, RANKS, SHORT_SURNAME
from .output import HERE
from .text import LINK, azbuka, set_hrefs, slug, strip_tags


def photo_path(url, kind):
    """A stored photo's path in the site: /foto/<hash of its source URL>.jpg."""
    return f"/foto/{hashlib.sha1(url.encode()).hexdigest()[:16]}.{kind.split('/')[1].replace('jpeg', 'jpg')}"


def write_photos(db, site):
    """The teacher photos nastavnici.py stored, as files: the faculty removes a departed teacher's."""
    (site / "foto").mkdir(parents=True, exist_ok=True)
    for url, kind, data in db.execute("SELECT url, type, data FROM photos"):
        (site / photo_path(url, kind).lstrip("/")).write_bytes(data)


HISTORY = HERE.resolve().parent / "data" / "nastavnici-istorija.jsonl"

# Portraits of teachers without one, from the monograph, the old site, In memoriam, Wikipedia, SANU: page id, the
# image's key in the photos table, the page it is on and its caption there.
FOTOS = HISTORY.with_name("nastavnici-foto.jsonl")

# Biographies from the faculty's 2023 monograph, its own words: page id, the paragraphs about them, each with its page.
BIOS = HISTORY.with_name("nastavnici-biografije.jsonl")

# A short biography of each teacher, about two paragraphs, written once (by Claude, reviewed) from that teacher's
# sources on this site: page id, name, the paragraphs.
SUMMARIES = HISTORY.with_name("nastavnici-sazetak.jsonl")


def load_history(teachers):
    """nastavnici-istorija.jsonl: teachers from the faculty's past (its 2023 monograph, In Memoriam, its old site
    2005-2014 on the Wayback Machine, Wikipedia, election reports), each source quoted. A line with a teacher id adds
    its sources to that teacher's page; the others are new pages, among the departed."""
    if not HISTORY.exists():
        return []
    by_id, new = {t["id"]: t for t in teachers}, []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        h = json.loads(line)
        for s in h["sources"]:
            m = re.search(r"Monografija.*#page=(\d+)", s["url"])
            # The PDF's page 307 is the book's printed page 305.
            s["page"] = m and int(m[1]) - 2
        # The written sources first, the old site's pages last; each kind by its years.
        kinds = ["referat", "in-memoriam", "monografija", "wikipedia", "web", "stari-sajt"]
        h["sources"].sort(
            key=lambda s: (kinds.index(s["kind"]) if s["kind"] in kinds else 4, s["page"] or 0, re.findall(r"\d{4}", s["years"] or ""))
        )
        if h["teacher"]:
            if h["teacher"] in by_id:
                by_id[h["teacher"]]["history"] = h
            continue
        # last_seen: the last year a source names, so the archive orders them after the recently departed.
        years = re.findall(r"\d{4}", h["years"] or "")
        new.append(
            dict(
                id=f"ist-{slug(h['name'] + ' ' + (h['life'] or ''))}",
                name=h["name"],
                full_name=h["name"],
                title=h["title"] or "",
                katedra=h["katedra"],
                katedra_id=None,
                office=None,
                email=None,
                username=None,
                phone=None,
                hours=None,
                research=((h.get("card") or {}).get("fields") or {}).get("research"),
                emeritus=0,
                html=None,
                first_seen=None,
                last_seen=max(years) if years else str((h.get("span") or {}).get("to") or "0000"),
                gone=1,
                photo=None,
                subjects=[],
                history=h,
                suffix=h["life"] and slug(h["life"]),
            )
        )
    return new


def load_teachers(db, subjects):
    """The teachers (nastavnici.py), each subject linked to its archive page when the board has its code."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'teachers'").fetchone():
        return []
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    taught = defaultdict(list)
    for r in db.execute("SELECT * FROM teacher_subjects ORDER BY name"):
        taught[r["teacher"]].append(dict(code=r["code"], name=r["name"], subj=by_code.get(r["code"])))
    # A teacher who left the faculty's list (gone) keeps their page and their posts' links; only the list hides them.
    teachers = [dict(t, subjects=taught[t["id"]]) for t in map(dict, db.execute("SELECT * FROM teachers ORDER BY rowid"))]
    teachers += [dict(t, subjects=[]) for t in OTHER_TEACHERS]
    teachers += load_history(teachers)
    for t in teachers:
        t["username"] = FORUM_ACCOUNT.get(t["username"], t["username"])
    set_hrefs(teachers, lambda t: f"/nastavnik/{slug(t['name'])}/")
    local = {url: photo_path(url, kind) for url, kind in db.execute("SELECT url, type FROM photos")}
    # The faculty's placeholder (a silhouette, 19 teachers in 2026-11): the same file under several teachers' URLs.
    # Theirs counts as no photo, so a portrait found elsewhere shows instead, else the initials.
    same = defaultdict(set)
    for url, data in db.execute("SELECT url, data FROM photos WHERE url LIKE '%/_media/fakultet/nastavnici/%'"):
        same[hashlib.sha1(data).digest()].add(url)
    placeholder = {u for urls in same.values() if len({u.split("?")[0] for u in urls}) >= 3 for u in urls}
    # So is one URL kept as several departed teachers' photo (masinac.org's nema_slike.jpg).
    placeholder |= {u for u, n in Counter(t.get("photo") for t in teachers if t.get("photo")).items() if n >= 3}
    fotos = {f["id"]: f for f in map(json.loads, FOTOS.read_text(encoding="utf-8").splitlines())} if FOTOS.exists() else {}
    bios = {b["id"]: b["paras"] for b in map(json.loads, BIOS.read_text(encoding="utf-8").splitlines())} if BIOS.exists() else {}
    sums = {b["id"]: b["paras"] for b in map(json.loads, SUMMARIES.read_text(encoding="utf-8").splitlines())} if SUMMARIES.exists() else {}
    # The last day the teachers' list was read: one not on it then (gone, or a department's staff nastavnici.py keeps)
    # has no profile at the faculty.
    listed_day = max((t["last_seen"] for t in teachers if not t["gone"] and not t.get("source")), default="")
    for t in teachers:
        t["off_list"] = t["gone"] or t["last_seen"] < listed_day
        t["bio"] = bios.pop(t["id"], None)
        t["summary"] = sums.pop(t["id"], None)
        # The photo from our copy (write_photos); a listed teacher's not copied yet from the faculty, one off the
        # list none (the faculty took it down).
        thumb, photo = photo_urls(t["html"], t.get("photo"))
        t["thumb"] = local.get(thumb) or (None if t["off_list"] else thumb)
        t["photo"] = local.get(photo) or (None if t["off_list"] else photo)
        if photo in placeholder or thumb in placeholder:
            t["thumb"] = t["photo"] = None
        # One without: a portrait found elsewhere (nastavnici-foto.jsonl), its source shown among the page's sources.
        f = fotos.pop(t["id"], None)
        if f and not t["photo"] and f["image"] in local:
            t["photo"] = t["thumb"] = local[f["image"]]
            m = re.search(r"Monografija.*#page=(\d+)", f["page"])
            # One the user saved from a search has no page to cite.
            t["photo_src"] = f["page"] and dict(f, book_page=m and int(m[1]) - 2)
        # 'Драган С. Алексендрић' -> 'Драган Алексендрић': the shown name, without the father's initial.
        # Their own page names them in full (page_name); elsewhere some go by their first surname only (SHORT_SURNAME).
        t["page_name"] = t["shown"] = re.sub(r" \w\.(?= )", "", t["name"])
        if t["id"] in SHORT_SURNAME:
            t["shown"] = t["shown"].split("-")[0]
        # The title's rank, for the list's order by title (site.js sorts the digit as text); an unknown title last.
        t["rank"] = RANKS.index(t["title"]) if t["title"] in RANKS else 9
    for name, left in (("nastavnici-foto.jsonl", fotos), ("nastavnici-biografije.jsonl", bios), (SUMMARIES.name, sums)):
        if left:
            print(f"{name}: no page for {', '.join(left)}", file=sys.stderr)
    # By surname, then given name, in the order of the Serbian alphabet (as the faculty's list).
    return sorted(teachers, key=lambda t: (azbuka(t["name"].split()[-1]), azbuka(t["name"])))


def department_intro(html):
    """A department page of the faculty's wiki (nastavnici.py departments) as (its text, its own site): the text
    before its staff list, without the title; the site is the link in its side box ('веб сајт катедре')."""
    m = re.search(r'<div class="wrap_related[^"]*"[^>]*>(.*?)</div>', html, re.S)
    own = LINK.search(m[1]) if m else None
    text = html.split('<div class="plugin_include_content', 1)[0]
    text = re.sub(r"<h1[^>]*>.*?</h1>", "", text[: m.start()] + text[m.end() :] if m else text, count=1, flags=re.S)
    text = clean_html(text).strip()
    return text if strip_tags(text) else "", own and unescape(own[1])


def bibliography(html, works, name):
    """A teacher's works as one list, newest first: the faculty profile's bibliography (each entry 'Authors (year).
    <a>Title</a>, venue.<br/> publisher, ISSN, <a>DOI</a>, M21.') and the repository's works (nastavnici-istorija.jsonl),
    the same work once (by its repository link, else its title). An entry: kind, authors [(name, is them)], year,
    title, url, venue, doi, m (the ministry's category)."""
    sur = set(fold(name).replace("-", " ").split()[1:]) if name else set()  # 'Татјана М. Лазовић-Капор': lazovic, kapor
    first = fold(name)[:1]
    out, seen = [], set()
    start = (html or "").find('id="nastavnici-bibliografija"')
    for m in re.finditer(r"<h3[^>]*>(.*?)</h3>(.*?)(?=<h3|$)", (html or "")[start:] if start >= 0 else "", re.S):
        kind = next((k for key, k in BIB_KINDS if key in m[1]), None)
        for p in re.findall(r"<p>(.*?)</p>", m[2], re.S):
            head, _, tail = p.partition("<br/>")
            e = re.match(r"\s*(.*?)\s*\((\d{4})\)\.\s*(.*)", head, re.S)
            if not e:
                continue
            link = LINK.search(e[3])
            title = strip_tags(link[2]) if link else strip_tags(e[3]).split(", ")[0]
            venue = strip_tags(e[3][link.end() :] if link else ", ".join(strip_tags(e[3]).split(", ")[1:])).strip(" ,.")
            doi = re.search(r'href="https?://(?:dx\.)?doi\.org/([^"]+)"', tail)
            mc = re.search(r"\b(M\d+[a-z]?)\.?\s*$", strip_tags(tail))
            # 'Lazović Tatjana', 'Spasojević Brkić Vesna', 'Momčilović Dejan B.': surname first, then the given name.
            me = lambda w: bool(w) and w[0] in sur and any(x[:1] == first for x in w[1:])
            authors = [(a, me(fold(a).replace("-", " ").split())) for a in strip_tags(e[1]).split(", ") if a]
            out.append(
                dict(
                    kind=kind,
                    authors=authors,
                    year=int(e[2]),
                    title=title,
                    url=link and unescape(link[1]),
                    venue=venue,
                    doi=doi and unescape(doi[1]),
                    m=mc and mc[1],
                )
            )
    for e in out:
        seen |= {e["url"], fold(e["title"])}
    for w in works or ():
        if w["url"] not in seen and fold(w["title"]) not in seen:
            out.append(
                dict(
                    kind=None, authors=[], year=w.get("year"), title=w["title"], url=w["url"], venue=w.get("source") or "", doi=None, m=None
                )
            )
    return sorted(out, key=lambda e: -(e["year"] or 0))
