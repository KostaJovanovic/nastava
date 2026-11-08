# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2"]
# ///
"""Render nastava.db as a static site for GitHub Pages.

Usage: uv run pages/build.py <nastava.db> <out dir>
Writes <out>/site. Pagefind runs after this script and writes <out>/site/pagefind.
"""
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
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
# shortcut: a document page shows and indexes at most this much text; raise it if GitHub Pages' 1 GB allows.
PAGE_TEXT = 300_000
CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш",
               "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split()))
assert len(CYR) == 30

env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())


def fold(s):
    """Serbian Cyrillic to Latin, no diacritics, lower case. search.js folds the query the same way."""
    s = "".join(CYR.get(ch, ch) for ch in (s or "").lower()).replace("đ", "dj")
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))


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
        # Drop the scraper's phpBB session id from the link.
        return local(value) or urljoin(base, re.sub(r"([?&])sid=[0-9a-f]+&?", r"\1", value).rstrip("?&"))

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
        smer = smerovi.setdefault(top["id"], {"id": top["id"], "name": top["name"]})
        if f is top:
            place[f["id"]] = (smer, None)
            continue
        name = subject_name(f["name"])
        # The lowest forum id of the merged subject names its page.
        subject = subjects.setdefault((top["id"], name), {"id": f["id"], "name": name, "smer": smer, "codes": []})
        subject["codes"] += re.findall(r"\((\d+)\)\s*$", f["name"])
        place[f["id"]] = (smer, subject)
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
                          author=p["author"], body=p["content"], html=clean_html(p["html"]),
                          source_url=f"{BASE}viewtopic.php?p={p['id']}#p{p['id']}"))
    for d in docs.values():
        p = posts.get(d["post"]) or {}
        iso, year = parse_date(p.get("date"), d["uploaded_at"])
        smer, subj = place.get(p.get("forum"), (None, None))
        items.append(dict(id=f"d{d['id']}", kind="document", title=d["title"] or d["filename"], smer=smer, subj=subj,
                          subject=subj and subj["name"],
                          date=iso, year=year, author=p.get("author"), body=(d["text"] or "")[:PAGE_TEXT], html=None,
                          source_url=f"{BASE}viewtopic.php?p={d['post']}#p{d['post']}" if d["post"] else None,
                          doc=dict(filename=d["filename"], size=round((d["size"] or 0) / 1024), uploaded_at=d["uploaded_at"]),
                          download_url=f"{BASE}download/file.php?id={d['id']}"))
    return items


def pagefind_tags(it):
    kind = KIND[it["kind"]]
    tags = [("meta", "title", it["title"] or ""), ("filter", "vrsta", kind), ("meta", "vrsta", kind)]
    if it["smer"]:
        tags += [("filter", "smer", it["smer"]["name"]), ("meta", "smer", it["smer"]["name"])]
    if it["subject"]:
        tags += [("filter", "predmet", it["subject"]), ("meta", "predmet", it["subject"])]
    if it["year"]:
        tags.append(("filter", "godina", str(it["year"])))
    if it["date"]:
        tags += [("sort", "datum", it["date"]), ("meta", "datum", it["date"])]
    return "".join(f'<meta data-pagefind-{t}="{k}[content]" content="{escape(v)}">' for t, k, v in tags)


def mark_for_pagefind(page, it):
    """Index only a folded copy of the title and text (one copy, so the excerpt does not repeat the title)."""
    assert page.count("</article>") == 1, it["id"]
    folded = escape(fold(f"{it['title']}\n{it['body'] or ''}"))
    return page.replace("</article>", f'<div class="pf" data-pagefind-body>{pagefind_tags(it)}{folded}</div></article>', 1)


def render_item(it):
    extra = {k: it[k] for k in ("source_url", "doc", "download_url") if it.get(k)}
    return mark_for_pagefind(env.get_template("detail.html").render(it=it, **extra), it)


def newest(rows):
    return sorted(rows, key=lambda r: r["date"] or "", reverse=True)


def write(path, html):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def render_places(site, items, smerovi, subjects):
    """One page per smer (its subjects and its own notices) and one per subject (all its notices). Empty ones get none."""
    in_subject, in_smer = defaultdict(list), defaultdict(list)
    for it in items:
        if it["subj"]:
            in_subject[it["subj"]["id"]].append(it)
        elif it["smer"]:
            in_smer[it["smer"]["id"]].append(it)
    for s in subjects.values():
        rows = newest(in_subject[s["id"]])
        s["count"], s["last"] = len(rows), rows[0]["date"] if rows else None
        if rows:
            write(site / "predmet" / str(s["id"]) / "index.html", env.get_template("predmet.html").render(subj=s, items=rows))
    for m in smerovi.values():
        subs = sorted((s for s in subjects.values() if s["smer"] is m and s["count"]), key=lambda s: s["name"])
        rows = newest(in_smer[m["id"]])
        m["count"] = len(rows) + sum(s["count"] for s in subs)
        m["last"] = max([r["date"] or "" for r in rows] + [s["last"] or "" for s in subs], default="")
        write(site / "smer" / str(m["id"]) / "index.html", env.get_template("smer.html").render(smer=m, subjects=subs, items=rows))


