# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2"]
# ///
"""Render nastava.db as a static site for GitHub Pages, with its Pagefind search index.

Usage: uv run pages/build.py <nastava.db> <out dir>
Writes <out>/site, most pages as fragments of shell.html (split_page), runs Pagefind (needs Node's npx) into
<out>/site/pagefind, then removes the hidden text Pagefind read from the item pages.
"""
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

import nh3
from jinja2 import Environment, FileSystemLoader, select_autoescape
from jinja2.utils import htmlsafe_json_dumps
from markupsafe import Markup, escape

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from studije import PAGES as STUDY_PAGES, SITE as STUDY_SITE, media_path  # noqa: E402
from nastavnici import photo_urls  # noqa: E402
BASE = "https://nastava.mas.bg.ac.rs/nastava/"
KIND = {"post": "obavestenje", "document": "dokument", "vest": "vest", "cent": "obavestenje"}
RECENT = 20
# vesti.py's site, which keeps the news' images and files (the pages link them); the home page shows the newest few.
VESTI, VESTI_HOME = "https://vesti.mas.bg.ac.rs/", 5
# A followed subject's newest topics in its novo.json (the home page's "Moji predmeti", site.js).
MINE = 10
# The Atom feeds (write_feeds): the posts in a subject's and in the whole board's, and the domain of their links.
FEED, FEED_ALL = 20, 50
SITE_URL = "https://nastava.masinci.org"
PAGEFIND = "pagefind@1.6.0"
# shortcut: a document page shows and indexes at most this much text; raise it if GitHub Pages' 1 GB allows.
PAGE_TEXT = 300_000
CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш",
               "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split()))
assert len(CYR) == 30

env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())
# The noun after a number: 1, 21 objava; 2, 3, 4, 22 objave; 5–20, 11–14 objava.
# The site's words: a topic is an "objava", one post in it a "post".
FORMS = {"objava": ("objava", "objave", "objava"), "post": ("post", "posta", "postova"),
         "odgovor": ("odgovor", "odgovora", "odgovora"), "predmet": ("predmet", "predmeta", "predmeta"),
         "nastavnik": ("nastavnik", "nastavnika", "nastavnika"), "autor": ("autor", "autora", "autora"),
         "prilog": ("prilog", "priloga", "priloga"), "preuzimanje": ("preuzimanje", "preuzimanja", "preuzimanja")}


def plural(n, word):
    one, few, many = FORMS[word]
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


env.filters["pl"] = plural
# A count as Serbian writes it: 23.692.
env.filters["n"] = lambda n: f"{n:,}".replace(",", ".")
# An ISO date (2026-11-08...) as the board writes it: 08.11.2026.
env.filters["dmy"] = lambda iso: ".".join(reversed((iso or "")[:10].split("-"))) + "." if iso else ""
# The masculine plurals among the katedre; every other name changes only a feminine '-у' (or is neuter).
KATEDRA_NOM = {"моторе": "мотори", "системе наоружања": "системи наоружања",
               "хидрауличне машине и енергетске системе": "хидрауличне машине и енергетски системи"}


def katedra(k):
    """'Катедра за математику' -> 'математика': in a list headed Katedra the prefix only repeats, and the name
    stands alone, so in the nominative."""
    rest = re.sub(r"^(Катедра|Katedra) (за|za) ", "", k or "")
    # What follows 'у' ('технологије у машинству') is in its own case: kept.
    head, at, tail = rest.partition(" у ")
    return KATEDRA_NOM.get(rest) or re.sub(r"у\b", "а", head) + at + tail


env.filters["katedra"] = katedra


def fold(s):
    """Serbian Cyrillic to Latin, no diacritics, lower case. search.js folds the query the same way."""
    s = "".join(CYR.get(ch, ch) for ch in (s or "").lower()).replace("đ", "dj")
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))


def slug(s):
    """A name as a URL part: 'Душан Љ. Ђукић' -> 'dusan-lj-djukic'."""
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


# A filter's value in a URL (?katedra=katedra-za-matematiku): Latin only, the shown text stays the name.
env.filters["slug"] = slug


