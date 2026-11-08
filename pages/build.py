# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2"]
# ///
"""Render nastava.db as a static site for GitHub Pages.

Usage: uv run pages/build.py <nastava.db> <out dir>
       uv run pages/build.py --strip <out dir>/site
Writes <out>/site, most pages as fragments of shell.html (split_page). Pagefind runs after this script and writes <out>/site/pagefind; --strip then removes the hidden
text Pagefind read from the item pages.
"""
import json
import re
import shutil
import sqlite3
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
    # The same subject name is in several smerovi, so a subject's URL has its smer's.
    set_hrefs(smerovi.values(), lambda m: f"/smer/{slug(short_smer(m['name']))}/")
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
                          author=p["author"], body=p["content"], html=clean_html(p["html"]),
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
        tags += [("filter", "smer", it["smer"]["name"]), ("meta", "smer", it["smer"]["name"])]
    if it["subject"]:
        tags += [("filter", "predmet", it["subject"]), ("meta", "predmet", it["subject"])]
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
    Run Pagefind again only on a fresh build: on a stripped site it finds no data-pagefind-body."""
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
                 href=f"/tema/{tid}/" if len(rows) > 1 else f"/item/{rows[0]['id']}/",
                 authors="|".join(sorted({(r["author"] or "").lower() for r in rows})),
                 find=fold(" ".join([titles.get(tid) or ""] + [f"{r['title']} {r['who'] or ''}" for r in rows])))
        for r in rows:
            r["thread"] = t
        topics.append(t)
    return sorted(topics, key=lambda t: t["last"]["posted"], reverse=True)


def render_places(site, topics, smerovi, subjects):
    """One page per smer (its subjects and its own topics) and one per subject (its topics), as the board's forum pages.
    Empty subjects get none."""
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
    for m in smerovi.values():
        subs = sorted((s for s in subjects.values() if s["smer"] is m and s["count"]), key=lambda s: fold(s["name"]))
        rows = in_smer[m["id"]]
        m["subjects"], m["topics"] = len(subs), len(rows) + sum(s["topics"] for s in subs)
        m["count"] = sum(len(t["posts"]) for t in rows) + sum(s["count"] for s in subs)
        m["last"] = max([t["last"] for t in rows[:1]] + [s["last"] for s in subs], key=lambda r: r["posted"], default=None)
        write(site / m["href"].strip("/") / "index.html", env.get_template("smer.html").render(smer=m, subjects=subs, topics=rows))
    for t in topics:
        if len(t["posts"]) > 1:
            write(site / "tema" / str(t["id"]) / "index.html", env.get_template("tema.html").render(t=t))


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
        html = clean_html(r["html"], source, lambda value: files.get(media_path(value))) or ""
        # The page's first heading is usually its title, which the page already has as h1.
        m = re.search(r"<h([12])[^>]*>(.*?)</h\1>", html, re.S)
        if m and fold(re.sub(r"<[^>]+>", "", m[2]).strip()) == fold(r["title"]):
            html = html[:m.start()] + html[m.end():]
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
    # A teacher who left the faculty's list (gone) keeps their page and their posts' links; only the list hides them.
    teachers = [dict(t, subjects=taught[t["id"]]) for t in map(dict, db.execute("SELECT * FROM teachers ORDER BY rowid"))]
    set_hrefs(teachers, lambda t: f"/nastavnik/{slug(t['name'])}/")
    for t in teachers:
        # The profile's photo: the faculty's 130 px copy for the list, the original (about 600x700) for the page.
        # shortcut: photos load from www.mas.bg.ac.rs, so they go when the faculty removes one; host copies if that happens.
        m = re.search(r'<img[^>]+src="([^"]*_media/fakultet/nastavnici/[^"]+)"', t["html"] or "")
        t["thumb"] = m and urljoin(STUDY_SITE, unescape(m[1]))
        t["photo"] = m and t["thumb"].split("?")[0]
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
    pages = {f"/fakultet/nastavnici/{t['id']}": t["href"] for t in teachers}
    subj_pages = {f"/studije/predmeti/{s['code']}": s["subj"]["href"]
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
                                          url=f"{STUDY_SITE}studije/predmeti/{s['code']}"))
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


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def short_smer(name):
    """'основне академске студије - МИ' -> 'ОАС - МИ': the faculty's own abbreviations, so a smer fits one line."""
    return re.sub(r"^мастер академске студије", "МАС", re.sub(r"^основне академске студије", "ОАС", name, flags=re.I), flags=re.I)


def side_panel(items, smerovi):
    """The counts of the side panel (sidebar.html), the same on every page."""
    per_smer = Counter(r["smer"]["id"] for r in items if r["smer"])
    years = Counter(r["year"] for r in items if r["year"])
    return dict(total=len(items), kinds=Counter(KIND[r["kind"]] for r in items),
                smerovi=[dict(m, count=per_smer[m["id"]], short=short_smer(m["name"])) for m in smerovi.values() if per_smer[m["id"]]],
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
    env.globals["side"] = side = side_panel(items, smerovi)
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
    render_places(site, topics, smerovi, subjects)
    for it in items:
        write(site / "item" / it["id"] / "index.html", render_item(it))
    render_teachers(site, teachers, items)
    render_study_pages(site, db)
    (site / "index.html").write_text(render_home(topics, smerovi, side, sum(not t["gone"] for t in teachers)), encoding="utf-8")
    (site / "404.html").write_text(env.get_template("error.html").render(status_code=404), encoding="utf-8")
    print(f"{len(items)} items, {len(topics)} topics, {sum(1 for s in subjects.values() if s['count'])} subjects, "
          f"{len(smerovi)} smerovi, {len(teachers)} teachers")


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
    _s, _f = split_page(f"<html><title>T</title><x>{MAIN}a</main><p></main></html>")
    assert (_s, _f) == (f"<html><title></title><x>{MAIN}<!--main--></main></html>", '<html lang="sr"><title>T</title>a</main><p></html>')
    if sys.argv[1] == "--strip":
        strip_pagefind(Path(sys.argv[2]))
    else:
        main(*sys.argv[1:3])
