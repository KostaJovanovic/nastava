# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2"]
# ///
"""Render nastava.db as a static site for GitHub Pages, with its Pagefind search index.

Usage: uv run pages/build.py <nastava.db> <out dir>
Writes <out>/site, most pages as fragments of shell.html (split_page), runs Pagefind (needs Node's npx) into
<out>/site/pagefind, then removes the hidden text Pagefind read from the item pages.
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin

import nh3
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import escape

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from studije import PAGES as STUDY_PAGES, SITE as STUDY_SITE, media_path  # noqa: E402
BASE = "https://nastava.mas.bg.ac.rs/nastava/"
KIND = {"post": "obavestenje", "document": "dokument"}
RECENT = 20
# A followed subject's newest topics in its novo.json (the home page's "Moji predmeti", site.js).
MINE = 10
PAGEFIND = "pagefind@1.6.0"
# shortcut: a document page shows and indexes at most this much text; raise it if GitHub Pages' 1 GB allows.
PAGE_TEXT = 300_000
CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш",
               "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split()))
assert len(CYR) == 30

env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())
# The noun after a number: 1, 21 tema; 2, 3, 4, 22 teme; 5–20, 11–14 tema.
FORMS = {"tema": ("tema", "teme", "tema"), "objava": ("objava", "objave", "objava"),
         "odgovor": ("odgovor", "odgovora", "odgovora"), "predmet": ("predmet", "predmeta", "predmeta"),
         "nastavnik": ("nastavnik", "nastavnika", "nastavnika")}


def plural(n, word):
    one, few, many = FORMS[word]
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


env.filters["pl"] = plural
# An ISO date (2026-11-08...) as the board writes it: 08.11.2026.
env.filters["dmy"] = lambda iso: ".".join(reversed((iso or "")[:10].split("-"))) + "." if iso else ""
# 'Катедра за математику' -> 'математику': in a list headed Katedra the prefix only repeats.
env.filters["katedra"] = lambda k: re.sub(r"^(Катедра|Katedra) (за|za) ", "", k or "")


def fold(s):
    """Serbian Cyrillic to Latin, no diacritics, lower case. search.js folds the query the same way."""
    s = "".join(CYR.get(ch, ch) for ch in (s or "").lower()).replace("đ", "dj")
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))


def slug(s):
    """A name as a URL part: 'Душан Љ. Ђукић' -> 'dusan-lj-djukic'."""
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


# A filter's value in a URL (?katedra=katedra-za-matematiku): Latin only, the shown text stays the name.
env.filters["slug"] = slug


def set_hrefs(rows, path):
    """Give each row href path(row); a name that folds the same as an earlier row's gets the row's id appended.
    rows: in the order they first appeared, so an existing page keeps its URL when a namesake is added later."""
    seen = set()
    for r in rows:
        href = path(r)
        if href in seen:
            href = f"{href[:-1]}-{r['id']}/"
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
    html = re.sub(r"Downloaded (\d+) times?", r"preuzeto \1 puta", re.sub(r">\s*Attachments\s*<", ">Prilozi<", html or ""))
    return nh3.clean(html, tags=nh3.ALLOWED_TAGS | {"tfoot"}, attribute_filter=attribute,
                     url_schemes=nh3.ALLOWED_URL_SCHEMES | {"data"}, link_rel="noopener noreferrer") or None


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
        items.append(dict(id=f"p{p['id']}", kind="post", title=p["title"], smer=smer, subj=subj,
                          subject=subj and subj["name"], date=iso, year=year,
                          topic=p["topic"], num=p["id"], when=p["date"], posted=p["posted"] or "",
                          author=p["author"], body=p["content"], html=clean_html(p["html"]), gone=p["gone"],
                          source_url=f"{BASE}viewtopic.php?p={p['id']}#p{p['id']}"))
    for d in docs.values():
        p = posts.get(d["post"]) or {}
        iso, year = parse_date(p.get("date"), d["uploaded_at"])
        smer, subj = place.get(p.get("forum"), (None, None))
        items.append(dict(id=f"d{d['id']}", kind="document", title=d["title"] or d["filename"], smer=smer, subj=subj,
                          subject=subj and subj["name"], topic=None, when=p.get("date"), posted=p.get("posted") or "",
                          date=iso, year=year, author=p.get("author"), body=(d["text"] or "")[:PAGE_TEXT], html=None,
                          source_url=f"{BASE}viewtopic.php?p={d['post']}#p{d['post']}" if d["post"] else None,
                          doc=dict(filename=d["filename"], size=round((d["size"] or 0) / 1024), uploaded_at=d["uploaded_at"]),
                          download_url=f"{BASE}download/file.php?id={d['id']}"))
    return items


def pagefind_tags(it):
    kind = KIND[it["kind"]]
    tags = [("meta", "title", it["title"] or ""), ("filter", "vrsta", kind), ("meta", "vrsta", kind)]
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
    # The text as written, word for word the indexed folded copy: search.js shows the excerpt in it.
    tags.append(("meta", "tekst", f"{it['title']}\n{it['body'] or ''}"))
    return "".join(f'<meta data-pagefind-{t}="{k}[content]" content="{escape(v)}">' for t, k, v in tags)


def mark_for_pagefind(page, it):
    """Index only a folded copy of the title and text (one copy, so the excerpt does not repeat the title)."""
    assert page.count("</article>") == 1, it["id"]
    folded = escape(fold(f"{it['title']}\n{it['body'] or ''}"))
    return page.replace("</article>", f'<div class="pf" data-pagefind-body>{pagefind_tags(it)}{folded}</div></article>', 1)


def strip_pagefind(site):
    """After Pagefind has indexed the site, drop the hidden copy it read from each item page (~50 MB in all).
    A stripped site cannot be indexed again: it has no data-pagefind-body left."""
    marker = '<div class="pf" data-pagefind-body>'
    assert (site / "pagefind" / "pagefind.js").exists(), "run Pagefind before stripping"
    for path in (site / "item").glob("*/index.html"):
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
shell = None  # shell.html, set by main()


def split_page(html):
    """A page -> (shell, fragment). The shell is the page with an empty <title> and <!--main--> for the main part;
    the fragment is the <title> and the main part, in <html lang="sr"> so that Pagefind reads it.
    The Worker (pages/src/index.js join) puts them together again."""
    t0, t1 = html.index("<title>"), html.index("</title>") + len("</title>")
    m0, m1 = html.index(MAIN) + len(MAIN), html.rindex("</main>")
    return (html[:t0] + "<title></title>" + html[t1:m0] + "<!--main-->" + html[m1:],
            f'<html lang="sr">{html[t0:t1]}{html[m0:m1]}</html>')


def write(path, html):
    """Write only the page's fragment: every page but the home and 404 pages shares shell.html."""
    page_shell, fragment = split_page(html)
    assert page_shell == shell, f"{path}: the page differs from shell.html outside <title> and <main>"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fragment, encoding="utf-8")