def desc(text, n=160):
    """A page's description (base.html): its text on one line, cut at a word."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


LAT = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш", "a b v g d đ e ž z i j k l lj m n nj o p r s t ć u f h c č dž š".split()))


def lat(s):
    """Serbian Cyrillic to Latin, as pismo.js toLat shows a page by default: for what no script converts (the link
    previews, base.html). Љ is 'LJ' in a word of capitals, 'Lj' otherwise. Escaped text stays escaped (Markup)."""
    def letter(m):
        c, l = m[0], LAT.get(m[0].lower())
        if l is None or c == c.lower():
            return l or c
        after = m.string[m.end():m.end() + 1]
        return l.upper() if after and after != after.lower() else l[0].upper() + l[1:]
    out = re.sub(r"[Ѐ-ӿ]", letter, str(s or ""))
    return Markup(out) if isinstance(s, Markup) else out


env.filters["desc"] = desc
env.filters["lat"] = lat
# Structured data in a page (schema.org), escaped for a <script> (<, >, &, ' as \u).
env.filters["ld"] = lambda d: Markup(f'<script type="application/ld+json">{htmlsafe_json_dumps(d, ensure_ascii=False)}</script>')
env.globals["site_url"] = SITE_URL


def set_hrefs(rows, path):
    """Give each row href path(row); a name that folds the same as an earlier row's gets the row's suffix (a past
    teacher's years) or id appended. rows: in the order they first appeared, so an existing page keeps its URL when a
    namesake is added later."""
    seen = set()
    for r in rows:
        href = path(r)
        if href in seen:
            href = f"{href[:-1]}-{r.get('suffix') or r['id']}/"
        seen.add(href)
        r["href"] = href


def parse_date(*values):
    """Return (iso date or None, year or None) from the first parsable value."""
    for v in values:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", v or "")
        if m:
            return f"{m[3]}-{m[2]}-{m[1]}", int(m[3])
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v or "")
        if m:
            return m[0], int(m[1])
    return None, None


def preuzeto(text):
    """The board's English download count, in Serbian: in a post's HTML and in its plain text (the search excerpt)."""
    return re.sub(r"Downloaded (\d+) times?", r"preuzeto \1 puta", text or "")


def clean_html(html, base=BASE, local=lambda value: None):
    """Sanitize; a link that local() maps goes to this site, every other relative link to the faculty's page."""
    def attribute(tag, attr, value):
        if attr not in ("href", "src"):
            return value
        if value.startswith("data:"):
            return value if tag == "img" and value.startswith("data:image/") else None
        # Posts link relative to the board page, so attachments and images resolve to the faculty's site.
        # shortcut: board files are not hosted here; when the board deletes one, the link dies.
        # Drop the scraper's phpBB session id from the link, and the board's search highlight (hilit=, often Cyrillic).
        value = re.sub(r"([?&])hilit=[^&#]*&?", r"\1", re.sub(r"([?&])sid=[0-9a-f]+&?", r"\1", value))
        return local(value) or urljoin(base, re.sub(r"[?&]+(?=#|$)", "", value))

    # The board's attachment box is in English; in Serbian it reads right in both scripts.
    html = preuzeto(re.sub(r">\s*Attachments\s*<", ">Prilozi<", html or ""))
    return nh3.clean(html, tags=nh3.ALLOWED_TAGS | {"tfoot"}, attribute_filter=attribute,
                     url_schemes=nh3.ALLOWED_URL_SCHEMES | {"data"}, link_rel="noopener noreferrer") or None


# A board attachment after clean_html: <dl><dt><span></span> <a href>name</a></dt>[<dd>comment</dd>]<dd>(size)
# preuzeto N puta</dd></dl>.
ATTACHMENT = re.compile(r'<dl>\s*<dt>(?:<span></span>)?\s*<a href="([^"]+)"[^>]*>([^<]*)</a>\s*</dt>\s*'
                        r'(?:<dd>((?:(?!</?d[dlt]>).)*)</dd>\s*)?<dd>\(([^)<]*)\)\s*([^<]*)</dd>\s*</dl>', re.S)
# A file type's colour on its badge (style.css .att__t--*).
FILE_KINDS = {**dict.fromkeys(["pdf"], "pdf"), **dict.fromkeys(["doc", "docx", "odt", "rtf"], "doc"),
              **dict.fromkeys(["xls", "xlsx", "ods", "csv"], "xls"), **dict.fromkeys(["ppt", "pptx", "pps", "ppsx", "odp"], "ppt"),
              **dict.fromkeys(["zip", "rar", "7z"], "zip"), **dict.fromkeys(["jpg", "jpeg", "png", "gif"], "img")}


def downloads(html):
    """A post's attachments as (attachment id, file name, downloads), from clean_html's output.
    shortcut: the count is as the board showed it when the topic was last fetched (only changed or recent topics are
    fetched again); re-fetch every topic now and then if fresh counts matter."""
    return [(int(i[1]), unescape(m[2]), int(n[0]) if (n := re.search(r"\d+", m[5])) else 0)
            for m in ATTACHMENT.finditer(html or "") if (i := re.search(r"file\.php\?id=(\d+)", m[1]))]


def attachments(html):
    """A post's attachments as rows (style.css .att): the file's type as a badge, its name, its comment, its size and
    downloads. It runs on clean_html's output and only moves its parts, which are sanitized already; the type is
    letters only."""
    def row(m):
        ext = re.search(r"\.([a-z0-9]{1,5})\s*$", unescape(m[2]).lower())
        ext = ext[1] if ext else ""
        note = f'<span class="att__c">{m[3].strip()}</span>' if m[3] and m[3].strip() else ""
        return (f'<a class="att" href="{m[1]}" rel="noopener noreferrer"><span class="att__t att__t--{FILE_KINDS.get(ext, "file")}">'
                f'{ext.upper() or "FAJL"}</span><span class="att__n">{m[2]}{note}<small>{m[4]} · {m[5].strip()}</small></span></a>')
    return ATTACHMENT.sub(row, html) if html else html


def subject_name(forum_name):
    """'Цевни водови (1044)' -> 'Цевни водови': one subject for all the codes it had."""
    return " ".join(re.sub(r"\(\d+\)\s*$", "", forum_name.replace("﻿", "")).split())


def load_places(db):
    """Map each forum id to (smer, subject). A smer is a top forum; a subject merges the forums of one smer with one name.
    The subject is None for the smer's own notices."""
    forums = {r["id"]: dict(r) for r in db.execute("SELECT id, parent, name FROM forums")}
    smerovi, subjects, place = {}, {}, {}
    for f in sorted(forums.values(), key=lambda f: f["id"]):
        top = f
        while top["parent"] is not None:
            top = forums[top["parent"]]
        # label: the name as shown ('Основне академске студије - МИ'); short: its abbreviation, for URLs and matching.
        smer = smerovi.setdefault(top["id"], {"id": top["id"], "name": top["name"], "short": short_smer(top["name"]),
                                              "label": top["name"][:1].upper() + top["name"][1:]})
        if f is top:
            place[f["id"]] = (smer, None)
            continue
        name = subject_name(f["name"])
        # The lowest forum id of the merged subject names its page.
        subject = subjects.setdefault((top["id"], name), {"id": f["id"], "name": name, "smer": smer, "codes": []})
        subject["codes"] += re.findall(r"\((\d+)\)\s*$", f["name"])
        place[f["id"]] = (smer, subject)
    # The same subject name is in several smerovi, so a subject's URL has its smer's.
    set_hrefs(smerovi.values(), lambda m: f"/smer/{slug(short_smer(m['name']))}/")
    for m in smerovi.values():
        # The smer in a search URL and in the index's filter: its URL's slug ('oas-mi'), never its Cyrillic name.
        m["key"] = m["href"].strip("/").split("/")[-1]
    set_hrefs(subjects.values(), lambda s: f"{s['smer']['href'].replace('/smer/', '/predmet/', 1)}{slug(s['name'])}/")
    return place, smerovi, subjects


def load_items(db, place):
    docs = {r["id"]: dict(r) for r in db.execute("SELECT * FROM documents WHERE fetched = 1 AND error IS NULL")}
    posts = {r["id"]: dict(r) for r in db.execute("SELECT * FROM posts")}
    items = []
    for p in posts.values():
        iso, year = parse_date(p["date"], p["posted"])
        smer, subj = place.get(p["forum"], (None, None))
        html = clean_html(p["html"])
        items.append(dict(id=f"p{p['id']}", kind="post", title=p["title"], smer=smer, subj=subj,
                          subject=subj and subj["name"], date=iso, year=year,
                          topic=p["topic"], num=p["id"], when=p["date"], posted=p["posted"] or "",
                          author=p["author"], body=preuzeto(p["content"]), html=attachments(html), files=downloads(html), gone=p["gone"],
                          source_url=f"{BASE}viewtopic.php?p={p['id']}#p{p['id']}"))
    for d in docs.values():
        p = posts.get(d["post"]) or {}
        iso, year = parse_date(p.get("date"), d["uploaded_at"])
        smer, subj = place.get(p.get("forum"), (None, None))
        items.append(dict(id=f"d{d['id']}", kind="document", title=d["title"] or d["filename"], smer=smer, subj=subj, files=[],
                          subject=subj and subj["name"], topic=None, when=p.get("date"), posted=p.get("posted") or "",
                          date=iso, year=year, author=p.get("author"), body=(d["text"] or "")[:PAGE_TEXT], html=None,
                          source_url=f"{BASE}viewtopic.php?p={d['post']}#p{d['post']}" if d["post"] else None,
                          doc=dict(filename=d["filename"], size=round((d["size"] or 0) / 1024), uploaded_at=d["uploaded_at"]),
                          download_url=f"{BASE}download/file.php?id={d['id']}"))
    return items


def load_vesti(db):
    """vesti.py's news, the newest version of each, newest first. Each is also an item for pagefind_tags (no smer,
    subject or author); body: its plain text."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'vesti'").fetchone():
        return []
    cats = dict(db.execute("SELECT id, name FROM vesti_categories"))
    out = []
    for r in db.execute("SELECT * FROM vesti v WHERE modified = (SELECT max(modified) FROM vesti WHERE id = v.id) "
                        "ORDER BY date DESC"):
        iso, year = parse_date(r["date"])
        names = [cats[c] for c in json.loads(r["categories"]) if c in cats]
        title = unescape(r["title"])
        out.append(dict(id=f"v{r['id']}", kind="vest", href=f"/vest/{r['id']}/", title=title, date=iso, year=year,
                        posted=f"{r['date_gmt']}Z", cats=names, cat_keys="|".join(slug(c) for c in names),
                        find=fold(" ".join([title] + names)), html=clean_html(r["html"], VESTI),
                        body=strip_tags(r["html"])[:PAGE_TEXT], gone=r["gone"], source_url=r["link"],
                        smer=None, subj=None, subject=None, author=None, who="Mašinski fakultet"))
    return out


def board_subject(by_code, by_name, code, name, program):
    """The board's subject of a subject-book entry: the same code, else the same name in the smer of its program."""
    return by_code.get(code) or by_name.get((fold(short_smer(program.replace(" — ", " - "))), fold(name)))


def load_cent(db, smerovi, subjects):
    """cent.py's subject pages of cent.mas.bg.ac.rs, under the board's subjects. Returns (the notices as items, the
    page versions as push.json rows); each subject with pages gets s["cent"]: its pages in the site's order, each with
    its versions, newest first (render_cent).
    A page is a subject's when the highest page at or above it with a code in its header has the subject's code (a
    subpage may copy another subject's header; of two sections with one code, the one with more pages under it). The
    code is the subject book's, or, unknown there, the section's title is a book subject's name; the book entry leads
    to the board subject as in load_book. A subject the board does not have is made here, in the smer of its program,
    and that smer too when the board has none (Индустрија 4.0). Before load_book: the book links these subjects."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'cent_pages'").fetchone():
        return [], []
    versions = defaultdict(list)
    for r in db.execute("SELECT rowid AS rid, * FROM cent_pages ORDER BY id, last_seen DESC"):
        versions[r["id"]].append(dict(r))
    pages = {i: v[0] for i, v in versions.items()}
    kids = Counter(p["parent"] for p in pages.values())

    def top(p):
        found = None
        while p:
            found = p if p["code"] else found
            p = pages.get(p["parent"])
        return found

    roots = {}
    for p in pages.values():
        # A section gone from cent stays (its pages are marked gone); of two with one code, one still there wins.
        if p["code"] and top(p) is p:
            if p["code"] not in roots or (not p["gone"], kids[p["id"]]) > (not roots[p["code"]]["gone"], kids[roots[p["code"]]["id"]]):
                roots[p["code"]] = p
    book = {r["id"]: r for r in db.execute("SELECT id, name, program FROM subjects")} if db.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'subjects'").fetchone() else {}
    book_by_name = {}
    for r in book.values():
        book_by_name.setdefault(fold(r["name"]), r["id"])
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    by_name = {(fold(s["smer"]["short"]), fold(s["name"])): s for s in subjects.values()}
    smer_of = {fold(m["short"]): m for m in smerovi.values()}
    subj_of = {}
    for code, r in roots.items():
        code = code if code in book else book_by_name.get(fold(r["title"]))
        if not code:
            print(f"cent: no subject in the book for {r['link']} ({r['title']}, ID {r['code']})", file=sys.stderr)
            continue
        name, program = book[code]["name"], book[code]["program"]
        s = board_subject(by_code, by_name, code, name, program)
        if not s:
            smer_name = program.replace(" — ", " - ")
            smer_name = smer_name[:1].lower() + smer_name[1:]
            m = smer_of.get(fold(short_smer(smer_name)))
            if not m:
                m = dict(id=f"cent:{program}", name=smer_name, short=short_smer(smer_name), label=smer_name[:1].upper() + smer_name[1:])
                m["href"] = f"/smer/{slug(m['short'])}/"
                m["key"] = m["href"].strip("/").split("/")[-1]
                smerovi[m["id"]] = smer_of[fold(m["short"])] = m
            s = dict(id=f"c{code}", name=name, smer=m, codes=[code])
            s["href"] = f"{m['href'].replace('/smer/', '/predmet/', 1)}{slug(name)}/"
            if any(o["href"] == s["href"] for o in subjects.values()):
                s["href"] = f"{s['href'][:-1]}-{code}/"
            subjects[(m["id"], name)] = by_code[code] = s
        subj_of[r["id"]] = s
        # The subject's own site: cent has files no page links (older uploads, past notices' attachments).
        s.setdefault("site", r["link"])
    notices = defaultdict(list)
    for n in db.execute("SELECT * FROM cent_notices ORDER BY nid"):
        notices[n["page"]].append(dict(n))
    items, pushed = [], []
    for p in sorted(pages.values(), key=lambda p: (p["menu_order"], p["id"])):
        s = subj_of.get((top(p) or {}).get("id"))
        if not s:
            continue
        for n in notices[p["id"]]:
            day = n["date"] or n["first_seen"][:10]
            # Its date is the notice's; its time the one it was first seen, when that was the same day.
            posted = n["first_seen"] if n["first_seen"][:10] == day else f"{day}T10:00:00+00:00"
            html = clean_html(n["html"], p["link"])
            items.append(dict(id=f"c{n['nid']}", kind="cent", title=n["title"], smer=s["smer"], subj=s, subject=s["name"],
                              date=day, year=int(day[:4]), topic=f"c{n['nid']}", num=n["nid"],
                              when=f"{day[8:10]}.{day[5:7]}.{day[:4]}.", posted=posted, author="cent",
                              body=strip_tags(html), html=html, files=[], gone=n["gone"], source_url=p["link"]))
        shown, emptied = [], False
        main = f"{s['href']}cent/{p['slug']}/"
        for i, v in enumerate(versions[p["id"]]):
            html = clean_html(v["html"], p["link"]) or ""
            # The page's first heading is its name ("Резултати испита"): the title, not repeated under it.
            m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
            title = strip_tags(m[1]) if m else v["title"]
            html = html[:m.start()] + html[m.end():] if m else html
            if not strip_tags(html) and "<a " not in html:
                emptied = emptied or not shown
                continue
            # The newest version with content is the page's: a page cent emptied keeps its last content.
            href = main if not shown else f"{main}{v['first_seen'][:10]}-{v['sha'][:6]}/"
            shown.append(dict(title=title, href=href, html=html, first_seen=v["first_seen"], last_seen=v["last_seen"]))
            new = i == len(versions[p["id"]]) - 1
            pushed.append(dict(k="s", id=v["rid"], s=s["href"], n=s["name"], t=f"{title}: {'nova stranica' if new else 'izmenjeno'}",
                               u=main))
        if shown:
            s.setdefault("cent", []).append(dict(title=shown[0]["title"], link=p["link"], gone=p["gone"] or emptied, versions=shown))
    return items, pushed


# Where a subject's material is besides the board (a post links it): a service's name and its hosts.
ELSEWHERE = [("Teams", r"^(teams\.microsoft\.com|teams\.live\.com|teams\.cloud\.microsoft)$"),
             ("Classroom", r"^classroom\.google\.com$"), ("Google Drive", r"^(drive|docs)\.google\.com$"),
             ("Moodle", r"^elearning\.rcub\.bg\.ac\.rs$"),
             # The faculty's SharePoint only: another one's is a company's (a software download).
             ("OneDrive", r"^(onedrive\.live\.com|1drv\.ms|masbgacrs(-my)?\.sharepoint\.com)$"),
             ("Dropbox", r"(^|\.)dropbox\.com$"), ("Box", r"(^|\.)box\.com$"),
             ("YouTube", r"^(www\.|m\.)?(youtube\.com|youtu\.be)$")]
FILE_HOSTS = {"Google Drive", "OneDrive", "Dropbox", "Box", "YouTube"}
# A folder, a playlist or a channel on them (a shared OneDrive folder: ':f:').
FOLDER = r"/folders/|/folder/|/sh/|/scl/fo/|/:f:/|/playlist|/channel/|/@|/c/"


def service(url):
    """The service a link is on (ELSEWHERE), or a department's site (its host: 'ie.mas.bg.ac.rs'); None for others.
    Not material: a Google form (a survey or a test; 'spreadsheet/viewform' the old ones), a published sheet (exam
    results), a Teams meeting (one class online)."""
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    if host == "docs.google.com" and re.search(r"^/forms|/viewform|/pubhtml", u.path):
        return None
    if "/meetup-join/" in u.path:
        return None
    for name, rx in ELSEWHERE:
        if re.search(rx, host):
            return name
    if host.endswith(".mas.bg.ac.rs") and host.split(".")[0] not in ("nastava", "www", "vesti"):
        # A department's Moodle (mat, motori: /moodle; it0 and cs are only one): needs a login, as the others.
        return "Moodle" if u.path.lower().startswith("/moodle") or host.split(".")[0] in ("it0", "cs") else host
    return None


def mark_elsewhere(items):
    """Each subject's material elsewhere, from its posts' links: s["elsewhere"] = {name: dict(name, first, last, who,
    users)}: the first and newest post that links it, who links it (shown names, most posts first) and their usernames
    (a teacher's page shows their own). A subject's teachers often split it, and only some use a service.
    A file host needs a folder or playlist, or two links: one video or file is not the subject's place there."""
    for it in items:
        if it["kind"] != "post" or not it["subj"]:
            continue
        for url in set(re.findall(r'href="(https?://[^"]+)"', it["html"] or "")):
            if name := service(url):
                e = it["subj"].setdefault("elsewhere", {}).setdefault(
                    name, dict(name=name, first=it, last=it, by=Counter(), users=set(), urls=set()))
                e["first"] = min(e["first"], it, key=lambda r: r["posted"])
                e["last"] = max(e["last"], it, key=lambda r: r["posted"])
                e["by"][it["who"]] += 1
                e["urls"].add(url)
                if it["teacher"]:
                    e["users"].add(it["teacher"]["username"])
    for s in {id(it["subj"]): it["subj"] for it in items if (it.get("subj") or {}).get("elsewhere")}.values():
        for name, e in list(s["elsewhere"].items()):
            if "by" not in e:
                continue
            e["who"] = [w for w, _ in e.pop("by").most_common()]
            if name in FILE_HOSTS and len(e["urls"]) < 2 and not any(re.search(FOLDER, u) for u in e["urls"]):
                del s["elsewhere"][name]
        if not s["elsewhere"]:
            del s["elsewhere"]


def load_katedre(db):
    """katedre.py's pages that are a subject's own: {folded subject name: page url}. A page is one when its title or
    its first heading is the name, nothing more ('Predmet: ' aside): a page that lists subjects names none."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'katedre_pages'").fetchone():
        return {}
    out = {}
    for url, title, html in db.execute("SELECT url, title, html FROM katedre_pages WHERE gone = 0 ORDER BY url"):
        head = re.search(r"<h[1-4][^>]*>(.*?)</h[1-4]>", html or "", re.S)
        for h in (title or "", head[1] if head else ""):
            name = re.sub(r"\s+", " ", fold(unescape(re.sub(r"<[^>]+>", " ", h)))).strip(" :.-")
            name = re.sub(r"^predmet ?: ?", "", name)
            if len(name) > 3:
                out.setdefault(name, url)
    return out


def render_cent(site, subjects):
    """Each subject's cent pages (load_cent): the newest version at <subject>/cent/<slug>/, each older one under its
    first date. Their links go to cent (the files are not hosted here)."""
    page = env.get_template("cent.html")
    for s in subjects.values():
        for p in s.get("cent", []):
            for v in p["versions"]:
                # Not indexed: a cent page is often exam results, by student.
                write(site / v["href"].strip("/") / "index.html", page.render(subj=s, page=p, v=v), index=False)


def pagefind_tags(it):
    kind = KIND[it["kind"]]
    tags = [("meta", "title", it["title"] or ""), ("filter", "vrsta", kind), ("meta", "vrsta", kind)]
    if it["kind"] == "vest":
        tags.append(("meta", "kategorija", ", ".join(it["cats"])))
    if it["smer"]:
        tags += [("filter", "smer", it["smer"]["key"]), ("meta", "smer", it["smer"]["name"])]
    if it["subject"]:
        tags += [("filter", "predmet", slug(it["subject"])), ("meta", "predmet", it["subject"])]
        # The subject itself (a name is in several smerovi): the followed subjects' search (search.js).
        tags.append(("filter", "pid", it["subj"]["href"]))
    if it["author"]:
        tags += [("filter", "autor", it["author"].lower()), ("meta", "autor", it["who"])]
    if it["year"]:
        tags.append(("filter", "godina", str(it["year"])))
    if it["date"]:
        tags += [("sort", "datum", it["date"]), ("meta", "datum", it["date"])]
    # The objava of a post that has replies: search.js shows one row per objava on a page of results.
    if it.get("thread") and len(it["thread"]["posts"]) > 1:
        tags.append(("meta", "tema", it["thread"]["href"]))
    # The text as written, word for word the indexed folded copy: search.js shows the excerpt in it.
    tags.append(("meta", "tekst", f"{it['title']}\n{it['body'] or ''}"))
    return "".join(f'<meta data-pagefind-{t}="{k}[content]" content="{escape(v)}">' for t, k, v in tags)


def mark_for_pagefind(page, it):
    """Index only a folded copy of the title and text (one copy, so the excerpt does not repeat the title)."""
    assert page.count("</article>") == 1, it["id"]
    folded = escape(fold(f"{it['title']}\n{it['body'] or ''}"))
    return page.replace("</article>", f'<div class="pf" data-pagefind-body>{pagefind_tags(it)}{folded}</div></article>', 1)


def strip_pagefind(site):
    """After Pagefind has indexed the site, drop the hidden copy it read from each item and news page (~50 MB in all).
    A stripped site cannot be indexed again: it has no data-pagefind-body left."""
    marker = '<div class="pf" data-pagefind-body>'
    assert (site / "pagefind" / "pagefind.js").exists(), "run Pagefind before stripping"
    for path in [*(site / "item").glob("*/index.html"), *(site / "vest").glob("*/index.html")]:
        html = path.read_text(encoding="utf-8")
        if (start := html.find(marker)) >= 0:
            # The copy is escaped text, so its own </div> is the first one after the marker.
            path.write_text(html[:start] + html[html.index("</div>", start) + 6:], encoding="utf-8")


def render_item(it):
    extra = {k: it[k] for k in ("source_url", "doc", "download_url") if it.get(k)}
    return mark_for_pagefind(env.get_template("detail.html").render(it=it, **extra), it)


def newest(rows):
    return sorted(rows, key=lambda r: r["date"] or "", reverse=True)


MAIN = '<main class="main" id="sadrzaj">'
HEAD_END = "<!--/head-->"
shell = None  # shell.html, set by main()
site_dir = None  # the site's folder, set by main(): write() makes a page's URL from its path in it
# Every page's canonical URL, for sitemap.xml (write).
urls = {f"{SITE_URL}/"}


def split_page(html):
    """A page -> (shell, fragment). The shell is the page with an empty <title> (in place of the page's own head, from
    <title> to <!--/head-->: base.html) and <!--main--> for the main part; the fragment is the page's head, <!--/head-->
    and the main part, in <html lang="sr"> so that Pagefind reads it.
    The Worker (pages/src/index.js join) puts them together again."""
    t0, t1 = html.index("<title>"), html.index(HEAD_END)
    m0, m1 = html.index(MAIN) + len(MAIN), html.rindex("</main>")
    return (html[:t0] + "<title></title>" + html[t1 + len(HEAD_END):m0] + "<!--main-->" + html[m1:],
            f'<html lang="sr">{html[t0:t1]}{HEAD_END}{html[m0:m1]}</html>')


def write(path, html, index=True, canonical=None):
    """Write only the page's fragment: every page but the home and 404 pages shares shell.html. Its canonical link:
    its URL on the main domain, for search engines (also for its copy on github.io), or that of the page canonical
    names (a site path) that shows the same. index=False: search engines leave it out (the posts, which name
    students; their subjects' pages are indexed), and so does the sitemap."""
    page_shell, fragment = split_page(html)
    assert page_shell == shell, f"{path}: the page differs from shell.html outside its head and <main>"
    url = SITE_URL + (canonical or f"/{path.parent.relative_to(site_dir).as_posix()}/")
    head = f'<link rel="canonical" href="{escape(url)}">'
    if index:
        urls.add(url)
        end = fragment.rindex("</html>")
        fragment = fragment[:end] + breadcrumbs(fragment, url) + fragment[end:]
    else:
        head += '<meta name="robots" content="noindex">'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fragment.replace(HEAD_END, head + HEAD_END, 1), encoding="utf-8")


def breadcrumbs(page, url):
    """The page's crumbs (base.html nav.crumbs) as schema.org data: Google shows the path in place of the URL."""
    nav = re.search(r'<nav class="crumbs".*?</nav>', page, re.S)
    here = nav and re.search(r'<span class="crumbs__here"[^>]*>(.*?)</span>', nav[0], re.S)
    if not here:
        return ""
    path = [(urljoin(SITE_URL, unescape(h)), strip_tags(t)) for h, t in LINK.findall(nav[0])] + [(url, strip_tags(here[1]))]
    # str: a str + Markup would escape the whole page.
    return str(env.filters["ld"]({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": u} for i, (u, name) in enumerate(path, 1)]}))


def write_sitemap(site):
    """sitemap.xml with every page's canonical URL, and robots.txt naming it (Cloudflare puts its own rules above)."""
    assert len(urls) <= 50_000, "a sitemap holds 50,000 URLs: split it into several under a sitemap index"
    (site / "sitemap.xml").write_text('<?xml version="1.0" encoding="utf-8"?>\n'
                                      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                      + "".join(f"<url><loc>{escape(u)}</loc></url>" for u in sorted(urls))
                                      + "</urlset>\n", encoding="utf-8")
    (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")


def load_topics(db, items):
    """The board's topics, newest last post first. A topic of one post links to that post's page, a longer one to /tema/."""
    titles = dict(db.execute("SELECT id, title FROM topics"))
    posts = defaultdict(list)
    for it in items:
        if it["kind"] in ("post", "cent"):
            posts[it["topic"]].append(it)
    topics = []
    for tid, rows in posts.items():
        rows.sort(key=lambda r: r["num"])
        t = dict(id=tid, title=titles.get(tid) or rows[0]["title"], posts=rows, first=rows[0],
                 last=max(rows, key=lambda r: r["posted"]), subj=rows[0]["subj"], smer=rows[0]["smer"],
                 gone=all(r["gone"] for r in rows),
                 href=f"/tema/{tid}/" if len(rows) > 1 else f"/item/{rows[0]['id']}/",
                 authors="|".join(sorted({(r["author"] or "").lower() for r in rows})),
                 find=fold(" ".join([titles.get(tid) or ""] + [f"{r['title']} {r['who'] or ''}" for r in rows])))
        for i, r in enumerate(rows):
            # The posts before and after it in the topic, for a post's own page.
            r["thread"], r["prev"], r["next"] = t, rows[i - 1] if i else None, rows[i + 1] if i + 1 < len(rows) else None
        topics.append(t)
    return sorted(topics, key=lambda t: t["last"]["posted"], reverse=True)


def render_places(site, topics, smerovi, subjects):
    """One page per smer (its subjects and its own topics) and one per subject (its topics), as the board's forum pages.
    Empty subjects get none."""
    topic_row = env.get_template("rows.html").module.topic_row
    in_subject, in_smer = defaultdict(list), defaultdict(list)
    for t in topics:
        if t["subj"]:
            in_subject[t["subj"]["id"]].append(t)
        elif t["smer"]:
            in_smer[t["smer"]["id"]].append(t)
    for s in subjects.values():
        rows = in_subject[s["id"]]
        s["topics"], s["count"], s["last"] = len(rows), sum(len(t["posts"]) for t in rows), rows[0]["last"] if rows else None
        s["live"] = bool(rows or s.get("cent") or s.get("site"))
        if s["live"]:
            authors = sorted({(r["author"] or "").lower(): r["who"] for t in rows for r in t["posts"]}.items(), key=lambda a: fold(a[1]))
            write(site / s["href"].strip("/") / "index.html",
                  env.get_template("predmet.html").render(subj=s, topics=rows, authors=authors))
            # Its newest topics as the home page's rows: site.js merges those of the subjects a browser follows.
            (site / s["href"].strip("/") / "novo.json").write_text(json.dumps(
                {"name": s["name"], "rows": [[t["last"]["posted"], str(topic_row(t, place=True))] for t in rows[:MINE]]},
                ensure_ascii=False), encoding="utf-8")
    for m in smerovi.values():
        subs = sorted((s for s in subjects.values() if s["smer"] is m and s["live"]), key=lambda s: fold(s["name"]))
        for s in subs:
            s["find"] = fold(" ".join([s["name"]] + [t["full_name"] for t in s.get("teachers", [])]))
        rows = in_smer[m["id"]]
        m["live"] = bool(rows or subs)
        m["subjects"], m["topics"] = len(subs), len(rows) + sum(s["topics"] for s in subs)
        # Its subjects, for the home page's row: hidden while only followed subjects show (head.js).
        m["pids"] = " ".join(s["href"] for s in subs)
        m["count"] = sum(len(t["posts"]) for t in rows) + sum(s["count"] for s in subs)
        m["last"] = max([t["last"] for t in rows[:1]] + [s["last"] for s in subs if s["last"]], key=lambda r: r["posted"], default=None)
        write(site / m["href"].strip("/") / "index.html", env.get_template("smer.html").render(smer=m, subjects=subs, topics=rows))
    for t in topics:
        if len(t["posts"]) > 1:
            write(site / "tema" / str(t["id"]) / "index.html", env.get_template("tema.html").render(t=t), index=False)


def post_href(it):
    """A post's place: its anchor in a topic of several posts, else its own page."""
    return f"{it['thread']['href']}#p{it['num']}" if len(it["thread"]["posts"]) > 1 else f"/item/{it['id']}/"


def atom(title, path, posts):
    """An Atom feed of the newest posts (newest first) for a feed reader: the whole board, one subject or the news
    (an item with its own href). A reader needs whole URLs, so they are on the main domain."""
    def entry(it):
        href, page = it.get("href") or post_href(it), it.get("href") or f"/item/{it['id']}/"
        place = (it["subj"] and it["subj"]["name"]) or (it["smer"] and it["smer"]["label"]) or ", ".join(it.get("cats", []))
        return (f"<entry><title>{escape(it['title'] or '')}</title><link href=\"{SITE_URL}{escape(href)}\"/>"
                f"<id>{SITE_URL}{escape(page)}</id><updated>{it['posted']}</updated>"
                f"<author><name>{escape(it['who'] or '')}</name></author>"
                + (f"<category term=\"{escape(place)}\"/>" if place else "")
                + f"<content type=\"html\">{escape(it['html'] or it['body'] or '')}</content></entry>")
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="sr">'
            f"<title>{escape(title)}</title><id>{SITE_URL}{escape(path)}</id>"
            f"<link rel=\"self\" href=\"{SITE_URL}{escape(path)}feed.xml\"/><link href=\"{SITE_URL}{escape(path)}\"/>"
            f"<updated>{posts[0]['posted'] if posts else '1970-01-01T00:00:00+00:00'}</updated>"
            + "".join(entry(it) for it in posts) + "</feed>\n")


def write_feeds(site, items, subjects, pushed=()):
    """/feed.xml: the board's newest posts; <subject page>/feed.xml: the subject's. Next to a page that exists."""
    posts = sorted((it for it in items if it["kind"] in ("post", "cent")), key=lambda it: it["posted"], reverse=True)
    (site / "feed.xml").write_text(atom("Forum nastave · Mašinski fakultet", "/", posts[:FEED_ALL]), encoding="utf-8")
    of = defaultdict(list)
    for it in posts:
        if it["subj"] and len(of[it["subj"]["id"]]) < FEED:
            of[it["subj"]["id"]].append(it)
    for s in subjects.values():
        if s.get("live"):
            (site / s["href"].strip("/") / "feed.xml").write_text(atom(f"{s['name']} · forum nastave", s["href"], of[s["id"]]),
                                                                  encoding="utf-8")
    # The subjects' newest posts, next to the site (not on it), for ci/push.py: it notifies those newer than a post id.
    # k: "p" a board post, "c" a cent notice, "s" a cent page version; ci/push.py keeps one "before" per kind.
    # shortcut: the newest 1000 posts and notices only; a scrape that brings more new posts notifies only these.
    (site.parent / "push.json").write_text(json.dumps(
        [dict(k=it["id"][0], id=it["num"], s=it["subj"]["href"], n=it["subj"]["name"], t=it["title"] or "", u=post_href(it))
         for it in posts if it["subj"]][:1000] + list(pushed), ensure_ascii=False), encoding="utf-8")


def strip_tags(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html or "")).split())


LINK = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


def first_link(html):
    """(text, href) of a page's first link, or None: the calendar's file on its page."""
    m = LINK.search(html or "")
    return m and (strip_tags(m[2]), unescape(m[1]))


def schedule_card(line, text):
    """A schedule link as a card, (badge, name): 'I god. raspored …' and '… - 1. godina' are years ('1', '1. godina');
    'BMI - Biomedicinsko inženjerstvo' is a module ('BMI', 'Biomedicinsko inženjerstvo')."""
    m = re.match(r"(IV|I{1,3})\s*god", line)
    n = ROMAN[m[1]] if m else (int(y[1]) if (y := re.search(r"(\d)\.\s*godina", text)) else None)
    if n:
        return str(n), f"{n}. godina"
    code, _, name = text.partition(" - ")
    return (code, name) if name and len(code) <= 4 else ("", text)


def parse_lectures(html):
    """The lecture schedule page (raspored-predavanja) as data for /raspored/: its title (h2), its semester (h3), and
    per program (an h4) its schedules as cards, its elective blocks, its computer rooms and its notes. A line is the
    text between <br>s: 'Izborni predmeti: 5.4, 5.5', 'Računarske sale: 324, …', a line with no link is a note,
    any other link a schedule. None when the page has no program: /raspored/ then shows the page as it is."""
    heads = re.findall(r"<h([23])[^>]*>(.*?)</h\1>", html or "", re.S)
    out = dict(title=next((strip_tags(h) for n, h in heads if n == "2"), ""),
               semester=next((strip_tags(h) for n, h in heads if n == "3"), ""), programs=[])
    for part in re.split(r"(?=<h4)", html or "")[1:]:
        head = re.match(r"<h4[^>]*>(.*?)</h4>", part, re.S)
        if not head:
            continue
        # 'OSNOVNE AKADEMSKE STUDIJE - MAŠINSKO INŽENjERSTVO' -> 'Osnovne akademske studije', 'Mašinsko inženjerstvo'
        level, _, name = strip_tags(head[1]).lower().partition(" - ")
        p = dict(key=slug(strip_tags(head[1])), level=level.capitalize(), name=name.capitalize(),
                 cards=[], electives=[], rooms=[], notes=[])
        for line in re.split(r"<br\s*/?>|</?p\b[^>]*>|</?div\b[^>]*>", part[head.end():]):
            text = strip_tags(line)
            links = [(strip_tags(t), unescape(h)) for h, t in LINK.findall(line)]
            if not links:
                # 'Obavezni predmeti, (po modulima):' only heads the links under it.
                if text and not text.endswith(":"):
                    p["notes"].append(text)
            elif fold(text).startswith("izborni"):
                p["electives"] += links
            elif "sal" in fold(text.split(":")[0]):
                p["rooms"] += links
            else:
                p["cards"] += [(*schedule_card(text, t), h) for t, h in links]
        out["programs"].append(p)
    return out if out["programs"] else None


def drop_empty_tables(html):
    """Leave out a table whose cells are all empty, with the heading right above it: the exam page keeps its forms
    with no rows between terms. The <div>s between the heading and the table stay (their </div> is after it)."""
    def table(m):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", m[0], re.S)
        return (m[2] or "") if cells and not strip_tags("".join(cells)) else m[0]
    return re.sub(r"(?:<h([1-6])[^>]*>(?:(?!</?h[1-6]).)*</h\1>(\s*(?:<div[^>]*>\s*)*))?<table\b.*?</table>", table, html, flags=re.S)


def schedule_entries(calendar, lectures, exams_html):
    """/raspored/ as the header search's entries (izbor.json raspored, site.js): [name, where, href] for the calendar,
    each lecture schedule, elective block and room, and each row of the exam tables (its first cells, the page's link)."""
    out = [["Kalendar nastave i ispita", calendar[0], calendar[1]]] if calendar else []
    for p in (lectures or {}).get("programs", []):
        where = " — ".join(filter(None, [p["level"], p["name"]]))
        out += [[name, f"Raspored predavanja · {where}", href] for _, name, href in p["cards"]]
        out += [[f"Izborni blok {t}", f"Raspored predavanja · {where}", h] for t, h in p["electives"]]
        out += [[f"Sala {t}", f"Raspored predavanja · {where}", h] for t, h in p["rooms"]]
    for table in re.findall(r"<table\b.*?</table>", exams_html or "", re.S):
        heads = [strip_tags(h).split("(")[0].strip() for h in re.findall(r"<th\b[^>]*>(.*?)</th>", table, re.S)]
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S):
            cells = [strip_tags(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)]
            if not cells or not cells[0]:
                continue
            dates = [f"{h} {c}" for h, c in zip(heads[1:3], cells[1:3]) if c]
            link = LINK.search(row)
            out.append([cells[0], " · ".join(["Raspored ispita"] + dates), unescape(link[1]) if link else "/raspored/#ri-h"])
    return out


def render_study_pages(site, db):
    """The schedule pages of www.mas.bg.ac.rs (studije.py), with their files served from this site. The newest version
    of a page is at /studije/<slug>/; each older one has a page of its own, linking the files as they were then.
    /raspored/ puts the newest of all three on one page: the calendar and OAS MI's years first, then the lecture
    and the exam schedules. Returns /raspored/ as search entries (schedule_entries)."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'study_pages'").fetchone():
        return []
    # Every version of every file: the one seen last keeps the plain URL, an older one is under its hash.
    newest, versions_of = {}, defaultdict(list)
    for r in db.execute("SELECT path, sha, data, first_seen FROM study_files ORDER BY path, last_seen DESC"):
        rel = f"v/{r['sha'][:12]}/{r['path']}" if r["path"] in newest else r["path"]
        write_bytes(site / "studije" / "files" / rel, r["data"])
        url = f"/studije/files/{quote(rel)}"
        newest.setdefault(r["path"], url)
        versions_of[r["path"]].append((r["first_seen"], url))

    def file_then(path, when):
        """A file as an older page version linked it: the version first seen last by then, else the oldest.
        shortcut: a file that went back to an earlier version links the one before; fine while that is rare."""
        seen = sorted(versions_of.get(path, []))
        then = [url for first, url in seen if first <= when]
        return then[-1] if then else seen[0][1] if seen else None

    pages, now = defaultdict(list), {}
    for r in db.execute("SELECT * FROM study_pages ORDER BY slug, last_seen DESC"):
        pages[r["slug"]].append(dict(r))
    for name, versions in pages.items():
        source = f"{STUDY_SITE}studije/{name}"
        for i, v in enumerate(versions):
            v["href"] = f"/studije/{name}/" if i == 0 else f"/studije/{name}/{v['first_seen'][:10]}-{v['sha'][:6]}/"
        for v in versions:
            when = None if v is versions[0] else v["last_seen"]
            local = lambda value: (p := media_path(value)) and (file_then(p, when) if when else newest.get(p))
            html = drop_empty_tables(clean_html(v["html"], source, local) or "")
            # The page's first heading is usually its title, which the page already has as h1.
            m = re.search(r"<h([12])[^>]*>(.*?)</h\1>", html, re.S)
            if m and fold(re.sub(r"<[^>]+>", "", m[2]).strip()) == fold(v["title"]):
                html = html[:m.start()] + html[m.end():]
            write(site / v["href"].strip("/") / "index.html", env.get_template("studije.html").render(
                page=v, current=versions[0], versions=versions, html=html, source_url=source))
            if v is versions[0]:
                now[name] = dict(page=v, html=html)
    get = lambda slug: now.get(slug, {}).get("html")
    calendar, lectures = first_link(get("kalendar-nastave")), parse_lectures(get("raspored-predavanja"))
    write(site / "raspored" / "index.html", env.get_template("raspored.html").render(
        calendar=calendar, lectures=lectures,
        lectures_html=get("raspored-predavanja"), exams_html=get("raspored-ispita"),
        sources=[(now[slug]["page"]["href"], title) for slug, title in STUDY_PAGES.items() if slug in now],
        checked=max((n["page"]["last_seen"] for n in now.values()), default=None)))
    return schedule_entries(calendar, lectures, get("raspored-ispita"))


def photo_path(url, kind):
    """A stored photo's path in the site: /foto/<hash of its source URL>.jpg."""
    return f"/foto/{hashlib.sha1(url.encode()).hexdigest()[:16]}.{kind.split('/')[1].replace('jpeg', 'jpg')}"


def write_photos(db, site):
    """The teacher photos nastavnici.py stored, as files: the faculty removes a departed teacher's."""
    (site / "foto").mkdir(parents=True, exist_ok=True)
    for url, kind, data in db.execute("SELECT url, type, data FROM photos"):
        (site / photo_path(url, kind).lstrip("/")).write_bytes(data)


# A teacher whose forum account is not their e-mail's name (the e-mail changed with a surname): theirs on the board.
FORUM_ACCOUNT = {"sjosipovic": "sgrbic"}  # Sonja Josipović, née Grbić (ie.mas.bg.ac.rs/zaposleni.html)
# Teachers who post on the board but are on no list of the faculty's (nastavnici.py), from the faculty's other pages.
# source: where the profile's facts are from.
_JOKSIMOVIC = ("https://mas.bg.ac.rs/_media/fakultet/izbori-u-zvanja/referati/2020/"
               "referat_komisije_-_kandidat_joksimovic_aleksandra.pdf")
OTHER_TEACHERS = [dict(
    id="ajoksimovic", name="Александра Д. Јоксимовић", full_name="Александра Д. Јоксимовић", title="асистент",
    katedra="Катедра за теорију механизама и машина", katedra_id=None, office=None, email=None, username="ajoksimovic",
    phone=None, hours=None, research=None, emeritus=0, photo=None, first_seen="2026-11-09", last_seen="2026-11-09",
    gone=0, source=_JOKSIMOVIC, source_name="реферат комисије, mas.bg.ac.rs",
    html="<p>Мастер инжењер машинства (2017, модул Прехрамбено машинство). На Машинском факултету од 2012. ради на "
         "предмету Инжењерска графика, од 2015. на предмету Мехатроника. Истраживач-приправник од 2017, изабрана у "
         "звање асистента на Катедри за теорију механизама и машина 2020. године.</p>"
         "<p>Није на списку наставника на сајту факултета; ово је из реферата комисије за њен избор у звање асистента "
         f'(2020): <a href="{_JOKSIMOVIC}">PDF</a>.</p>')]


HISTORY = Path(__file__).resolve().parent.parent / "nastavnici-istorija.jsonl"


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
        h["sources"].sort(key=lambda s: (kinds.index(s["kind"]) if s["kind"] in kinds else 4, s["page"] or 0,
                                         re.findall(r"\d{4}", s["years"] or "")))
        if h["teacher"]:
            if h["teacher"] in by_id:
                by_id[h["teacher"]]["history"] = h
            continue
        # last_seen: the last year a source names, so the archive orders them after the recently departed.
        years = re.findall(r"\d{4}", h["years"] or "")
        new.append(dict(id=f"ist-{slug(h['name'] + ' ' + (h['life'] or ''))}", name=h["name"], full_name=h["name"],
                        title=h["title"] or "", katedra=h["katedra"], katedra_id=None, office=None, email=None, username=None,
                        phone=None, hours=None, research=None, emeritus=0, html=None, first_seen=None,
                        last_seen=max(years) if years else "0000", gone=1, photo=None, subjects=[], history=h,
                        suffix=h["life"] and slug(h["life"])))
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
    for t in teachers:
        # The photo from our copy (write_photos); a listed teacher's not copied yet from the faculty, a departed
        # one's none (the faculty took it down).
        thumb, photo = photo_urls(t["html"], t.get("photo"))
        t["thumb"] = local.get(thumb) or (None if t["gone"] else thumb)
        t["photo"] = local.get(photo) or (None if t["gone"] else photo)
        # 'Драган С. Алексендрић' -> 'Драган Алексендрић': the shown name, without the father's initial.
        t["shown"] = re.sub(r" \w\.(?= )", "", t["name"])
        # The title's rank, for the list's order by title (site.js sorts the digit as text); an unknown title last.
        t["rank"] = RANKS.index(t["title"]) if t["title"] in RANKS else 9
    # By surname, then given name, in the order of the Serbian alphabet (as the faculty's list).
    return sorted(teachers, key=lambda t: (azbuka(t["name"].split()[-1]), azbuka(t["name"])))


RANKS = ["професор емеритус", "редовни професор", "ванредни професор", "доцент", "асистент са докторатом", "асистент"]
AZBUKA = {c: i for i, c in enumerate("абвгдђежзијклљмнњопрстћуфхцчџш")}


def azbuka(word):
    return [AZBUKA.get(c, 100 + ord(c)) for c in word.lower()]


def render_teachers(site, teachers, items, book):
    """A list of all teachers with a filter, and one page per teacher: the faculty's profile and their posts here."""
    posts = defaultdict(list)
    for it in items:
        posts[(it["author"] or "").lower()].append(it)
    pages = {f"/fakultet/nastavnici/{t['id']}": t["href"] for t in teachers}
    # A subject's link: its forum page, else its page in the subject list.
    book_href = {s["id"]: s["href"] for s in book}
    subj_pages = {f"/studije/predmeti/{c}": h for c, h in book_href.items()}
    subj_pages |= {f"/studije/predmeti/{s['code']}": s["subj"]["href"]
                   for t in teachers for s in t["subjects"] if s["subj"] and s["subj"].get("live")}
    for t in teachers:
        t["posts"] = newest(posts[t["username"]]) if t["username"] else []
        # The profile's subjects: one row per archive subject (it can have several codes), archived first.
        mine = Counter(p["subj"]["id"] for p in t["posts"] if p["subj"])
        courses = {}
        for s in t["subjects"]:
            archived = s["subj"] if s["subj"] and s["subj"].get("live") else None
            # One row per name too: a subject the profile lists under two codes ('Трибологија' twice).
            row = courses.setdefault(archived["id"] if archived else fold(s["name"]),
                                     dict(name=s["name"], subj=archived, codes=[], mine=archived and mine[archived["id"]],
                                          url=book_href.get(s["code"]) or f"{STUDY_SITE}studije/predmeti/{s['code']}"))
            row["codes"].append(s["code"])
        # Where they post most first; subjects without their posts after, by name.
        t["courses"] = sorted(courses.values(), key=lambda c: (-(c["mine"] or 0), not c["subj"], azbuka(c["name"])))
        t["find"] = fold(" ".join([t["full_name"], t["title"] or "", t["katedra"] or "", t["email"] or "", t["research"] or "",
                                   t["office"] or ""] + [s["name"] for s in t["subjects"]]))
        # How far the grey corner reaches (style.css --p): the longer since they were last at the faculty, the more of
        # the card, up to 85% for the 1860s; by the square root, so the recent decades still differ. No year: none.
        ago = date.today().year - int(t["last_seen"][:4]) if t["gone"] and t["last_seen"][:4] != "0000" else 0
        t["age"] = round(85 * min(1, max(0, ago) / 165) ** 0.5)
    for t in teachers:
        source = base = f"{STUDY_SITE}fakultet/nastavnici/{'emeritus/start' if t['emeritus'] else t['id']}"
        name = "mas.bg.ac.rs"
        if t.get("source"):  # OTHER_TEACHERS
            source, name = t["source"], t["source_name"]
        elif t["id"].startswith("masinac-"):
            # Known only from masinac.org: 'masinac-omk-zoran-stamenic' is its page katedre/omk/predavaci/zoran-stamenic.
            _, k, who = t["id"].split("-", 2)
            source = base = f"https://www.masinac.org/fakultet/katedre/{k}/predavaci/{who}"
            name = "masinac.org"
        elif t["gone"]:
            name = "web.archive.org"
            # The faculty took the profile down: the Wayback Machine's copy nearest the last day it was listed.
            stamp = re.sub(r"\D", "", t["last_seen"])[:14]
            source = f"https://web.archive.org/web/{stamp}/{source}"
        local = lambda v: pages.get(v.split("?")[0]) or subj_pages.get(v.split("?")[0])
        # The profile repeats the name as its first heading and the photo; the page has both above it.
        html = re.sub(r"<h[12][^>]*>.*?</h[12]>", "", t["html"] or "", count=1, flags=re.S)
        # base: the profile's relative links are the faculty's (or masinac.org's), even when shown from the Wayback copy.
        html = clean_html(re.sub(r"<img[^>]+_media/fakultet/nastavnici/[^>]+>", "", html, count=1), base, local)
        write(site / t["href"].strip("/") / "index.html",
              env.get_template("nastavnik.html").render(t=t, html=html, source_url=source, source_name=name))
    listed = [t for t in teachers if not t["gone"]]
    katedre = sorted({t["katedra"] for t in listed if t["katedra"]})
    # The ones who left, most recent first: a section below the list.
    left = sorted((t for t in teachers if t["gone"]), key=lambda t: t["last_seen"], reverse=True)
    write(site / "nastavnici" / "index.html",
          env.get_template("nastavnici.html").render(teachers=listed, katedre=katedre, left=left))
    write(site / "nastavnici" / "arhiva" / "index.html",
          env.get_template("nastavnici.html").render(teachers=left, katedre=sorted({t["katedra"] for t in left if t["katedra"]}),
                                                     archive=True))


# The programs in the order of the faculty's studies; a subject book program not here goes last.
PROGRAMS = ["Основне академске студије — МИ", "Основне академске студије — ИТМ", "Мастер академске студије — МИ",
            "Мастер академске студије — Индустрија 4.0", "Докторске студије — МИ"]


def slot_label(slot_name, slot):
    """'Изборни предмет 5.4.5', '5.4' -> 'Изборни предмет 5.4': the cell's last number is the ECTS."""
    return re.sub(r"\s*[\d.]+$", "", slot_name) + " " + slot


def load_book(db, subjects, teachers):
    """The faculty's subjects (predmeti.py), each with its places in the plans, its teachers and its forum subject:
    the same code, or else the same name in the board's smer of the same program."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'subjects'").fetchone():
        return []
    # Before render_places, so the forum pages can link here; a forum subject with no topics (no page) is dropped later.
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    by_name = {(fold(s["smer"]["short"]), fold(s["name"])): s for s in subjects.values()}
    teacher = {t["id"]: t for t in teachers}
    book = [dict(r, places=[]) for r in db.execute("SELECT * FROM subjects ORDER BY rowid")]
    set_hrefs(book, lambda s: f"/predmeti/{slug(s['name'])}/")
    by_id = {s["id"]: s for s in book}
    for s in book:
        s["forum"] = board_subject(by_code, by_name, s["id"], s["name"], s["program"])
        # The holder first, then the other teachers of the page's head ('Извођачи').
        m = re.search(r"Извођачи</strong>(.*?)<br", s["html"] or "", re.S)
        ids = [s["holder"]] + re.findall(r"/fakultet/nastavnici/(\d+)", m[1] if m else "")
        s["teachers"] = [teacher[i] for i in dict.fromkeys(ids) if i in teacher]
        s["holder_t"] = teacher.get(s["holder"])
    # i: the order the plans were read in (predmeti.py: programs, then the modules as the master's page lists them).
    for i, r in enumerate(db.execute("SELECT * FROM subject_places ORDER BY rowid")):
        places = by_id[r["subject"]]["places"] if r["subject"] in by_id else None
        # A place stored more than once (predmeti.py before it listed a slot's subject once: Завршни предмет 102 times).
        key = lambda p: (p["program"], p["module"], p["semester"], p["slot"])
        if places is not None and not any(key(p) == key(r) for p in places):
            places.append(dict(r, i=i, label=slot_label(r["slot_name"], r["slot"]) if r["slot"] else None))
    for s in book:
        s["find"] = fold(" ".join([s["name"], s["id"], s["katedra"] or "", s["program"]]
                                  + [t["name"] for t in s["teachers"]] + [p["module"] or "" for p in s["places"]]))
        if s["forum"]:
            s["forum"].setdefault("info", s)
    return book


def plan_groups(book):
    """The list's default grouping, as the faculty's plans: program (and module) > semester > the required subjects,
    then one group per elective slot. A subject in no plan is listed under its program at the end."""
    plans, first = {}, {}
    for s in book:
        if s["gone"]:
            continue
        for p in s["places"]:
            first[(p["program"], p["module"])] = min(p["i"], first.get((p["program"], p["module"]), p["i"]))
            plan = plans.setdefault((p["program"], p["module"]), {})
            sem = plan.setdefault(p["semester"], dict(sem=p["semester"], req=[], slots={}))
            if p["slot"]:
                sem["slots"].setdefault((p["pos"], p["slot"]), dict(label=p["label"], rows=[]))["rows"].append(s)
            else:
                sem["req"].append((p["pos"], s))
        if not s["places"]:
            plans.setdefault((s["program"], "ван наставног плана"), {}).setdefault(0, dict(sem=0, req=[], slots={}))["req"].append((0, s))
    order = {p: i for i, p in enumerate(PROGRAMS)}
    out = []
    # Programs in study order; modules in the order of the master's page; 'not in a plan' last in its program.
    for (program, module), sems in sorted(plans.items(), key=lambda kv: (order.get(kv[0][0], len(order)), first.get(kv[0], 1e9))):
        out.append(dict(program=program, module=module, sems=[
            dict(sem=n, req=[s for _, s in sorted(v["req"], key=lambda x: (x[0], azbuka(x[1]["name"])))],
                 slots=[v["slots"][k] for k in sorted(v["slots"])]) for n, v in sorted(sems.items())]))
    return out


def render_book(site, book):
    """A list of all subjects with a filter, grouping and sorting, and one page per subject: the faculty's page."""
    pages = {f"/studije/predmeti/{s['id']}": s["href"] for s in book}
    for s in book:
        if s["forum"] and not s["forum"].get("live"):
            s["forum"] = None
    for s in book:
        source = f"{STUDY_SITE}studije/predmeti/{s['id']}"
        # The page's name and head (ID, ECTS, teachers, katedra) are above it, from the same fields.
        html = re.sub(r"<h1[^>]*>.*?</h1>", "", s["html"] or "", count=1, flags=re.S)
        html = re.sub(r'<div class="wrap_box[^"]*">.*?</div>', "", html, count=1, flags=re.S)
        # 'Извођења' (semester, position) is the 'U planu' line above.
        html = re.sub(r'<h2[^>]*id="извођења".*?</h2>\s*<div class="level2">.*?</div>', "", html, count=1, flags=re.S)
        write(site / s["href"].strip("/") / "index.html", env.get_template("predmet_opis.html").render(
            s=s, html=clean_html(html, source, lambda v: pages.get(v.split("?")[0])), source_url=source))
    listed = [s for s in book if not s["gone"]]
    write(site / "predmeti" / "index.html", env.get_template("predmeti.html").render(
        plans=plan_groups(book), n=len(listed), katedre=sorted({s["katedra"] for s in listed if s["katedra"]}),
        programs=[p for p in PROGRAMS if any(s["program"] == p for s in listed)]))


def picker(subjects, book, teachers, katedre={}):
    """The subject picker ("Moji predmeti", site.js): the subjects with topics, as [href, name]; a tree of them by the
    plans, program > (module >) year of study > group: '' for the required subjects, else the elective block
    ('Изборни предмет 5.4'). Every subject of the plans is in it: one with topics as its board subject, one without
    as its page in the subject book, [href, name, 0]. A board subject in no plan (a subject the faculty no longer
    has) is under its program's 'Stari predmeti'; the board's other forums (katedre, moduli) are programs with one
    group. A group has its subjects in s, any other node its children in c.
    teachers: each teacher with the board subjects they teach (into the list); people: every listed teacher's
    [name, page], for the header search on a teacher's page; marks: a subject's index to where else it has material.
    katedre: the department sites' subject pages (load_katedre).
    After render_places (the counts) and render_teachers (the courses)."""
    live = [s for s in subjects.values() if s.get("live")]
    entries = [[s["href"], s["name"]] for s in live]
    at = {("f", s["id"]): i for i, s in enumerate(live)}
    tree, placed = {}, set()

    def index(b):
        """A plan's subject in the list: its board subject when that has topics, else its page in the book."""
        f = b["forum"]
        key = ("f", f["id"]) if f and f.get("live") else ("b", b["id"])
        if key not in at:
            at[key] = len(entries)
            entries.append([b["href"], b["name"], 0])
        placed.add(key)
        return at[key]

    def add(path, i):
        node = tree
        for name in path:
            node = node.setdefault(name, {})
        node.setdefault(None, []).append(i)

    def marks(s, name):
        """An entry's other pages: cent's, its page on a department's site (load_katedre), then the services its posts
        link, newest first; a department's site by its first label ('ie.mas.bg.ac.rs': 'ie')."""
        own = katedre.get(fold(name))
        return list(dict.fromkeys(["cent"] * bool(s.get("cent")) + ([urlsplit(own).hostname.split(".")[0]] if own else []) + [
            e["name"].removesuffix(".mas.bg.ac.rs")
            for e in sorted((s.get("elsewhere") or {}).values(), key=lambda e: e["last"]["posted"], reverse=True)]))

    order = {p: i for i, p in enumerate(PROGRAMS)}
    places = [(p, b) for b in book if not b["gone"] for p in b["places"]]
    for p, b in sorted(places, key=lambda x: (order.get(x[0]["program"], len(order)), x[0]["i"])):
        group = slot_label(p["slot_name"], p["slot"]) if p["slot"] else ""
        add([p["program"]] + [p["module"]] * bool(p["module"]) + [f"{(p['semester'] + 1) // 2}. godina", group], index(b))
    for s in live:
        if ("f", s["id"]) not in placed:
            # The board's smer 'Основне академске студије - МИ' is the plans' 'Основне академске студије — МИ'.
            program = s["smer"]["label"].replace(" - ", " — ")
            add([program, "Stari predmeti", ""] if " — " in program else [program, ""], at[("f", s["id"])])

    def nodes(tree):
        # The required subjects first, then the elective blocks in the plan's order.
        keys = sorted((k for k in tree if k is not None), key=lambda k: k != "")
        return [dict(n=k, c=nodes(tree[k]), s=sorted(set(tree[k].get(None, [])), key=lambda i: azbuka(entries[i][1])))
                for k in keys]
    return dict(subjects=entries, tree=nodes(tree),
                teachers=[[t["shown"], sorted({at[("f", c["subj"]["id"])] for c in t["courses"] if c["subj"]})]
                          for t in teachers if not t["gone"] and any(c["subj"] for c in t["courses"])],
                people=[[t["shown"], t["href"]] for t in teachers if not t["gone"]],
                marks={i: m for i, e in enumerate(entries) if (m := marks(live[i] if i < len(live) else {}, e[1]))})


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def short_smer(name):
    """'основне академске студије - МИ' -> 'ОАС - МИ': the faculty's own abbreviations, for the smer's URL."""
    return re.sub(r"^мастер академске студије", "МАС", re.sub(r"^основне академске студије", "ОАС", name, flags=re.I), flags=re.I)


def side_panel(items):
    """The counts of the side panel (sidebar.html), the same on every page."""
    years = Counter(r["year"] for r in items if r["year"])
    return dict(total=len(items), kinds=Counter(KIND[r["kind"]] for r in items),
                year_hist=sorted(years.items()), downloads=sum(n for n, _ in attachment_files(items).values()))


def attachment_files(items):
    """{attachment id: (downloads, post)}: a file that two posts link counts once."""
    return {f: (n, it) for it in items for f, _, n in it["files"]}


def bars(pairs, href=None):
    """[(label, count)] -> the rows of a bar chart (stats.html chart), each bar's height in % of the highest."""
    top = max((n for _, n in pairs), default=0) or 1
    return [dict(label=label, n=n, pct=round(n / top * 100, 1), href=href and href(label)) for label, n in pairs]


def ranking(counts, row, k=10):
    """The k highest counts as rows of a ranked list (stats.html rank); row(key) -> (label, href, note)."""
    top = counts.most_common(k)
    return [dict(zip(("label", "href", "note"), row(key)), n=n, pct=round(n / top[0][1] * 100, 1)) for key, n in top]


MONTHS = "jan feb mar apr maj jun jul avg sep okt nov dec".split()
WEEKDAYS = "pon uto sre čet pet sub ned".split()


def archive_stats(items, topics, teachers):
    """The numbers of /statistika/: the board by time, who posts, what is downloaded, the teachers."""
    posts = [it for it in items if it["kind"] == "post"]
    dated = [it for it in posts if it["date"]]
    files = attachment_files(posts)
    by = {}  # a ranking's key (a username or a page's href) -> an item that names it
    tally = defaultdict(Counter)
    for it in posts:
        if it["author"]:
            tally["authors"][it["author"].lower()] += 1
            by.setdefault(it["author"].lower(), it)
        if it["subj"]:
            tally["subjects"][it["subj"]["href"]] += 1
            by.setdefault(it["subj"]["href"], it)
        if it["smer"]:
            tally["smerovi"][it["smer"]["href"]] += 1
            by.setdefault(it["smer"]["href"], it)
    for fid, (n, it) in files.items():
        tally["files"][fid] = n
        if it["teacher"]:
            tally["teacher_dl"][it["teacher"]["href"]] += n
            by.setdefault(it["teacher"]["href"], it)
        if it["subj"]:
            tally["subject_dl"][it["subj"]["href"]] += n
        if it["smer"]:
            tally["smer_dl"][it["smer"]["href"]] += n
    names = {fid: name for it in posts for fid, name, _ in it["files"]}
    author = lambda a: (by[a]["who"], by[a]["teacher"] and by[a]["teacher"]["href"], by[a]["teacher"] and "nastavnik")
    subject = lambda h: (by[h]["subj"]["name"], h, short_smer(by[h]["smer"]["name"]))
    smer = lambda h: (by[h]["smer"]["label"], h, None)
    teacher = lambda h: (by[h]["teacher"]["shown"], h, by[h]["teacher"]["title"])
    # A file's note has its post's date too: a teacher uploads a new copy of the same name for each exam.
    upload = lambda f: (names[f], f"/item/{files[f][1]['id']}/",
                        " · ".join(filter(None, [files[f][1]["subject"] or files[f][1]["who"], env.filters["dmy"](files[f][1]["date"])])))

    years = Counter(it["year"] for it in dated)
    months = Counter((it["year"], int(it["date"][5:7])) for it in dated)
    top_month = max(months.values(), default=1)
    hours = Counter(int(m[1]) for it in posts if (m := re.search(r"(\d{1,2}):\d\d", it["when"] or "")))
    days = Counter(date.fromisoformat(it["date"][:10]).weekday() for it in dated)
    busiest = Counter(it["date"][:10] for it in dated).most_common(1)
    topic = {t["href"]: t for t in topics}

    listed = [t for t in teachers if not t["gone"]]
    posting = {t["username"] for t in listed if t["username"] and t["username"] in tally["authors"]}
    by_teachers = sum(1 for it in posts if it["teacher"])
    return dict(
        first=min(dated, key=lambda it: it["date"], default=None), last=max(dated, key=lambda it: it["date"], default=None),
        totals=[(len(posts), "post"), (len(topics), "objava"), (len(tally["authors"]), "autor"),
                (len(tally["subjects"]), "predmet"), (len(files), "prilog"), (sum(tally["files"].values()), "preuzimanje")],
        years=bars(sorted(years.items()), lambda y: f"/?from={y}&to={y}"),
        heat=[dict(year=y, cells=[dict(m=MONTHS[m - 1], n=months[(y, m)], pct=round(months[(y, m)] / top_month * 100))
                                  for m in range(1, 13)]) for y in sorted(years)],
        hours=bars([(h, hours[h]) for h in range(24)]),
        days=bars([(d, days[i]) for i, d in enumerate(WEEKDAYS)]),
        busiest=busiest[0] if busiest else None,
        authors=ranking(tally["authors"], author), subjects=ranking(tally["subjects"], subject),
        smerovi=ranking(tally["smerovi"], smer, k=20),
        files=ranking(tally["files"], upload), teacher_dl=ranking(tally["teacher_dl"], teacher),
        subject_dl=ranking(tally["subject_dl"], subject), smer_dl=ranking(tally["smer_dl"], smer, k=20),
        longest=ranking(Counter({t["href"]: len(t["posts"]) for t in topics}),
                        lambda h: (topic[h]["title"], h, topic[h]["subj"] and topic[h]["subj"]["name"])),
        teachers=dict(listed=len(listed), emeritus=sum(1 for t in listed if t["emeritus"]), gone=len(teachers) - len(listed),
                      posting=len(posting), share=round(by_teachers / (len(posts) or 1) * 100),
                      titles=[(r, n) for r in RANKS if (n := sum(1 for t in listed if t["title"] == r))],
                      katedre=ranking(Counter(t["katedra"] for t in listed if t["katedra"]),
                                      lambda k: (env.filters["katedra"](k).capitalize(), f"/nastavnici/?katedra={slug(k)}", None))))


def render_vesti(site, vesti):
    """The news: a page each at /vest/<id>/ (what search finds; an id can be a year, so not under /vesti/), a list per
    year with a category filter (the newest year at /vesti/, each other at /vesti/<year>/), and /vesti/feed.xml."""
    if not vesti:
        return
    years = sorted({v["year"] for v in vesti}, reverse=True)
    year_href = {y: "/vesti/" if y == years[0] else f"/vesti/{y}/" for y in years}
    page = env.get_template("vest.html")
    for v in vesti:
        v["year_href"] = year_href[v["year"]]
        write(site / v["href"].strip("/") / "index.html", mark_for_pagefind(page.render(v=v), v))
    for y in years:
        rows = [v for v in vesti if v["year"] == y]
        cats = sorted({c for v in rows for c in v["cats"]}, key=fold)
        write(site / year_href[y].strip("/") / "index.html", env.get_template("vesti.html").render(
            vesti=rows, year=y, years=years, year_href=year_href, cats=cats, total=len(vesti)))
    (site / "vesti" / "feed.xml").write_text(atom("Vesti · Mašinski fakultet", "/vesti/", vesti[:FEED_ALL]), encoding="utf-8")


def render_home(topics, smerovi, side, n_teachers, vesti):
    return env.get_template("search.html").render(
        smerovi=[m for m in smerovi.values() if m.get("live")], recent=topics[:RECENT], vesti=vesti[:VESTI_HOME],
        stats=dict(posts=side["total"], topics=len(topics), teachers=n_teachers),
        years_json=json.dumps([y for y, _ in side["year_hist"]]))


def main(db_path, out):
    site = Path(out) / "site"
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(HERE / "static", site / "static")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    place, smerovi, subjects = load_places(db)
    cent_items, cent_pushed = load_cent(db, smerovi, subjects)
    items = load_items(db, place) + cent_items
    teachers = load_teachers(db, subjects)
    if teachers:
        write_photos(db, site)
    # A board author is a teacher when the username is the teacher's e-mail before @. When two rows share it (a
    # teacher who became emeritus), the one still listed comes last and wins.
    teacher_of = {t["username"]: t for t in sorted(teachers, key=lambda t: not t["gone"]) if t["username"]}
    for it in items:
        it["teacher"] = teacher_of.get((it["author"] or "").lower())
        # The shown name: no title or middle initial (those are on the teacher's own page only).
        it["who"] = it["teacher"]["shown"] if it["teacher"] else it["author"]
    topics = load_topics(db, items)
    mark_elsewhere(items)
    env.globals["side"] = side = side_panel(items)
    # The footer's "Ažurirano" (base.html): the build follows the sync (ci/deploy.sh). UTC; site.js shows local time.
    env.globals["built"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    global shell, site_dir
    shell, site_dir = split_page(env.get_template("base.html").render())[0], site
    (site / "shell.html").write_text(shell, encoding="utf-8")
    # The faculty's subject code often differs from the board's: a subject of the same name the teacher posted in wins.
    posted = defaultdict(dict)
    for it in items:
        if it["teacher"] and it["subj"]:
            posted[it["teacher"]["username"]][fold(it["subj"]["name"])] = it["subj"]
    for t in teachers:
        for s in t["subjects"]:
            s["subj"] = posted[t["username"]].get(fold(s["name"])) or s["subj"]
    for t in teachers:
        if t["gone"]:
            continue
        for s in t["subjects"]:
            if s["subj"] and t not in s["subj"].setdefault("teachers", []):
                s["subj"]["teachers"].append(t)
    book = load_book(db, subjects, teachers)
    render_places(site, topics, smerovi, subjects)
    render_cent(site, subjects)
    write_feeds(site, items, subjects, cent_pushed)
    for it in items:
        write(site / "item" / it["id"] / "index.html", render_item(it), index=False)
    render_teachers(site, teachers, items, book)
    render_book(site, book)
    raspored = render_study_pages(site, db)
    (site / "izbor.json").write_text(json.dumps(dict(picker(subjects, book, teachers, load_katedre(db)), raspored=raspored),
                                                ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write(site / "statistika" / "index.html", env.get_template("stats.html").render(st=archive_stats(items, topics, teachers)))
    about = env.get_template("o_sajtu.html").render()
    write(site / "o-sajtu" / "index.html", about)
    write(site / "about" / "index.html", about, canonical="/o-sajtu/")  # the English address, same page
    vesti = load_vesti(db)
    render_vesti(site, vesti)
    (site / "index.html").write_text(render_home(topics, smerovi, side, sum(not t["gone"] for t in teachers), vesti),
                                     encoding="utf-8")
    (site / "404.html").write_text(env.get_template("error.html").render(), encoding="utf-8")
    write_sitemap(site)
    print(f"{len(items)} items, {len(topics)} topics, {sum(1 for s in subjects.values() if s['live'])} subjects, "
          f"{len(smerovi)} smerovi, {len(teachers)} teachers, {len(book)} book subjects, {len(vesti)} vesti", flush=True)
    npx = shutil.which("npx") or sys.exit("npx not found: Pagefind needs Node.js")
    subprocess.run([npx, "-y", PAGEFIND, "--site", str(site)], check=True)
    strip_pagefind(site)


if __name__ == "__main__":
    assert fold("Ђачки распоред, Čas") == "djacki raspored, cas"
    assert slug(" Душан Љ. Ђукић ") == "dusan-lj-djukic" and slug(short_smer("основне академске студије - МИ")) == "oas-mi"
    _r = [dict(id=1, n="Мата 1"), dict(id=7, n="Mata 1"), dict(id=9, n="Друго")]
    set_hrefs(_r, lambda r: f"/p/{slug(r['n'])}/")
    assert [r["href"] for r in _r] == ["/p/mata-1/", "/p/mata-1-7/", "/p/drugo/"]
    assert subject_name("﻿Цевни  водови (1044) ") == "Цевни водови"
    assert [plural(n, "objava") for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)] == "objava objave objava objava objava objava objave objava objava".split()
    assert [plural(n, "post") for n in (1, 2, 5, 21, 22)] == "post posta postova post posta".split()
    assert [katedra("Катедра за " + k) for k in ("термодинамику", "процесну технику", "теорију механизама и машина",
            "аутоматско управљање", "моторна возила", "моторе", "информационе технологије у машинству")] == [
        "термодинамика", "процесна техника", "теорија механизама и машина", "аутоматско управљање", "моторна возила", "мотори",
        "информационе технологије у машинству"]
    assert env.filters["dmy"]("2026-11-08 10:00") == "08.11.2026."
    assert env.filters["katedra"]("Катедра за механику флуида") == "механика флуида" and env.filters["katedra"](None) == ""
    assert short_smer("основне академске студије - ИТМ") == "ОАС - ИТМ" and short_smer("катедре") == "катедре"
    assert slot_label("Изборни предмет 5.4.5", "5.4") == "Изборни предмет 5.4" and slot_label("Изборни предмет 5.2", "5.2") == "Изборни предмет 5.2"
    assert fold(short_smer(PROGRAMS[0].replace(" — ", " - "))) == fold("ОАС - МИ")
    assert [service(u) for u in ("https://teams.microsoft.com/l/x", "https://docs.google.com/document/d/1", "https://docs.google.com/forms/d/1",
                                 "https://us02web.zoom.us/j/1", "http://ie.mas.bg.ac.rs/x", "https://nastava.mas.bg.ac.rs/x",
                                 "https://masbgacrs-my.sharepoint.com/x", "https://youtu.be/x", "https://mat.mas.bg.ac.rs/moodle/login/",
                                 "http://it0.mas.bg.ac.rs/")] == [
        "Teams", "Google Drive", None, None, "ie.mas.bg.ac.rs", None, "OneDrive", "YouTube", "Moodle", "Moodle"]
    # A mark names who links it, most posts first; only teachers' usernames (for their own pages).
    _s, _t = dict(name="ME"), dict(username="pl")
    _p = lambda who, t, d: dict(kind="post", subj=_s, who=who, teacher=t, posted=d, html='<a href="https://classroom.google.com/c/1">c</a>')
    mark_elsewhere([_p("Ana", None, "2021"), _p("Petar L", _t, "2023"), _p("Petar L", _t, "2026"), dict(kind="post", subj=None)])
    _e = _s["elsewhere"]["Classroom"]
    assert (_e["who"], _e["users"], _e["first"]["posted"], _e["last"]["posted"]) == (["Petar L", "Ana"], {"pl"}, "2021", "2026")
    # One video is not a place, two are, as is a playlist; a meeting and a results sheet are not material.
    def _marks(*urls):
        s = dict(name="S")
        mark_elsewhere([dict(kind="post", subj=s, who="A", teacher=None, posted="2025", html=f'<a href="{u}">v</a>') for u in urls])
        return list(s.get("elsewhere", {}))
    assert _marks("https://youtu.be/a", "https://drive.google.com/drive/folders/x", "https://teams.microsoft.com/l/meetup-join/19x",
                  "https://docs.google.com/spreadsheets/d/e/x/pubhtml") == ["Google Drive"]
    assert _marks("https://youtu.be/a", "https://youtu.be/b") == ["YouTube"] and _marks("https://youtu.be/a") == []
    assert service("https://solfins.sharepoint.com/x") is None
    _a = lambda v: re.search(r'href="([^"]*)"', clean_html(f'<a href="{v}">x</a>'))[1].replace("&amp;", "&")
    assert _a("viewtopic.php?p=1&hilit=%D1%81#p1") == f"{BASE}viewtopic.php?p=1#p1"
    assert _a("viewtopic.php?f=2&sid=0af3&t=9") == f"{BASE}viewtopic.php?f=2&t=9" and _a("viewtopic.php?sid=0af3") == f"{BASE}viewtopic.php"
    assert env.filters["slug"]("Катедра за математику") == "katedra-za-matematiku" and env.filters["slug"](None) == ""
    _m, _k = dict(label="Основне академске студије - МИ"), dict(label="Катедре")
    _a, _b, _c, _e = (dict(id=i, name=n, href=f"/{i}/", count=1, live=True, smer=m) for i, n, m in
                      ((1, "Б", _m), (2, "А", _m), (3, "В", _k), (4, "Г", _k)))
    _b.update(cent=[{}], elsewhere={n: dict(name=n, last=dict(posted=d)) for n, d in
                                    (("Teams", "2021"), ("Moodle", "2024"), ("cent.mas.bg.ac.rs", "2025"))})
    _pl = dict(program=PROGRAMS[0], module=None, semester=3, i=0, slot=None)
    _bk = lambda f, places, **kw: dict(dict(forum=f, places=places, gone=0, id="b", href="/b/", name="Б"), **kw)
    _p = picker({1: _a, 2: _b, 3: _c, 4: _e}, [
        _bk(_a, [_pl, dict(_pl, i=1, slot="4.4", slot_name="Изборни предмет 4.4.5")]), _bk(_c, [dict(_pl, i=2, semester=4)]),
        _bk(None, [dict(_pl, i=3, semester=5)], id="b9", href="/b9/", name="Д"), _bk(None, [_pl], id="b8", gone=1)],
                [dict(shown="Н", href="/n/", gone=0, courses=[dict(subj=_b), dict(subj=None)]),
                 dict(shown="Г", href="/g/", gone=1, courses=[dict(subj=_a)])], {"d": "https://fluidi.mas.bg.ac.rs/d/"})
    _g = lambda n, s: dict(n=n, c=[], s=s)
    assert _p["tree"] == [dict(n=PROGRAMS[0], s=[], c=[
        dict(n="2. godina", s=[], c=[_g("", [0, 2]), _g("Изборни предмет 4.4", [0])]),
        dict(n="3. godina", s=[], c=[_g("", [4])]),
        dict(n="Stari predmeti", s=[], c=[_g("", [1])])]), dict(n="Катедре", s=[], c=[_g("", [3])])], _p["tree"]
    assert _p["teachers"] == [["Н", [1]]] and _p["people"] == [["Н", "/n/"]]
    assert _p["marks"] == {1: ["cent", "Moodle", "Teams"], 4: ["fluidi"]}, _p["marks"]
    # A department page is a subject's when its title or first heading is the name; a list of subjects is none's.
    _db = sqlite3.connect(":memory:")
    _db.execute("CREATE TABLE katedre_pages (url, title, html, gone)")
    _db.executemany("INSERT INTO katedre_pages VALUES (?, ?, ?, 0)", [
        ("https://fluidi.mas.bg.ac.rs/omf/", "Основе механике флуида", ""),
        ("https://etc.mas.bg.ac.rs/mm2.htm", "x", "<h2>Predmet: <b>Mašinski  materijali 2</b></h2>"),
        ("https://motori.mas.bg.ac.rs/oas/", "OAS", "<h1>OAS</h1><h3>Мотори СУС</h3>")])
    assert load_katedre(_db) == {"osnove mehanike fluida": "https://fluidi.mas.bg.ac.rs/omf/",
                                 "masinski materijali 2": "https://etc.mas.bg.ac.rs/mm2.htm"}, load_katedre(_db)
    assert _p["subjects"][0] == ["/1/", "Б"] and _p["subjects"][4:] == [["/b9/", "Д", 0]], _p["subjects"]
    assert first_link('<h1>K</h1><a href="/f/k.pdf?a=1&amp;b=2">Календар  2026</a>') == ("Календар 2026", "/f/k.pdf?a=1&b=2")
    _pr = ('<h2>Raspored 2026</h2><h3>Jesenji semestar</h3><h4>OSNOVNE AKADEMSKE STUDIJE - <b>MAŠINSKO</b> INŽENjERSTVO</h4>'
           '<p>I god. <a href="/f/1.pdf">raspored</a> za obavezne<br/>II god. <a href="/f/2.pdf"> raspored</a></p>'
           '<p>Izborni predmeti: <a href="/f/54.pdf">5.4</a>, <a href="/f/55.pdf">5.5</a><br/>Računarska sala: <a href="/f/3.pdf">324</a></p>'
           '<h4>MASTER AKADEMSKE STUDIJE - INDUSTRIJA 4.0</h4><p>Obavezni (po modulima):<br/><a href="/f/b.pdf">BMI - Biomedicina</a><br/>'
           '<a href="/f/i.pdf">OAS - Informacione - 3. godina</a></p><h4>DOKTORSKE</h4><p>Biće objavljen!</p>')
    _l = parse_lectures(_pr)
    assert (_l["title"], _l["semester"], [p["key"] for p in _l["programs"]]) == (
        "Raspored 2026", "Jesenji semestar", ["osnovne-akademske-studije-masinsko-inzenjerstvo", "master-akademske-studije-industrija-4-0", "doktorske"])
    assert _l["programs"][0] == dict(key=_l["programs"][0]["key"], level="Osnovne akademske studije", name="Mašinsko inženjerstvo",
        cards=[("1", "1. godina", "/f/1.pdf"), ("2", "2. godina", "/f/2.pdf")], electives=[("5.4", "/f/54.pdf"), ("5.5", "/f/55.pdf")],
        rooms=[("324", "/f/3.pdf")], notes=[]), _l["programs"][0]
    assert _l["programs"][1]["cards"] == [("BMI", "Biomedicina", "/f/b.pdf"), ("3", "3. godina", "/f/i.pdf")]
    assert _l["programs"][2]["notes"] == ["Biće objavljen!"] and parse_lectures("<p>x</p>") is None
    _at = attachments(clean_html('<dl class="attachbox"><dt>Attachments</dt><dd><dl class="file"><dt><span class="imageset"></span> '
                                 '<a class="postlink" href="./download/file.php?id=7">Rok &amp; B.PDF</a></dt><dd>(58.7 KiB) Downloaded 4 times'
                                 '</dd></dl></dd></dl>'))
    assert ('<a class="att" href="https://nastava.mas.bg.ac.rs/nastava/download/file.php?id=7" rel="noopener noreferrer">'
            '<span class="att__t att__t--pdf">PDF</span><span class="att__n">Rok &amp; B.PDF<small>58.7 KiB · preuzeto 4 puta</small>'
            '</span></a>') in _at and "<dt>Prilozi</dt>" in _at, _at
    assert attachments(None) is None and attachments("<p>x</p>") == "<p>x</p>"
    _dl = clean_html('<dl class="file"><dt><a class="postlink" href="./download/file.php?id=11&amp;sid=b0c">R&amp;T.zip</a></dt>'
                     '<dd><em>овде</em></dd> <dd>(45.16 KiB) Downloaded 642 times</dd></dl>'
                     '<dl class="file"><dt><a href="./download/file.php?id=12">b.pdf</a></dt><dd>(1 KiB) Downloaded 1 time</dd></dl>')
    assert downloads(_dl) == [(11, "R&T.zip", 642), (12, "b.pdf", 1)] and downloads(None) == [], downloads(_dl)
    assert bars([(2014, 5), (2015, 10)], str) == [dict(label=2014, n=5, pct=50.0, href="2014"), dict(label=2015, n=10, pct=100.0, href="2015")]
    assert ranking(Counter(a=4, b=1, c=2), lambda k: (k.upper(), None, None), k=2) == [
        dict(label="A", href=None, note=None, n=4, pct=100.0), dict(label="C", href=None, note=None, n=2, pct=50.0)]
    assert env.filters["n"](23692) == "23.692" and plural(642, "preuzimanje") == "preuzimanja"
    _at = attachments('<dl>\n<dt><span></span> <a href="/f?id=1" rel="x">a.docx</a></dt>\n<dd><em>Ocene</em></dd> <dd>(1 KiB) preuzeto 2 puta</dd>\n</dl>')
    assert _at == ('<a class="att" href="/f?id=1" rel="noopener noreferrer"><span class="att__t att__t--doc">DOCX</span><span class="att__n">'
                   'a.docx<span class="att__c"><em>Ocene</em></span><small>1 KiB · preuzeto 2 puta</small></span></a>'), _at
    _s, _f = split_page(f"<html><title>T</title><meta>{HEAD_END}<x>{MAIN}a</main><p></main></html>")
    assert (_s, _f) == (f"<html><title></title><x>{MAIN}<!--main--></main></html>",
                        f'<html lang="sr"><title>T</title><meta>{HEAD_END}a</main><p></html>'), (_s, _f)
    assert desc(" a\n b ") == "a b" and desc("aaa bbb ccc", 9) == "aaa bbb…"
    assert lat("Љиљана ЉУБА Ђорђе, Џ. Mašina 2") == "Ljiljana LJUBA Đorđe, Dž. Mašina 2" and lat(None) == ""
    assert lat(Markup("Ш &amp; A")) == Markup("Š &amp; A")
    _bc = breadcrumbs('<nav class="crumbs"><a href="/"><svg></svg>Početna</a><svg></svg><a href="/smer/x/" title="A &amp; B">A &amp; B</a>'
                      '<svg></svg><span class="crumbs__here" aria-current="page">Мата</span></nav>', f"{SITE_URL}/p/")
    assert [(i["position"], i["name"], i["item"]) for i in json.loads(re.search(r">(.*)</script>", _bc)[1])["itemListElement"]] == [
        (1, "Početna", f"{SITE_URL}/"), (2, "A & B", f"{SITE_URL}/smer/x/"), (3, "Мата", f"{SITE_URL}/p/")], _bc
    assert breadcrumbs("<p>no crumbs</p>", SITE_URL) == "" and type(_bc) is str
    assert drop_empty_tables('<table><tr><th>Predmet</th></tr><tr><td> &nbsp;</td></tr></table><p>x</p>') == "<p>x</p>"
    assert drop_empty_tables('<table><tr><td></td><td><b>2.11.</b></td></tr></table>').startswith("<table>")
    assert drop_empty_tables('<h2>A</h2><div><table><td>1</td></table></div><h2>B</h2>\n<div class="l">'
                             '<table><th>x</th><td> </td></table></div>') == '<h2>A</h2><div><table><td>1</td></table></div>\n<div class="l"></div>'
    assert preuzeto("(1 KiB) Downloaded 1 time, Downloaded 22 times") == "(1 KiB) preuzeto 1 puta, preuzeto 22 puta"
    import xml.etree.ElementTree as ET
    _it = dict(id="p5", num=5, title="A & <b>", posted="2026-11-08T14:39:57+00:00", who="Ђ", html="<p>x &amp; y</p>", body="",
               subj=dict(name="Мата 1"), smer=None, thread=dict(href="/tema/3/", posts=[1, 2]))
    _x = ET.fromstring(atom("T", "/predmet/m/", [_it]))
    _ns = {"a": "http://www.w3.org/2005/Atom"}
    assert _x.find("a:entry/a:link", _ns).get("href") == f"{SITE_URL}/tema/3/#p5" and _x.find("a:entry/a:title", _ns).text == "A & <b>"
    assert _x.find("a:entry/a:content", _ns).text == "<p>x &amp; y</p>" and ET.fromstring(atom("T", "/", [])).find("a:updated", _ns) is not None
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
