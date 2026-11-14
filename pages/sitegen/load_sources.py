"""The other sources as board posts: the news, cent's pages and notices, the departments' sites, the mails."""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from html import unescape
from urllib.parse import quote
from bs4 import BeautifulSoup
from translit import fold
from mail import asset_name, TAG as MAIL_TAG
from .clean import CENT_CLASSES, cent_tidy, clean_html, file_rows, linkify
from .known import FORUMS, SITES, SITE_NAMES, SUBJECT_PAGE, VIA
from .load_board import book_subject
from .output import HERE, PAGE_TEXT, VESTI
from .text import parse_date, slug, strip_tags


def load_vesti(db):
    """vesti.py's news, the newest version of each, newest first. Each is also an item for pagefind_tags (no smer,
    subject or author); body: its plain text."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'vesti'").fetchone():
        return []
    cats = dict(db.execute("SELECT id, name FROM vesti_categories"))
    out = []
    for r in db.execute("SELECT * FROM vesti v WHERE modified = (SELECT max(modified) FROM vesti WHERE id = v.id) ORDER BY date DESC"):
        iso, year = parse_date(r["date"])
        names = [cats[c] for c in json.loads(r["categories"]) if c in cats]
        title = unescape(r["title"])
        # upis: in the news site's category Упис (its id 8), the enrollment news (the wiki's upis/vesti lists them).
        out.append(
            dict(
                id=f"v{r['id']}",
                kind="vest",
                href=f"/vest/{r['id']}/",
                title=title,
                date=iso,
                year=year,
                upis=8 in json.loads(r["categories"]),
                posted=f"{r['date_gmt']}Z",
                cats=names,
                cat_keys="|".join(slug(c) for c in names),
                find=fold(" ".join([title] + names)),
                html=clean_html(r["html"], VESTI),
                body=strip_tags(r["html"])[:PAGE_TEXT],
                gone=r["gone"],
                source_url=r["link"],
                smer=None,
                subj=None,
                subject=None,
                author=None,
                who="Mašinski fakultet",
            )
        )
    return out


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
    # A content on five pages or more is cent's template, copied unchanged into the subjects nobody filled in (an old
    # TMO page, with TMO's files): not the subject's. A page has a content once (the key is id, sha).
    copies = Counter(v["sha"] for vs in versions.values() for v in vs)

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
    book = (
        {r["id"]: r for r in db.execute("SELECT id, name, program FROM subjects")}
        if db.execute("SELECT 1 FROM sqlite_master WHERE name = 'subjects'").fetchone()
        else {}
    )
    book_by_name = {}
    for r in book.values():
        book_by_name.setdefault(fold(r["name"]), r["id"])
    subj_of = {}
    for code, r in roots.items():
        code = code if code in book else book_by_name.get(fold(r["title"]))
        if not code:
            print(f"cent: no subject in the book for {r['link']} ({r['title']}, ID {r['code']})", file=sys.stderr)
            continue
        s = subj_of[r["id"]] = book_subject(book[code], smerovi, subjects)
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
            html = clean_html(cent_tidy(n["html"]), p["link"], classes=CENT_CLASSES)
            items.append(
                dict(
                    id=f"c{n['nid']}",
                    kind="cent",
                    title=n["title"],
                    smer=s["smer"],
                    subj=s,
                    subject=s["name"],
                    date=day,
                    year=int(day[:4]),
                    topic=f"c{n['nid']}",
                    num=n["nid"],
                    when=f"{day[8:10]}.{day[5:7]}.{day[:4]}.",
                    posted=posted,
                    author="cent",
                    site=dict(mark="cent", host="cent.mas.bg.ac.rs", name="Katedra za proizvodno mašinstvo"),
                    body=strip_tags(html),
                    html=html,
                    files=[],
                    gone=n["gone"],
                    source_url=p["link"],
                )
            )
        shown, emptied = [], False
        main = f"{s['href']}cent/{p['slug']}/"
        for i, v in enumerate(versions[p["id"]]):
            html = clean_html(cent_tidy(v["html"]), p["link"], classes=CENT_CLASSES) or ""
            # The page's first heading is its name ("Резултати испита"): the title, not repeated under it.
            m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
            title = strip_tags(m[1]) if m else v["title"]
            html = html[: m.start()] + html[m.end() :] if m else html
            if not strip_tags(html) and "<a " not in html:
                emptied = emptied or not shown
                continue
            if copies[v["sha"]] >= 5:
                continue
            # The newest version with content is the page's: a page cent emptied keeps its last content.
            href = main if not shown else f"{main}{v['first_seen'][:10]}-{v['sha'][:6]}/"
            shown.append(dict(title=title, href=href, html=html, first_seen=v["first_seen"], last_seen=v["last_seen"]))
            new = i == len(versions[p["id"]]) - 1
            pushed.append(
                dict(k="s", id=v["rid"], s=s["href"], n=s["name"], t=f"{title}: {'nova stranica' if new else 'izmenjeno'}", u=main)
            )
        if shown:
            s.setdefault("cent", []).append(dict(title=shown[0]["title"], link=p["link"], gone=p["gone"] or emptied, versions=shown))
    return items, pushed


def load_katedre(db, smerovi, subjects):
    """katedre.py's notices of the departments' sites as posts (items), and a subject's material there (s["lit"]:
    dict(mark, n, html), ie's "Literatura" as file rows). A subject's page (SUBJECT_PAGE) is the subject it names (ie:
    its first h1; fluidi: its title): a board subject by that name (SITE_NAMES), punctuation aside ("čovek-mašina",
    "човек - машина"), else the book's (book_subject). A department's page is its forum (FORUMS), but a notice titled
    with a subject's name ("Транспортни уређаји – резултати") is that subject's. Before render_places: such a subject
    has a page."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'katedre_notices'").fetchone():
        return []
    key = lambda name: re.sub(r"[^a-z0-9]", "", fold(name))
    book = (
        list(db.execute("SELECT id, name, program FROM subjects"))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name = 'subjects'").fetchone()
        else []
    )
    katedre = next((m for m in smerovi.values() if m.get("key") == "katedre"), None)

    def board(name, smer=None):
        """The board subjects of a name."""
        return [s for s in subjects.values() if key(s["name"]) == key(name) and (not smer or s["smer"]["key"] == smer)]

    def forum(site):
        s = next((s for s in subjects.values() if s["smer"] is katedre and fold(s["name"]) == fold(FORUMS[site])), None)
        if not s and katedre:
            s = dict(id=f"k:{site}", name=FORUMS[site], smer=katedre, codes=[])
            s["href"] = f"{katedre['href'].replace('/smer/', '/predmet/', 1)}{slug(s['name'])}/"
            subjects[(katedre["id"], s["name"])] = s
        return s

    subj_of, department = {}, set()
    # A page gone from its site (or missed by one crawl) too: its notices stay in the archive, as cent's do.
    for r in db.execute(
        "SELECT url, site, title, html FROM katedre_pages k WHERE last_seen = (SELECT max(last_seen) FROM katedre_pages WHERE url = k.url)"
    ):
        if r["site"] not in FORUMS:  # a site katedre.py no longer reads (etc, motori, ppm): its old pages
            continue
        if not SUBJECT_PAGE.search(r["url"]):
            subj_of[r["url"]] = forum(r["site"])
            department.add(r["url"])
            continue
        soup = BeautifulSoup(r["html"], "html.parser")
        name = (soup.h1.get_text(" ", strip=True) if soup.h1 else "") if r["site"] == "ie" else r["title"]
        name, smer = SITE_NAMES.get(fold(name), (name, None))
        found = board(name, smer)
        b = next((b for b in book if key(b["name"]) == key(name)), None)
        s = found[0] if len(found) == 1 else book_subject(b, smerovi, subjects) if b and not found else None
        if not s:
            print(
                f"katedre: no subject for {r['url']} ({name}{', ' + str(len(found)) + ' of that name' if found else ''})", file=sys.stderr
            )
            continue
        subj_of[r["url"]] = s
        s.setdefault("site", r["url"])
        lit = next((h.parent for h in soup.find_all("h1") if h.get_text(strip=True) == "LITERATURA"), None)
        files = [
            (a["href"], (d := a.find_next_sibling("div")) and d.get_text(" ", strip=True), a.get_text(strip=True))
            for a in (lit.find_all("a", href=True) if lit else [])
        ]
        if files:
            s["lit"] = dict(mark=r["site"], n=len(files), html=file_rows(files, "Literatura"))
    items = []
    for n in db.execute("SELECT * FROM katedre_notices ORDER BY nid"):
        s = subj_of.get(n["url"])
        if n["url"] in department:
            named = next((f for t in (n["title"], re.split(r"\s+[–-]\s+", n["title"])[0]) if len(f := board(t)) == 1), None)
            s = named[0] if named else s
        if not s:
            continue
        day = n["date"] or n["first_seen"][:10]
        # Its date is the notice's; its time the one it was first seen, when that was the same day.
        posted = n["first_seen"] if n["first_seen"][:10] == day else f"{day}T10:00:00+00:00"
        html = linkify(clean_html(n["html"], n["url"])) + file_rows([(h, f, None) for h, f in json.loads(n["files"]) or []])
        items.append(
            dict(
                id=f"k{n['nid']}",
                kind="katedra",
                title=n["title"],
                smer=s["smer"],
                subj=s,
                subject=s["name"],
                date=day,
                year=int(day[:4]),
                topic=f"k{n['nid']}",
                num=n["nid"],
                when=f"{day[8:10]}.{day[5:7]}.{day[:4]}.",
                posted=posted,
                author=n["site"],
                site=dict(mark=n["site"], host=f"{n['site']}.mas.bg.ac.rs", name=SITES[n["site"]]),
                body=strip_tags(html),
                html=html,
                files=[],
                gone=n["gone"],
                source_url=n["url"],
            )
        )
    return items