def render_study_pages(site, db):
    """The schedule pages of www.mas.bg.ac.rs (studije.py), newest version, with their files served from this site."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'study_pages'").fetchone():
        return
    files = {}
    for r in db.execute("SELECT path, data FROM study_files f WHERE last_seen = (SELECT max(last_seen) FROM study_files WHERE path = f.path)"):
        files[r["path"]] = f"/studije/files/{quote(r['path'])}"
        write_bytes(site / "studije" / "files" / r["path"], r["data"])
    for r in db.execute("SELECT * FROM study_pages p WHERE last_seen = (SELECT max(last_seen) FROM study_pages WHERE slug = p.slug)"):
        source = f"{STUDY_SITE}studije/{r['slug']}"
        html = clean_html(r["html"], source, lambda value: files.get(media_path(value)))
        write(site / "studije" / r["slug"] / "index.html",
              env.get_template("studije.html").render(page=dict(r), html=html, source_url=source))


def load_teachers(db, subjects):
    """The teachers (nastavnici.py), each subject linked to its archive page when the board has its code."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'teachers'").fetchone():
        return []
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    taught = defaultdict(list)
    for r in db.execute("SELECT * FROM teacher_subjects ORDER BY name"):
        taught[r["teacher"]].append(dict(code=r["code"], name=r["name"], subj=by_code.get(r["code"])))
    teachers = [dict(t, subjects=taught[t["id"]], katedra_short=re.sub(r"^Катедра за\s+", "", t["katedra"] or ""))
                for t in map(dict, db.execute("SELECT * FROM teachers WHERE gone = 0"))]
    # By surname, then given name, in the order of the Serbian alphabet (as the faculty's list).
    return sorted(teachers, key=lambda t: (azbuka(t["name"].split()[-1]), azbuka(t["name"])))


AZBUKA = {c: i for i, c in enumerate("абвгдђежзијклљмнњопрстћуфхцчџш")}


def azbuka(word):
    return [AZBUKA.get(c, 100 + ord(c)) for c in word.lower()]


def render_teachers(site, teachers, items):
    """A list of all teachers with a filter, and one page per teacher: the faculty's profile and their posts here."""
    posts = defaultdict(list)
    for it in items:
        posts[(it["author"] or "").lower()].append(it)
    pages = {f"/fakultet/nastavnici/{t['id']}": f"/nastavnik/{t['id']}/" for t in teachers}
    subj_pages = {f"/studije/predmeti/{s['code']}": f"/predmet/{s['subj']['id']}/"
                  for t in teachers for s in t["subjects"] if s["subj"] and s["subj"].get("count")}
    for t in teachers:
        t["posts"] = newest(posts[t["username"]]) if t["username"] else []
        t["find"] = fold(" ".join([t["full_name"], t["title"] or "", t["katedra"] or "", t["email"] or "", t["research"] or "",
                                   t["office"] or ""] + [s["name"] for s in t["subjects"]]))
    for t in teachers:
        source = f"{STUDY_SITE}fakultet/nastavnici/{'emeritus/start' if t['emeritus'] else t['id']}"
        local = lambda v: pages.get(v.split("?")[0]) or subj_pages.get(v.split("?")[0])
        # The profile repeats the name as its first heading; the page has it as h1.
        html = clean_html(re.sub(r"<h[12][^>]*>.*?</h[12]>", "", t["html"] or "", count=1, flags=re.S), source, local)
        write(site / "nastavnik" / t["id"] / "index.html",
              env.get_template("nastavnik.html").render(t=t, html=html, source_url=source))
    katedre = sorted({t["katedra"] for t in teachers if t["katedra"]})
    write(site / "nastavnici" / "index.html", env.get_template("nastavnici.html").render(teachers=teachers, katedre=katedre))


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def side_panel(items, smerovi):
    """The counts of the side panel (sidebar.html), the same on every page."""
    subjects = Counter(r["subject"] for r in items if r["subject"])
    per_smer = Counter(r["smer"]["id"] for r in items if r["smer"])
    years = Counter(r["year"] for r in items if r["year"])
    return dict(total=len(items), kinds=Counter(KIND[r["kind"]] for r in items),
                smerovi=[dict(m, count=per_smer[m["id"]]) for m in smerovi.values() if per_smer[m["id"]]],
                subjects=sorted(subjects), subject_counts=subjects, year_hist=sorted(years.items()),
                study_pages=STUDY_PAGES)


def render_home(items, side):
    recent = newest(r for r in items if r["date"])[:RECENT]
    return env.get_template("search.html").render(
        q="", p={}, results=[], recent=recent, total=len(items), smerovi=side["smerovi"], full_side=True,
        years_json=json.dumps([y for y, _ in side["year_hist"]]), pages=0, page=1)


def main(db_path, out):
    site = Path(out) / "site"
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(HERE / "static", site / "static")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    place, smerovi, subjects = load_places(db)
    items = load_items(db, place)
    env.globals["side"] = side = side_panel(items, smerovi)
    write(site / "predmeti.html", env.get_template("predmeti.html").render())
    teachers = load_teachers(db, subjects)
    # A board author is a teacher when the username is the teacher's e-mail before @.
    env.globals["teacher_of"] = {t["username"]: t for t in teachers if t["username"]}
    for it in items:
        write(site / "item" / it["id"] / "index.html", render_item(it))
    for t in teachers:
        for s in t["subjects"]:
            if s["subj"] and t not in s["subj"].setdefault("teachers", []):
                s["subj"]["teachers"].append(t)
    render_places(site, items, smerovi, subjects)
    render_teachers(site, teachers, items)
    render_study_pages(site, db)
    (site / "index.html").write_text(render_home(items, side), encoding="utf-8")
    (site / "404.html").write_text(env.get_template("error.html").render(status_code=404), encoding="utf-8")
    print(f"{len(items)} items, {sum(1 for s in subjects.values() if s['count'])} subjects, {len(smerovi)} smerovi, {len(teachers)} teachers")


if __name__ == "__main__":
    assert fold("Ђачки распоред, Čas") == "djacki raspored, cas"
    assert subject_name("﻿Цевни  водови (1044) ") == "Цевни водови"
    main(*sys.argv[1:3])