def load_topics(db, items):
    """The board's topics, newest last post first. A topic of one post links to that post's page, a longer one to /tema/."""
    titles = dict(db.execute("SELECT id, title FROM topics"))
    posts = defaultdict(list)
    for it in items:
        if it["kind"] == "post":
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
        if rows:
            authors = sorted({(r["author"] or "").lower(): r["who"] for t in rows for r in t["posts"]}.items(), key=lambda a: fold(a[1]))
            write(site / s["href"].strip("/") / "index.html",
                  env.get_template("predmet.html").render(subj=s, topics=rows, authors=authors))
            # Its newest topics as the home page's rows: site.js merges those of the subjects a browser follows.
            (site / s["href"].strip("/") / "novo.json").write_text(json.dumps(
                {"name": s["name"], "rows": [[t["last"]["posted"], str(topic_row(t, place=True))] for t in rows[:MINE]]},
                ensure_ascii=False), encoding="utf-8")
    for m in smerovi.values():
        subs = sorted((s for s in subjects.values() if s["smer"] is m and s["count"]), key=lambda s: fold(s["name"]))
        for s in subs:
            s["find"] = fold(" ".join([s["name"]] + [t["full_name"] for t in s.get("teachers", [])]))
        rows = in_smer[m["id"]]
        m["subjects"], m["topics"] = len(subs), len(rows) + sum(s["topics"] for s in subs)
        m["count"] = sum(len(t["posts"]) for t in rows) + sum(s["count"] for s in subs)
        m["last"] = max([t["last"] for t in rows[:1]] + [s["last"] for s in subs], key=lambda r: r["posted"], default=None)
        write(site / m["href"].strip("/") / "index.html", env.get_template("smer.html").render(smer=m, subjects=subs, topics=rows))
    for t in topics:
        if len(t["posts"]) > 1:
            write(site / "tema" / str(t["id"]) / "index.html", env.get_template("tema.html").render(t=t))