MAIL = HERE.parent / "mail"


def mail_href(path):
    """A file of mail/ (its path there), as the Worker serves it from the release "mail" (mail.py upload)."""
    return f"/files/{MAIL_TAG}/{asset_name(path)}/{quote(path.rsplit('/', 1)[-1])}"


def load_mail(subjects, folder=MAIL):
    """mail.py's mails as board posts of their subject (post.json's page). A reply is in the topic of the oldest mail
    here it answers; its number (the post's anchor, its order in the topic) is its time, so a mail added later never
    renumbers the others. Its files are the release's (mail_href)."""
    by_href = {s["href"]: s for s in subjects.values()}
    mails = [dict(json.loads(p.read_text(encoding="utf-8")), dir=p.parent.name) for p in sorted(folder.glob("*/post.json"))]
    key = {m["id"]: m["dir"][-8:] for m in mails}
    items = []
    for m in mails:
        s = by_href.get(m["page"])
        if not s:
            print(f"mail: no subject page {m['page']} ({m['dir']})", file=sys.stderr)
            continue
        # Only a "Re:": a new subject line on a reply is a new notice, sent as a reply to keep the list of students.
        root = next((r for r in m["refs"] if r in key), m["id"]) if re.match(r"re:", m["title"], re.I) else m["id"]
        files = [(mail_href(f"{m['dir']}/{f}"), f, f"{m['sizes'][f] / 1024:.1f} KiB") for f in m["files"]]
        html = linkify(clean_html(m["html"]) or "") + file_rows(files)
        day = m["posted"][:10]
        # Where it came from, as a tag beside the author (rows.html who): a Teams or Moodle post, or a mail to the students.
        via = VIA[next((k for k in ("teams", "moodle") if m["id"].startswith(k + ":")), "webmail")]
        items.append(
            dict(
                id=f"m{key[m['id']]}",
                kind="post",
                title=m["title"],
                smer=s["smer"],
                subj=s,
                subject=s["name"],
                date=day,
                year=int(day[:4]),
                topic=f"m{key[root]}",
                num=int(datetime.fromisoformat(m["posted"]).timestamp()),
                when=m["when"],
                posted=m["posted"],
                author=m["author"],
                body=strip_tags(html),
                html=html,
                files=[],
                gone=0,
                source_url=None,
                via=via,
            )
        )
    # teams.py's and moodle.py's material: a Teams class's library beyond its posts' files, a Moodle course's files, in
    # one box on the subject's page; each file with its class's school year and folder. shortcut: a subject with ie's
    # "Literatura" too gets only this box.
    material, sources = defaultdict(list), defaultdict(list)
    for p in sorted(folder.glob("*/material.json")):
        m = json.loads(p.read_text(encoding="utf-8"))
        s = by_href.get(m["page"])
        if not s:
            print(f"mail: no subject page {m['page']} ({p.parent.name})", file=sys.stderr)
            continue
        if (src := m.get("source", "teams")) not in sources[s["href"]]:
            sources[s["href"]].append(src)
        year = (re.search(r"20\d\d/\d+", m["name"]) or [None])[0]
        material[s["href"]] += [
            (
                mail_href(f"{p.parent.name}/{f}"),
                f.rsplit("/", 1)[-1],
                " · ".join(filter(None, [year, f.rsplit("/", 1)[0] if "/" in f else None])),
            )
            for f in m["files"]
        ]
    names = {"teams": "Teams", "moodle": "Moodle"}
    for href, files in material.items():
        src = sources[href]
        title = "Materijal sa " + " i ".join(f"{names[x]}-a" for x in src)
        by_href[href]["lit"] = dict(mark=src[0], title=title, n=len(files), html=file_rows(files, names[src[0]]))
    return items