def render_study_pages(site, db):
    """The schedule pages of www.mas.bg.ac.rs (studije.py), with their files served from this site. The newest version
    of a page is at /studije/<slug>/; each older one has a page of its own, linking the files as they were then."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'study_pages'").fetchone():
        return
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

    pages = defaultdict(list)
    for r in db.execute("SELECT * FROM study_pages ORDER BY slug, last_seen DESC"):
        pages[r["slug"]].append(dict(r))
    for name, versions in pages.items():
        source = f"{STUDY_SITE}studije/{name}"
        for i, v in enumerate(versions):
            v["href"] = f"/studije/{name}/" if i == 0 else f"/studije/{name}/{v['first_seen'][:10]}-{v['sha'][:6]}/"
        for v in versions:
            when = None if v is versions[0] else v["last_seen"]
            local = lambda value: (p := media_path(value)) and (file_then(p, when) if when else newest.get(p))
            html = clean_html(v["html"], source, local) or ""
            # The page's first heading is usually its title, which the page already has as h1.
            m = re.search(r"<h([12])[^>]*>(.*?)</h\1>", html, re.S)
            if m and fold(re.sub(r"<[^>]+>", "", m[2]).strip()) == fold(v["title"]):
                html = html[:m.start()] + html[m.end():]
            write(site / v["href"].strip("/") / "index.html", env.get_template("studije.html").render(
                page=v, current=versions[0], versions=versions, html=html, source_url=source))


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
    set_hrefs(teachers, lambda t: f"/nastavnik/{slug(t['name'])}/")
    for t in teachers:
        # The profile's photo: the faculty's 130 px copy for the list, the original (about 600x700) for the page.
        # shortcut: photos load from www.mas.bg.ac.rs, so they go when the faculty removes one; host copies if that happens.
        m = re.search(r'<img[^>]+src="([^"]*_media/fakultet/nastavnici/[^"]+)"', t["html"] or "")
        t["thumb"] = m and urljoin(STUDY_SITE, unescape(m[1]))
        t["photo"] = m and t["thumb"].split("?")[0]
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
                   for t in teachers for s in t["subjects"] if s["subj"] and s["subj"].get("count")}
    for t in teachers:
        t["posts"] = newest(posts[t["username"]]) if t["username"] else []
        # The profile's subjects: one row per archive subject (it can have several codes), archived first.
        mine = Counter(p["subj"]["id"] for p in t["posts"] if p["subj"])
        courses = {}
        for s in t["subjects"]:
            archived = s["subj"] if s["subj"] and s["subj"].get("count") else None
            row = courses.setdefault(archived["id"] if archived else s["code"],
                                     dict(name=s["name"], subj=archived, codes=[], mine=archived and mine[archived["id"]],
                                          url=book_href.get(s["code"]) or f"{STUDY_SITE}studije/predmeti/{s['code']}"))
            row["codes"].append(s["code"])
        # Where they post most first; subjects without their posts after, by name.
        t["courses"] = sorted(courses.values(), key=lambda c: (-(c["mine"] or 0), not c["subj"], azbuka(c["name"])))
        t["find"] = fold(" ".join([t["full_name"], t["title"] or "", t["katedra"] or "", t["email"] or "", t["research"] or "",
                                   t["office"] or ""] + [s["name"] for s in t["subjects"]]))
    for t in teachers:
        source = f"{STUDY_SITE}fakultet/nastavnici/{'emeritus/start' if t['emeritus'] else t['id']}"
        local = lambda v: pages.get(v.split("?")[0]) or subj_pages.get(v.split("?")[0])
        # The profile repeats the name as its first heading and the photo; the page has both above it.
        html = re.sub(r"<h[12][^>]*>.*?</h[12]>", "", t["html"] or "", count=1, flags=re.S)
        html = clean_html(re.sub(r"<img[^>]+_media/fakultet/nastavnici/[^>]+>", "", html, count=1), source, local)
        write(site / t["href"].strip("/") / "index.html",
              env.get_template("nastavnik.html").render(t=t, html=html, source_url=source))
    listed = [t for t in teachers if not t["gone"]]
    katedre = sorted({t["katedra"] for t in listed if t["katedra"]})
    write(site / "nastavnici" / "index.html", env.get_template("nastavnici.html").render(teachers=listed, katedre=katedre))


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
        s["forum"] = by_code.get(s["id"]) or by_name.get((fold(short_smer(s["program"].replace(" — ", " - "))), fold(s["name"])))
        # The holder first, then the other teachers of the page's head ('Извођачи').
        m = re.search(r"Извођачи</strong>(.*?)<br", s["html"] or "", re.S)
        ids = [s["holder"]] + re.findall(r"/fakultet/nastavnici/(\d+)", m[1] if m else "")
        s["teachers"] = [teacher[i] for i in dict.fromkeys(ids) if i in teacher]
        s["holder_t"] = teacher.get(s["holder"])
    # i: the order the plans were read in (predmeti.py: programs, then the modules as the master's page lists them).
    for i, r in enumerate(db.execute("SELECT * FROM subject_places ORDER BY rowid")):
        if r["subject"] in by_id:
            by_id[r["subject"]]["places"].append(dict(r, i=i, label=slot_label(r["slot_name"], r["slot"]) if r["slot"] else None))
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
        if s["forum"] and not s["forum"]["count"]:
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


def picker(subjects, book, teachers):
    """The subject picker ("Moji predmeti", site.js): the subjects with topics, as [href, name]; a tree of them by the
    plans, program > (module >) year of study > group: '' for the required subjects, else the elective block
    ('Изборни предмет 5.4'). The subjects in no plan are under their program's 'Ostalo'; the board's other forums
    (katedre, moduli) are programs with one group. A group has its subjects in s, any other node its children in c.
    teachers: each teacher with the subjects they teach (into the list); people: every listed teacher's
    [name, page], for the header search on a teacher's page.
    After render_places (the counts) and render_teachers (the courses)."""
    live = [s for s in subjects.values() if s.get("count")]
    at = {s["id"]: i for i, s in enumerate(live)}
    tree, placed = {}, set()

    def add(path, s):
        node = tree
        for name in path:
            node = node.setdefault(name, {})
        node.setdefault(None, []).append(at[s["id"]])
        placed.add(s["id"])

    order = {p: i for i, p in enumerate(PROGRAMS)}
    places = [(p, s["forum"]) for s in book if s["forum"] and s["forum"]["id"] in at for p in s["places"]]
    for p, f in sorted(places, key=lambda x: (order.get(x[0]["program"], len(order)), x[0]["i"])):
        group = slot_label(p["slot_name"], p["slot"]) if p["slot"] else ""
        add([p["program"]] + [p["module"]] * bool(p["module"]) + [f"{(p['semester'] + 1) // 2}. godina", group], f)
    for s in live:
        if s["id"] not in placed:
            # The board's smer 'Основне академске студије - МИ' is the plans' 'Основне академске студије — МИ'.
            program = s["smer"]["label"].replace(" - ", " — ")
            add([program, "Ostalo", ""] if " — " in program else [program, ""], s)

    def nodes(tree):
        # The required subjects first, then the elective blocks in the plan's order.
        keys = sorted((k for k in tree if k is not None), key=lambda k: k != "")
        return [dict(n=k, c=nodes(tree[k]), s=sorted(set(tree[k].get(None, [])), key=lambda i: azbuka(live[i]["name"])))
                for k in keys]
    return dict(subjects=[[s["href"], s["name"]] for s in live], tree=nodes(tree),
                teachers=[[t["shown"], sorted({at[c["subj"]["id"]] for c in t["courses"] if c["subj"]})]
                          for t in teachers if not t["gone"] and any(c["subj"] for c in t["courses"])],
                people=[[t["shown"], t["href"]] for t in teachers if not t["gone"]])


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
                year_hist=sorted(years.items()), study_pages=STUDY_PAGES)


def render_home(topics, smerovi, side, n_teachers):
    return env.get_template("search.html").render(
        smerovi=[m for m in smerovi.values() if m["count"]], recent=topics[:RECENT],
        stats=dict(posts=side["total"], topics=len(topics), teachers=n_teachers),
        years_json=json.dumps([y for y, _ in side["year_hist"]]))


def main(db_path, out):
    site = Path(out) / "site"
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(HERE / "static", site / "static")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    place, smerovi, subjects = load_places(db)
    items = load_items(db, place)
    teachers = load_teachers(db, subjects)
    # A board author is a teacher when the username is the teacher's e-mail before @. When two rows share it (a
    # teacher who became emeritus), the one still listed comes last and wins.
    teacher_of = {t["username"]: t for t in sorted(teachers, key=lambda t: not t["gone"]) if t["username"]}
    for it in items:
        it["teacher"] = teacher_of.get((it["author"] or "").lower())
        it["who"] = it["teacher"]["full_name"] if it["teacher"] else it["author"]
    topics = load_topics(db, items)
    env.globals["side"] = side = side_panel(items)
    global shell
    shell = split_page(env.get_template("base.html").render())[0]
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
    for it in items:
        write(site / "item" / it["id"] / "index.html", render_item(it))
    render_teachers(site, teachers, items, book)
    render_book(site, book)
    (site / "izbor.json").write_text(json.dumps(picker(subjects, book, teachers), ensure_ascii=False, separators=(",", ":")),
                                     encoding="utf-8")
    render_study_pages(site, db)
    (site / "index.html").write_text(render_home(topics, smerovi, side, sum(not t["gone"] for t in teachers)), encoding="utf-8")
    (site / "404.html").write_text(env.get_template("error.html").render(), encoding="utf-8")
    print(f"{len(items)} items, {len(topics)} topics, {sum(1 for s in subjects.values() if s['count'])} subjects, "
          f"{len(smerovi)} smerovi, {len(teachers)} teachers, {len(book)} book subjects", flush=True)
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
    assert [plural(n, "tema") for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)] == "tema teme tema tema tema tema teme tema tema".split()
    assert env.filters["dmy"]("2026-11-08 10:00") == "08.11.2026."
    assert env.filters["katedra"]("Катедра за мехнику флуида") == "мехнику флуида" and env.filters["katedra"](None) == ""
    assert short_smer("основне академске студије - ИТМ") == "ОАС - ИТМ" and short_smer("катедре") == "катедре"
    assert slot_label("Изборни предмет 5.4.5", "5.4") == "Изборни предмет 5.4" and slot_label("Изборни предмет 5.2", "5.2") == "Изборни предмет 5.2"
    assert fold(short_smer(PROGRAMS[0].replace(" — ", " - "))) == fold("ОАС - МИ")
    _a = lambda v: re.search(r'href="([^"]*)"', clean_html(f'<a href="{v}">x</a>'))[1].replace("&amp;", "&")
    assert _a("viewtopic.php?p=1&hilit=%D1%81#p1") == f"{BASE}viewtopic.php?p=1#p1"
    assert _a("viewtopic.php?f=2&sid=0af3&t=9") == f"{BASE}viewtopic.php?f=2&t=9" and _a("viewtopic.php?sid=0af3") == f"{BASE}viewtopic.php"
    assert env.filters["slug"]("Катедра за математику") == "katedra-za-matematiku" and env.filters["slug"](None) == ""
    _m, _k = dict(label="Основне академске студије - МИ"), dict(label="Катедре")
    _a, _b, _c, _e = (dict(id=i, name=n, href=f"/{i}/", count=1, smer=m) for i, n, m in
                      ((1, "Б", _m), (2, "А", _m), (3, "В", _k), (4, "Г", _k)))
    _pl = dict(program=PROGRAMS[0], module=None, semester=3, i=0, slot=None)
    _p = picker({1: _a, 2: _b, 3: _c, 4: _e}, [dict(forum=_a, places=[_pl, dict(_pl, i=1, slot="4.4", slot_name="Изборни предмет 4.4.5")]),
                                        dict(forum=_c, places=[dict(_pl, i=2, semester=4)])],
                [dict(shown="Н", href="/n/", gone=0, courses=[dict(subj=_b), dict(subj=None)]),
                 dict(shown="Г", href="/g/", gone=1, courses=[dict(subj=_a)])])
    _g = lambda n, s: dict(n=n, c=[], s=s)
    assert _p["tree"] == [dict(n=PROGRAMS[0], s=[], c=[
        dict(n="2. godina", s=[], c=[_g("", [0, 2]), _g("Изборни предмет 4.4", [0])]),
        dict(n="Ostalo", s=[], c=[_g("", [1])])]), dict(n="Катедре", s=[], c=[_g("", [3])])], _p["tree"]
    assert _p["teachers"] == [["Н", [1]]] and _p["subjects"][0] == ["/1/", "Б"] and _p["people"] == [["Н", "/n/"]]
    _s, _f = split_page(f"<html><title>T</title><x>{MAIN}a</main><p></main></html>")
    assert (_s, _f) == (f"<html><title></title><x>{MAIN}<!--main--></main></html>", '<html lang="sr"><title>T</title>a</main><p></html>')
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
