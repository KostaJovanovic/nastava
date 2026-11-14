# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2", "beautifulsoup4==4.15.0"]
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
from collections import Counter, defaultdict
from datetime import date
from html import unescape
from itertools import groupby
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from markupsafe import Markup, escape

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scrapers"))
from studije import PAGES as STUDY_PAGES, SHOWN, SITE as STUDY_SITE, media_path  # noqa: E402
from translit import fold, lat  # noqa: E402
from sitegen.clean import (
    CENT_CLASSES,
    attachments,
    book_page,
    cent_tidy,
    clean_html,
    downloads,
    drop_empty_tables,
    file_rows,
    linkify,
    preuzeto,
)  # noqa: E402
from sitegen.known import (
    CLOUD_STOP,
    HOME_ORDER,
    LINKS,
    MONTHS,
    OWN_SITES,
    QUIET,
    RANKS,
    STIL_FONTS,
    STIL_LOGOS,
    UPIS,
    UPIS_TABS,
    VZ_ITEM,
    VZ_TAGS,
    WEEKDAYS,
)  # noqa: E402
from sitegen.links import mark_elsewhere, service  # noqa: E402
from sitegen.load_board import attachment_files, load_items, load_places, load_topics, row_katedra, side_panel, subject_name  # noqa: E402
from sitegen.load_book import load_book, plan_groups  # noqa: E402
from sitegen.load_sources import load_cent, load_katedre, load_mail, load_vesti  # noqa: E402
from sitegen.load_teachers import bibliography, department_intro, load_teachers, write_photos  # noqa: E402
from sitegen.output import (
    FEED,
    FEED_ALL,
    HEAD_END,
    LazyTemplate,
    MAIN,
    MINE,
    PAGEFIND,
    RECENT,
    VESTI_HOME,
    asset_v,
    breadcrumbs,
    env,
    katedra_href,
    katedra_pages,
    mark_for_pagefind,
    pages,
    snav,
    snav_href,
    split_page,
    strip_pagefind,
    version_static,
    versioned,
    write,
    write_bytes,
    write_page,
    write_sitemap,
)  # noqa: E402
from sitegen.text import (
    BASE,
    LINK,
    PROGRAMS,
    SITE_URL,
    acronyms,
    azbuka,
    desc,
    katedra,
    plural,
    set_hrefs,
    short_smer,
    slot_label,
    slug,
    smer_label,
    strip_tags,
)  # noqa: E402
from sitegen import output  # noqa: E402
from mail import asset_name  # noqa: E402
from wiki_tidy import CLASSES as WIKI_CLASSES, lexicon, recase, tidy as wiki_tidy  # noqa: E402


def render_cent(site, subjects):
    """Each subject's cent pages (load_cent): the newest version at <subject>/cent/<slug>/, each older one under its
    first date. Their links go to cent (the files are not hosted here)."""
    page = env.get_template("cent.html")
    for s in subjects.values():
        for p in s.get("cent", []):
            for v in p["versions"]:
                # Not indexed: a cent page is often exam results, by student.
                write(
                    site / v["href"].strip("/") / "index.html",
                    page.render(
                        page=p,
                        v=v,
                        mark="cent",
                        host="cent.mas.bg.ac.rs",
                        trail=[(s["smer"]["href"], s["smer"]["label"]), (s["href"], s["name"])],
                    ),
                    index=False,
                )


def render_item(it):
    extra = {k: it[k] for k in ("source_url", "doc", "download_url") if it.get(k)}
    return mark_for_pagefind(env.get_template("detail.html").render(it=it, **extra), it)


def newest(rows):
    return sorted(rows, key=lambda r: r["date"] or "", reverse=True)


def render_places(site, topics, smerovi, subjects):
    """One page per smer (its subjects and its own topics) and one per subject (its topics), as the board's forum pages."""
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
        # Every subject has a page, an empty one too (predmet.html quiet).
        # Not teams.py's "Student #N": a number within one thread, no one across the page.
        authors = sorted(
            {
                (r["author"] or "").lower(): r["who"] for t in rows for r in t["posts"] if not (r["author"] or "").startswith("Student #")
            }.items(),
            key=lambda a: fold(a[1]),
        )
        # quiet: a subject without posts says so with one of QUIET, the same one on every build (no change to deploy).
        quiet = QUIET[int(hashlib.md5(s["href"].encode()).hexdigest(), 16) % len(QUIET)]
        write(
            site / s["href"].strip("/") / "index.html",
            env.get_template("predmet.html").render(subj=s, topics=rows, authors=authors, quiet=quiet),
        )
        # Its newest topics as the home page's rows: site.js merges those of the subjects a browser follows.
        (site / s["href"].strip("/")).mkdir(parents=True, exist_ok=True)  # dev mode writes no page there
        (site / s["href"].strip("/") / "novo.json").write_text(
            json.dumps(
                {"name": s["name"], "rows": [[t["last"]["posted"], versioned(str(topic_row(t, place=True)))] for t in rows[:MINE]]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    for m in smerovi.values():
        subs = sorted((s for s in subjects.values() if s["smer"] is m), key=lambda s: fold(s["name"]))
        for s in subs:
            # sorted: a set's order changes from run to run, and with it the page (a deploy with nothing new).
            s["find"] = fold(" ".join([s["name"], *sorted(s["acr"])] + [t["full_name"] for t in s.get("teachers", [])]))
            s["katedra"] = row_katedra(s, in_subject[s["id"]])
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
        return (
            f'<entry><title>{escape(it["title"] or "")}</title><link href="{SITE_URL}{escape(href)}"/>'
            f"<id>{SITE_URL}{escape(page)}</id><updated>{it['posted']}</updated>"
            f"<author><name>{escape(it['who'] or '')}</name></author>"
            + (f'<category term="{escape(place)}"/>' if place else "")
            + f'<content type="html">{escape(it["html"] or it["body"] or "")}</content></entry>'
        )

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="sr">'
        f"<title>{escape(title)}</title><id>{SITE_URL}{escape(path)}</id>"
        f'<link rel="self" href="{SITE_URL}{escape(path)}feed.xml"/><link href="{SITE_URL}{escape(path)}"/>'
        f"<updated>{posts[0]['posted'] if posts else '1970-01-01T00:00:00+00:00'}</updated>"
        + "".join(entry(it) for it in posts)
        + "</feed>\n"
    )


def write_feeds(site, items, subjects, pushed=()):
    """/feed.xml: the board's newest posts; <subject page>/feed.xml: the subject's. Next to a page that exists."""
    posts = sorted((it for it in items if it["kind"] in ("post", "cent", "katedra")), key=lambda it: it["posted"], reverse=True)
    (site / "feed.xml").write_text(atom("Forum nastave · Mašinski fakultet", "/", posts[:FEED_ALL]), encoding="utf-8")
    of = defaultdict(list)
    for it in posts:
        if it["subj"] and len(of[it["subj"]["id"]]) < FEED:
            of[it["subj"]["id"]].append(it)
    for s in subjects.values():
        (site / s["href"].strip("/") / "feed.xml").write_text(
            atom(f"{s['name']} · forum nastave", s["href"], of[s["id"]]), encoding="utf-8"
        )
    # The subjects' newest posts, next to the site (not on it), for ci/push.py: it notifies those newer than a post id.
    # k: "p" a board post, "c" a cent notice, "s" a cent page version; ci/push.py keeps one "before" per kind.
    # a: the teacher who wrote it (their page's slug), for a browser that wants only some teachers' posts of a subject.
    # shortcut: the newest 1000 posts and notices only; a scrape that brings more new posts notifies only these.
    (site.parent / "push.json").write_text(
        json.dumps(
            [
                dict(
                    k=it["id"][0],
                    id=it["num"],
                    s=it["subj"]["href"],
                    n=it["subj"]["name"],
                    t=it["title"] or "",
                    u=post_href(it),
                    **({"a": it["teacher"]["href"].split("/")[2]} if it.get("teacher") else {}),
                )
                for it in posts
                if it["subj"]
            ][:1000]
            + list(pushed),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


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
    out = dict(
        title=next((strip_tags(h) for n, h in heads if n == "2"), ""),
        semester=next((strip_tags(h) for n, h in heads if n == "3"), ""),
        programs=[],
    )
    for part in re.split(r"(?=<h4)", html or "")[1:]:
        head = re.match(r"<h4[^>]*>(.*?)</h4>", part, re.S)
        if not head:
            continue
        # 'OSNOVNE AKADEMSKE STUDIJE - MAŠINSKO INŽENjERSTVO' -> 'Osnovne akademske studije', 'Mašinsko inženjerstvo'
        level, _, name = strip_tags(head[1]).lower().partition(" - ")
        p = dict(
            key=slug(strip_tags(head[1])), level=level.capitalize(), name=name.capitalize(), cards=[], electives=[], rooms=[], notes=[]
        )
        for line in re.split(r"<br\s*/?>|</?p\b[^>]*>|</?div\b[^>]*>", part[head.end() :]):
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
    # The tabs' labels: 'OAS - MI', 'MAS - IND4.0', and the level alone where it has one program ('DAS').
    initials = lambda s: "".join(w[0] for w in s.split() if len(w) > 1).upper()
    for p in out["programs"]:
        name = "IND4.0" if fold(p["name"]).startswith("industrija 4") else initials(p["name"])
        alone = sum(q["level"] == p["level"] for q in out["programs"]) == 1
        p["short"] = initials(p["level"]) + ("" if alone or not name else f" - {name}")
    return out if out["programs"] else None


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
    # Every version of every file: the one seen last keeps the plain URL, an older one is under its hash. Written at
    # the end, only those a shown page links (used): the database also has files of wiki pages no longer shown.
    newest, versions_of, stored, used = {}, defaultdict(list), {}, set()
    for r in db.execute("SELECT path, sha, first_seen FROM study_files ORDER BY path, last_seen DESC"):
        rel = f"v/{r['sha'][:12]}/{r['path']}" if r["path"] in newest else r["path"]
        url = f"/studije/files/{quote(rel)}"
        stored[url] = (rel, r["path"], r["sha"])
        newest.setdefault(r["path"], url)
        versions_of[r["path"]].append((r["first_seen"], url))

    def file_then(path, when):
        """A file as an older page version linked it: the version first seen last by then, else the oldest.
        shortcut: a file that went back to an earlier version links the one before; fine while that is rare."""
        seen = sorted(versions_of.get(path, []))
        then = [url for first, url in seen if first <= when]
        return then[-1] if then else seen[0][1] if seen else None

    def render(versions, base, source, crumb, link=lambda value: None, tidy=None, classes=None, **newest_only):
        """A page's versions, newest first: the newest at base, each older one under its first date. link: a link's
        address on this site, if it has the page (else the faculty's). tidy: the page's html before clean_html keeps
        classes. newest_only: more for the newest one's template (upis/start's tabs). Returns the newest one's html."""
        for i, v in enumerate(versions):
            v["href"] = base if i == 0 else f"{base}{v['first_seen'][:10]}-{v['sha'][:6]}/"
        for v in versions:
            when = None if v is versions[0] else v["last_seen"]

            def local(value, when=when):
                url = (p := media_path(value)) and (file_then(p, when) if when else newest.get(p))
                if url:
                    used.add(url)
                return url or link(value)

            html = drop_empty_tables(clean_html(tidy(v["html"]) if tidy else v["html"], source, local, classes) or "")
            # The page's first heading is usually its title, which the page already has as h1.
            m = re.search(r"<h([12])[^>]*>(.*?)</h\1>", html, re.S)
            if m and fold(re.sub(r"<[^>]+>", "", m[2]).strip()) == fold(v["title"]):
                html = html[: m.start()] + html[m.end() :]
            write(
                site / v["href"].strip("/") / "index.html",
                env.get_template("studije.html").render(
                    page=v,
                    current=versions[0],
                    versions=versions,
                    html=html,
                    source_url=source,
                    crumb_to=crumb,
                    **(newest_only if v is versions[0] else {}),
                ),
            )
            if v is versions[0]:
                newest_html = html
        return newest_html

    pages, now = defaultdict(list), {}
    for r in db.execute("SELECT * FROM study_pages ORDER BY slug, last_seen DESC"):
        pages[r["slug"]].append(dict(r))
    for name, versions in pages.items():
        html = render(versions, f"/studije/{name}/", f"{STUDY_SITE}studije/{name}", ("/raspored/", "Kalendar i rasporedi"))
        now[name] = dict(page=versions[0], html=html)
    render_wiki_pages(site, db, render)
    for url in used:
        rel, path, sha = stored[url]
        (data,) = db.execute("SELECT data FROM study_files WHERE path = ? AND sha = ?", (path, sha)).fetchone()
        write_bytes(site / "studije" / "files" / rel, data)
    get = lambda slug: now.get(slug, {}).get("html")
    calendar, lectures = first_link(get("kalendar-nastave")), parse_lectures(get("raspored-predavanja"))
    write(
        site / "raspored" / "index.html",
        env.get_template("raspored.html").render(
            calendar=calendar,
            lectures=lectures,
            lectures_html=get("raspored-predavanja"),
            exams_html=get("raspored-ispita"),
            sources=[(now[slug]["page"]["href"], title) for slug, title in STUDY_PAGES.items() if slug in now],
            checked=max((n["page"]["last_seen"] for n in now.values()), default=None),
            # Linkovi's Upis i studiranje, under the exam schedule.
            upis=next((g for t, g in link_groups(archived_wiki(db)) if t == "Upis i studiranje"), []),
            icons=link_icons(),
        ),
    )
    return schedule_entries(calendar, lectures, get("raspored-ispita"))


def link_groups(archived):
    """LINKS as link.html shows them: (group, [(name, href, icon, data-domain, the card's second line)]). The second
    line: the address; a shown page of the faculty's its site (its paths are long: vaznidatumioas); with a data-domain
    (the drive), OneDrive. archived: the wiki paths the database has; one it lacks (studije.py not run yet) links the
    faculty's page."""
    wiki = {h[3:] for _, links in LINKS for _, h, _, _ in links if h.startswith("mf:")}
    assert wiki <= SHOWN, f"LINKS has pages studije.py does not keep: {wiki - SHOWN}"
    mf = lambda path: wiki_href(path) if path in archived else STUDY_SITE + path
    return [
        (
            group,
            [
                (name, mf(h[3:]), icon, domain, "www.mas.bg.ac.rs")
                if h.startswith("mf:")
                else (name, h, icon, domain, "OneDrive" if domain else h.split("://")[-1].rstrip("/"))
                for name, h, icon, domain in links
            ],
        )
        for group, links in LINKS
    ]


def link_icons():
    """{host: file} of the sites' own icons in static/link (saved by hand), for the cards (link_card.html)."""
    return {p.stem: p.name for p in (HERE / "static" / "link").iterdir()}


def archived_wiki(db):
    """The wiki paths wiki_pages has (none before studije.py made the table)."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'wiki_pages'").fetchone():
        return set()
    return {r[0] for r in db.execute("SELECT DISTINCT path FROM wiki_pages")}


def wiki_href(path):
    """A shown wiki page's address here: /mf/<path>/, in Latin as the site's other URLs (upis/konkurs-дас)."""
    return "/mf/" + "/".join(map(slug, path.split("/"))) + "/"


def wiki_link(value, hrefs):
    """A link to a page of www.mas.bg.ac.rs that this site keeps (hrefs: {wiki path: its /mf/ href}), as that copy;
    else None. Both forms the wiki writes: /ns/page and doku.php?id=ns:page; a folder's address is its start page."""
    u = urlsplit(urljoin(STUDY_SITE, value))
    if u.netloc not in ("www.mas.bg.ac.rs", "mas.bg.ac.rs"):
        return None
    path = unquote(u.path).strip("/")
    if path == "doku.php":
        path = next((v for k, v in (p.partition("=")[::2] for p in u.query.split("&")) if k == "id"), "")
    path = path.replace(":", "/")
    href = hrefs.get(path) or hrefs.get(path + "/start")
    return href and href + (f"#{u.fragment}" if u.fragment else "")


def render_wiki_pages(site, db, render):
    """The pages of www.mas.bg.ac.rs a student needs (studije.py SHOWN, of wiki_pages; Linkovi lists them, LINKS) at
    wiki_href, as the schedule pages (render, from render_study_pages), linking each other's copies. The rest of the
    wiki is kept in the database, not shown. A page gone from the wiki stays, marked."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'wiki_pages'").fetchone():
        return
    pages = defaultdict(list)
    for r in db.execute(
        f"SELECT * FROM wiki_pages WHERE path IN ({','.join('?' * len(SHOWN))}) ORDER BY path, last_seen DESC", sorted(SHOWN)
    ):
        pages[r["path"]].append(dict(r))
    hrefs = {path: wiki_href(path) for path in pages}
    lex = lexicon(BeautifulSoup(r[0], "html.parser").get_text("\n") for r in db.execute("SELECT html FROM wiki_pages"))
    shown = {}
    for path, versions in sorted(pages.items(), key=lambda kv: kv[0] == UPIS):  # upis/start last: its tabs show the rest
        for v in versions:
            v["title"] = wiki_title(v["title"], lex)
        extra = dict(tabs=upis_tabs(versions[0]["html"], pages, shown, hrefs)) if path == UPIS else {}
        shown[path] = render(
            versions,
            hrefs[path],
            STUDY_SITE + quote(path),
            ("/link/", "Linkovi"),
            link=lambda value: wiki_link(value, hrefs),
            tidy=lambda html, path=path: wiki_tidy(html, path, lex),
            classes=WIKI_CLASSES,
            **extra,
        )


def upis_tabs(raw, pages, shown, hrefs):
    """upis/start's links as tabs (studije.html; site.js shows one at a time, as /raspored/'s programs): each the
    linked page's shown html, its important-dates page linked from it shown above it in place of that link. A dates
    page that only links one page per program shows those; when their timelines are the same, the first, once."""
    soup = BeautifulSoup(raw, "html.parser")
    paths = list(dict.fromkeys(a["data-wiki-id"].replace(":", "/") for a in soup.select("a[data-wiki-id]")))
    paths = [p for p in paths if p in shown]
    if set(paths) != set(UPIS_TABS):
        print(f"[warn] mf/{UPIS}: links {paths}, the tabs expected {list(UPIS_TABS)}", file=sys.stderr)
    by_href = {h: p for p, h in hrefs.items()}
    tabs = []
    for path in paths:
        body = BeautifulSoup(shown[path], "html.parser")
        rok, seen = [], set()
        for a in body.select("a[href]"):
            dates = by_href.get(a["href"].split("#")[0])
            if not dates or "datum" not in dates:
                continue
            block = a.find_parent(["li", "p"]) or a
            if len(block.get_text(" ", strip=True)) < 80:  # "Важни датуми налазе се на линку": the dates replace it
                block.decompose()
            if dates in seen:  # linked again further down
                continue
            seen.add(dates)
            page = BeautifulSoup(shown[dates], "html.parser")
            if page.select_one("ol.wt-tl"):
                rok.append(("", from_timeline(page)))
                continue
            # A program's link: "МАШИНСКО ИНЖЕЊЕРСТВО и за студије на српском и …", named by its program alone.
            subs = [(re.split(r"\s+[иi]\s+за\s", s.get_text(" ", strip=True))[0], by_href.get(s["href"])) for s in page.select("a[href]")]
            subs = [(t, BeautifulSoup(shown[p], "html.parser")) for t, p in subs if p in shown]
            lines = {str(s.select_one("ol.wt-tl")) for _, s in subs}
            if subs and len(lines) == 1:
                rok.append((" и ".join(t for t, _ in subs), from_timeline(subs[0][1])))
            else:
                rok += [(t, from_timeline(s)) for t, s in subs] or [("", str(page))]
        short, name = UPIS_TABS.get(path, (pages[path][0]["title"], pages[path][0]["title"]))
        tabs.append(dict(key=slug(short), short=short, name=name, href=hrefs[path], rok=rok, html=str(body)))
    return tabs


def from_timeline(page):
    """A dates page from its timeline on: what is above it names the program, which the tab and the box already
    say; only a heading naming the round (рок: "Важни датуми и рокови за трећи уписни рок") stays."""
    tl = page.select_one("ol.wt-tl")
    for el in list(tl.find_previous_siblings()) if tl else []:
        if not (re.match(r"h[2-6]$", el.name or "") and "рок" in el.get_text().lower()):
            el.decompose()
    return str(page)


def wiki_title(t, lex=None):
    """A wiki page's title as the site shows it: one in capitals ("УПИС НА ОСНОВНЕ...") in sentence case, its
    acronyms kept (lex: wiki_tidy.lexicon; "VPN"), a page name ("cenovnik") capitalized."""
    if t.isupper():
        return recase(t, lex or {}, True)
    return t[0].upper() + t[1:] if t.islower() else t


def gone_span(t, first_list):
    """A departed teacher's years at the faculty for the archive's card: {from, to, from_est, to_est}, an estimate
    where no source says it. From the past (nastavnici-istorija.jsonl): its span. Off the faculty's list: to, the
    year they left it; from, the earliest of their election report's year (exact), a source's year and their first
    year on the list (exact unless it is the first list's: they were there before)."""
    h = t.get("history") or {}
    if not t["gone"]:
        return None
    if not t["first_seen"]:
        return h.get("span")
    seen = [(int(t["first_seen"][:4]), t["first_seen"][:4] == first_list)]
    seen += [(int(y), True) for y in re.findall(r"\d{4}", h.get("years") or "")]
    if h.get("start"):
        seen.append((h["start"], False))
    start, est = min(seen, key=lambda s: (s[0], s[1]))
    return {"from": start, "to": int(t["last_seen"][:4]), "from_est": est, "to_est": False}


def render_teachers(site, teachers, items, book):
    """A list of all teachers with a filter, and one page per teacher: the faculty's profile and their posts here."""
    posts = defaultdict(list)
    for it in items:
        posts[(it["author"] or "").lower()].append(it)
    pages = {f"/fakultet/nastavnici/{t['id']}": t["href"] for t in teachers}
    # A subject's link: its forum page, else its page in the subject list.
    book_href = {s["id"]: s["href"] for s in book}
    # The year the faculty's lists were first read (2014): a teacher on the first one was there before it.
    first_list = min((t["first_seen"][:4] for t in teachers if t["first_seen"]), default="0000")
    subj_pages = {f"/studije/predmeti/{c}": h for c, h in book_href.items()}
    subj_pages |= {f"/studije/predmeti/{s['code']}": s["subj"]["href"] for t in teachers for s in t["subjects"] if s["subj"]}
    # A page the plans list under several names (Завршни предмет's areas, load_book): one row per name.
    areas = {s["id"] for s in book for p in s["places"] if p["variants"]}
    for t in teachers:
        t["posts"] = newest(posts[t["username"]]) if t["username"] else []
        # The profile's subjects: one row per archive subject (it can have several codes), archived first.
        mine = Counter(p["subj"]["id"] for p in t["posts"] if p["subj"])
        courses = {}
        for s in t["subjects"]:
            archived = s["subj"]
            area = s["code"] in areas
            # One row per name too: a subject the profile lists under two codes ('Трибологија' twice).
            row = courses.setdefault(
                archived["id"] if archived and not area else fold(s["name"]),
                dict(
                    name=s["name"],
                    subj=archived,
                    area=area,
                    codes=[],
                    mine=archived and mine[archived["id"]],
                    url=book_href.get(s["code"]) or f"{STUDY_SITE}studije/predmeti/{s['code']}",
                ),
            )
            row["codes"].append(s["code"])
        # Where they post most first; subjects without their posts after, by name.
        t["courses"] = sorted(courses.values(), key=lambda c: (-(c["mine"] or 0), not c["subj"], azbuka(c["name"])))
        t["find"] = fold(
            " ".join(
                [t["full_name"], t["title"] or "", t["katedra"] or "", t["email"] or "", t["research"] or "", t["office"] or ""]
                + [s["name"] for s in t["subjects"]]
            )
        )
        # How far the grey corner reaches (style.css --p): the longer since they were last at the faculty, the more of
        # the card, evenly by the year, all of it for 1900 and before. No year: none.
        ago = date.today().year - int(t["last_seen"][:4]) if t["gone"] and t["last_seen"][:4] != "0000" else 0
        t["age"] = round(100 * min(1, max(0, ago) / (date.today().year - 1900)))
        t["span"] = gone_span(t, first_list)
        t["biblio"] = bibliography(t["html"], (t.get("history") or {}).get("works"), t["name"])
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
        elif t["off_list"]:
            name = "web.archive.org"
            # The faculty took the profile down: the Wayback Machine's copy nearest the last day it was listed.
            stamp = re.sub(r"\D", "", t["last_seen"])[:14]
            source = f"https://web.archive.org/web/{stamp}/{source}"
        # A page written here (OTHER_TEACHERS) links this site's own pages ("/item/p3263/"): those stay as they are.
        local = lambda v: (
            pages.get(v.split("?")[0])
            or subj_pages.get(v.split("?")[0])
            or (v if t.get("source") and v.startswith("/") and not v.startswith("//") else None)
        )
        # The profile repeats the name as its first heading and the photo; the page has both above it.
        html = re.sub(r"<h[12][^>]*>.*?</h[12]>", "", t["html"] or "", count=1, flags=re.S)
        # Its bibliography is the page's own section (bibliography); clean_html closes what this leaves open.
        html = re.sub(r'<h2[^>]*id="библиографија".*?(?=<h2|$)', "", html, flags=re.S)
        # base: the profile's relative links are the faculty's (or masinac.org's), even when shown from the Wayback copy.
        html = clean_html(re.sub(r"<img[^>]+_media/fakultet/nastavnici/[^>]+>", "", html, count=1), base, local)
        write(
            site / t["href"].strip("/") / "index.html",
            env.get_template("nastavnik.html").render(t=t, html=html, source_url=source, source_name=name),
        )
    listed = [t for t in teachers if not t["gone"] and not t.get("aside")]
    katedre = sorted({t["katedra"] for t in listed if t["katedra"]})
    # Each katedra's icon is a symbol in icons.svg (the cards, nastavnik.html); a new one shows a blank until drawn.
    sprite = (HERE / "static" / "icons.svg").read_text(encoding="utf-8")
    ElementTree.fromstring(sprite)  # one bad tag blanks every icon on the site
    assert all(f'id="i-{k}"' in sprite for k in HOME_ORDER), "icons.svg: a smer of HOME_ORDER has no icon"
    for k in sorted({t["katedra"] for t in teachers if t["katedra"]}):
        if f'id="i-{slug(k)}"' not in sprite:
            print(f'[warn] no icon for {k}: add <symbol id="i-{slug(k)}"> to static/icons.svg', file=sys.stderr)
    # The ones who left, most recent first: a section below the list.
    left = sorted((t for t in teachers if t["gone"]), key=lambda t: t["last_seen"], reverse=True)
    write(site / "nastavnici" / "index.html", env.get_template("nastavnici.html").render(teachers=listed, katedre=katedre, left=left))
    write(
        site / "nastavnici" / "arhiva" / "index.html",
        env.get_template("nastavnici.html").render(
            teachers=left, katedre=sorted({t["katedra"] for t in left if t["katedra"]}), archive=True
        ),
    )
    write(
        site / "nastavnici" / "istrazivaci" / "index.html",
        env.get_template("nastavnici.html").render(teachers=[t for t in teachers if t.get("aside")], katedre=[], researchers=True),
    )


def render_katedre(site, db, teachers, subjects, topics):
    """A page per katedra with listed teachers (/katedra/<name>/): the faculty's text about it and its own site,
    its teachers' cards, its subjects (those whose row has its icon, build.py row_katedra) by smer, and the newest
    topics in them."""
    dept = {}
    if db.execute("SELECT 1 FROM sqlite_master WHERE name = 'departments'").fetchone():
        dept = {r["name"]: r for r in db.execute("SELECT * FROM departments")}
    listed = [t for t in teachers if not t["gone"] and not t.get("aside")]
    newest = defaultdict(list)
    for t in topics:  # newest first
        if t["subj"] and t["subj"].get("katedra") and len(newest[t["subj"]["katedra"]]) < 15:
            newest[t["subj"]["katedra"]].append(t)
    for k in sorted(katedra_pages):
        d = dept.get(k)
        intro, own = department_intro(d["html"]) if d else ("", None)
        subs = sorted(
            (s for s in subjects.values() if s.get("katedra") == k),
            key=lambda s: (HOME_ORDER.index(s["smer"]["key"]) if s["smer"].get("key") in HOME_ORDER else 99, -s["topics"], fold(s["name"])),
        )
        groups = [(m["label"], list(rows)) for m, rows in groupby(subs, key=lambda s: s["smer"])]
        write(
            site / katedra_href(k).strip("/") / "index.html",
            env.get_template("katedra.html").render(
                k=k,
                intro=intro,
                own=own or OWN_SITES.get(k),
                source=d and f"{STUDY_SITE}organizacija/katedre/{d['id']}",
                teachers=[t for t in listed if t["katedra"] == k],
                groups=groups,
                n_subjects=len(subs),
                topics=newest[k],
            ),
        )


def render_book(site, book):
    """A list of all subjects with a filter, grouping and sorting, and one page per subject: the faculty's page."""
    for s in book:
        write(
            site / s["href"].strip("/") / "index.html",
            env.get_template("predmet_opis.html").render(
                s=s, page=book_page(s["html"]), source_url=f"{STUDY_SITE}studije/predmeti/{s['id']}"
            ),
        )
    listed = [s for s in book if not s["gone"]]
    write(
        site / "predmeti" / "index.html",
        env.get_template("predmeti.html").render(
            plans=plan_groups(book),
            n=len(listed),
            finds={s["id"]: s["find"] for s in listed},
            katedre=sorted({s["katedra"] for s in listed if s["katedra"]}),
            programs=[p for p in PROGRAMS if any(s["program"] == p for s in listed)],
        ),
    )


def picker(subjects, book, teachers, items=()):
    """The subject picker (/mojipredmeti/, site.js): the subjects with topics, as [href, name]; a tree of them by the
    plans, program > (module >) year of study > group: '' for the required subjects, else the elective block
    ('Изборни предмет 5.4'). Every subject of the plans is in it: one with topics as its board subject, one without
    as its page in the subject book, [href, name, 0]. A board subject in no plan (a subject the faculty no longer
    has) is under its program's 'Stari predmeti'; the board's other forums (katedre, moduli) are programs with one
    group. A group has its subjects in s, any other node its children in c.
    teachers: each teacher with the board subjects they teach (into the list); people: every listed teacher's
    [name, page], for the header search on a teacher's page. posters: per subject (as subjects), the teachers who
    posted in it as [index in people, posts], most first: the picker's second step, whose notifications to get.
    After render_places (the counts) and render_teachers (the courses)."""
    live = list(subjects.values())
    entries = [[s["href"], s["name"]] for s in live]
    acr = [" ".join(sorted(s.get("acr", ()))) for s in live]
    # ki: each subject's katedra icon (icons.svg i-<slug>), as its row on the forum has (row_katedra), for the header search.
    # Only a katedra has one (the Katedre forum's 'Laboratorija CIAH' does not).
    icon = lambda k: slug(k) if k and slug(k).startswith("katedra-") else ""
    ki = [icon(s.get("katedra")) for s in live]
    at = {("f", s["id"]): i for i, s in enumerate(live)}
    tree, placed = {}, set()

    def index(b):
        """A plan's subject in the list: its board subject when that has topics, else its page in the book."""
        f = b["forum"]
        key = ("f", f["id"]) if f else ("b", b["id"])
        if key not in at:
            at[key] = len(entries)
            entries.append([b["href"], b["name"], 0])
            acr.append(" ".join(sorted(b.get("acr", ()))))
            ki.append(icon(b.get("katedra")))
        placed.add(key)
        return at[key]

    def add(path, i):
        node = tree
        for name in path:
            node = node.setdefault(name, {})
        node.setdefault(None, []).append(i)

    order = {p: i for i, p in enumerate(PROGRAMS)}
    places = [(p, b) for b in book if not b["gone"] for p in b["places"]]
    for p, b in sorted(places, key=lambda x: (order.get(x[0]["program"], len(order)), x[0]["i"])):
        group = slot_label(p["slot_name"], p["slot"]) if p["slot"] else ""
        add([p["program"]] + [p["module"]] * bool(p["module"]) + [f"{(p['semester'] + 1) // 2}. godina", group], index(b))
    for s in live:
        if ("f", s["id"]) not in placed:
            # The board's smer 'Основне академске студије - МИ' is the plans' 'Основне академске студије — МИ'.
            program = (s["smer"]["name"][:1].upper() + s["smer"]["name"][1:]).replace(" - ", " — ")
            add([program, "Stari predmeti", ""] if " — " in program else [program, ""], at[("f", s["id"])])

    def nodes(tree):
        # The required subjects first, then the elective blocks in the plan's order.
        keys = sorted((k for k in tree if k is not None), key=lambda k: k != "")
        return [dict(n=k, c=nodes(tree[k]), s=sorted(set(tree[k].get(None, [])), key=lambda i: azbuka(entries[i][1]))) for k in keys]

    def person(t):
        """[name, page, photo, title · katedra]; one who left: [name, page, photo, title · years, the grey corner's
        length (style.css --p), or None when no year is known (hatched)], as their card on /nastavnici/."""
        if not t["gone"]:
            return [t["shown"], t["href"], t["thumb"], " · ".join(filter(None, [t["title"], katedra(t["katedra"])]))]
        s = t["span"] or {}
        est = lambda y, guess: f"~{y}" if guess else str(y)
        years = s.get("to") and (
            (f"{est(s['from'], s.get('from_est'))}–" if s["from"] != s["to"] else "") if s.get("from") else "do "
        ) + est(s["to"], s.get("to_est"))
        undated = t["last_seen"][:4] == "0000"
        return [t["shown"], t["href"], t["thumb"], " · ".join(filter(None, [t["title"], years])), None if undated else t["age"]]

    listed = Counter(t["katedra"] for t in teachers if not t["gone"] and t["katedra"])
    people = sorted((t for t in teachers if not t.get("aside")), key=lambda t: t["gone"])
    who = {t["href"]: i for i, t in enumerate(people)}
    posts = Counter((it["subj"]["id"], it["teacher"]["href"]) for it in items if it["subj"] and it["teacher"])
    posters = [[] for _ in entries]
    for (s, t), n in sorted(posts.items(), key=lambda x: -x[1]):
        if ("f", s) in at:
            posters[at[("f", s)]].append([who[t], n])
    # acr: each subject's acronyms (acronyms), for the searches.
    return dict(
        subjects=entries,
        acr=acr,
        ki=ki,
        tree=nodes(tree),
        posters=posters,
        teachers=[
            [t["shown"], sorted({at[("f", c["subj"]["id"])] for c in t["courses"] if c["subj"]})]
            for t in teachers
            if not t["gone"] and any(c["subj"] for c in t["courses"])
        ],
        # The listed teachers first, then the ones who left (the header search shows them where there is room).
        people=[person(t) for t in people],
        # [full name, short name, icon slug, listed teachers, its page (render_katedre)].
        katedre=[[k, katedra(k).capitalize(), slug(k), n, katedra_href(k)] for k, n in sorted(listed.items(), key=lambda x: azbuka(x[0]))],
    )


def bars(pairs, href=None):
    """[(label, count)] -> the rows of a bar chart (stats.html chart), each bar's height in % of the highest."""
    top = max((n for _, n in pairs), default=0) or 1
    return [dict(label=label, n=n, pct=round(n / top * 100, 1), href=href and href(label)) for label, n in pairs]


def ranking(counts, row, k=10):
    """The k highest counts as rows of a ranked list (stats.html rank); row(key) -> (label, href, note)."""
    top = counts.most_common(k)
    return [dict(zip(("label", "href", "note"), row(key)), n=n, pct=round(n / top[0][1] * 100, 1)) for key, n in top]


# What in a post's text is not its words: a link, an e-mail, a file's name, an attachment's "(1.2 MiB) preuzeto 5 puta".
NOT_WORDS = re.compile(
    r"\S*(?:://|www\.|@)\S*|\S+\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|7z|jpe?g|png|gif|txt|dwg|m)\b"
    r"|\([\d.,]+ [KMG]?i?B\) preuzeto \d+ puta",
    re.I,
)


def post_words(it):
    """A post's words for the word cloud (stats.html): its title and text in Latin, lower case, without its
    attachments' names, links and file names."""
    text = it["title"] + "\n" + it["body"]
    for _, name, _ in it["files"]:
        text = text.replace(name, " ")
    return [w for w in re.findall(r"[^\W\d_]{4,}", lat(NOT_WORDS.sub(" ", text)).lower()) if w not in CLOUD_STOP]


CASE_END = re.compile(r"(?:ima|ama|omu|ega|emu|om|em|og|oj|im|ih|a|e|i|u|o)$")


def same_words(counts):
    """{word: count} -> {word: count} with a word's cases as one (ispit, ispita, ispitu): the forms whose stem (the
    word without its case ending) is the same; each shown as its stem when that is a common form (ispit; not a typo or
    an abbreviation, smen.), else its most frequent.
    shortcut: endings only, no dictionary: a sound change (zadatak, zadaci) stays apart; a stemmer if that matters."""
    stems = defaultdict(Counter)
    for w, n in counts.items():
        s = CASE_END.sub("", w)
        stems[s if len(s) >= 3 else w][w] += n
    # The "a" a word has only in some cases (studenata, petak) goes when the stem without it is there (student, petk).
    for s in list(stems):
        if (t := re.sub(r"a(\w)$", r"\1", s)) != s and t in stems:
            stems[t].update(stems.pop(s))
    return Counter({max(c, key=lambda w: (w == s and c[w] * 4 >= max(c.values()), c[w])): c.total() for s, c in stems.items()})


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
    upload = lambda f: (
        names[f],
        f"/item/{files[f][1]['id']}/",
        " · ".join(filter(None, [files[f][1]["subject"] or files[f][1]["who"], env.filters["dmy"](files[f][1]["date"])])),
    )

    years = Counter(it["year"] for it in dated)
    months = Counter((it["year"], int(it["date"][5:7])) for it in dated)
    top_month = max(months.values(), default=1)
    hours = Counter(int(m[1]) for it in posts if (m := re.search(r"(\d{1,2}):\d\d", it["when"] or "")))
    days = Counter(date.fromisoformat(it["date"][:10]).weekday() for it in dated)
    busiest = Counter(it["date"][:10] for it in dated).most_common(1)
    topic = {t["href"]: t for t in topics}
    words = same_words(Counter(w for it in posts for w in post_words(it)))

    listed = [t for t in teachers if not t["gone"]]
    posting = {t["username"] for t in listed if t["username"] and t["username"] in tally["authors"]}
    by_teachers = sum(1 for it in posts if it["teacher"])
    return dict(
        first=min(dated, key=lambda it: it["date"], default=None),
        last=max(dated, key=lambda it: it["date"], default=None),
        totals=[
            (len(posts), "post"),
            (len(topics), "thread"),
            (len(tally["authors"]), "autor"),
            (len(tally["subjects"]), "predmet"),
            (len(files), "prilog"),
            (sum(tally["files"].values()), "preuzimanje"),
        ],
        years=bars(sorted(years.items()), lambda y: f"/?from={y}&to={y}"),
        heat=[
            dict(year=y, cells=[dict(m=MONTHS[m - 1], n=months[(y, m)], pct=round(months[(y, m)] / top_month * 100)) for m in range(1, 13)])
            for y in sorted(years)
        ],
        hours=bars([(h, hours[h]) for h in range(24)]),
        days=bars([(d, days[i]) for i, d in enumerate(WEEKDAYS)]),
        busiest=busiest[0] if busiest else None,
        words=sorted(ranking(words, lambda w: (w, f"/?q={quote(fold(w))}", None), k=60), key=lambda r: fold(r["label"])),
        authors=ranking(tally["authors"], author),
        subjects=ranking(tally["subjects"], subject),
        smerovi=ranking(tally["smerovi"], smer, k=20),
        files=ranking(tally["files"], upload),
        teacher_dl=ranking(tally["teacher_dl"], teacher),
        subject_dl=ranking(tally["subject_dl"], subject),
        smer_dl=ranking(tally["smer_dl"], smer, k=20),
        longest=ranking(
            Counter({t["href"]: len(t["posts"]) for t in topics}),
            lambda h: (topic[h]["title"], h, topic[h]["subj"] and topic[h]["subj"]["name"]),
        ),
        teachers=dict(
            listed=len(listed),
            emeritus=sum(1 for t in listed if t["emeritus"]),
            gone=len(teachers) - len(listed),
            posting=len(posting),
            share=round(by_teachers / (len(posts) or 1) * 100),
            titles=[(r, n) for r in RANKS if (n := sum(1 for t in listed if t["title"] == r))],
            katedre=ranking(
                Counter(t["katedra"] for t in listed if t["katedra"]),
                lambda k: (env.filters["katedra"](k).capitalize(), katedra_href(k), None),
            ),
        ),
    )


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
        write(
            site / year_href[y].strip("/") / "index.html",
            env.get_template("vesti.html").render(vesti=rows, year=y, years=years, year_href=year_href, cats=cats, total=len(vesti)),
        )
    (site / "vesti").mkdir(exist_ok=True)  # dev mode writes no page there
    (site / "vesti" / "feed.xml").write_text(atom("Vesti · Mašinski fakultet", "/vesti/", vesti[:FEED_ALL]), encoding="utf-8")


def render_objave(site, topics):
    """All the board's topics, newest last post first, as /vesti/: a list per year of the last post (the newest year
    at /objave/, each other at /objave/<year>/), with a filter. The home page's Najnovije objave link here."""
    years = sorted({t["last"]["year"] for t in topics if t["last"]["year"]}, reverse=True)
    if not years:
        return
    year_href = {y: "/objave/" if y == years[0] else f"/objave/{y}/" for y in years}
    for y in years:
        rows = [t for t in topics if t["last"]["year"] == y]
        authors = sorted(
            {
                (r["author"] or "").lower(): r["who"]
                for t in rows
                for r in t["posts"]
                if r["author"] and not r["author"].startswith("Student #")
            }.items(),
            key=lambda a: fold(a[1] or a[0]),
        )
        write(
            site / year_href[y].strip("/") / "index.html",
            env.get_template("objave.html").render(
                topics=rows, year=y, years=years, year_href=year_href, authors=authors, total=len(topics)
            ),
        )


def render_home(topics, smerovi, side, n_teachers, vesti):
    live = [m for m in smerovi.values() if m.get("live")]
    live.sort(key=lambda m: HOME_ORDER.index(m["key"]) if m["key"] in HOME_ORDER else len(HOME_ORDER))
    return env.get_template("search.html").render(
        home=True,
        smerovi=live,
        recent=topics[:RECENT],
        vesti=vesti[:VESTI_HOME],
        stats=dict(posts=side["total"], topics=len(topics), teachers=n_teachers),
        years_json=json.dumps([y for y, _ in side["year_hist"]]),
    )


def load_verzije(text):
    """verzije.md (its own head says how it is written) -> the days of /verzije/, newest first:
    [{date, lead, span, n, parts: [{head, items: [{v, tag, html}]}]}]. Every commit 1..N must be listed exactly once."""
    inline = lambda s: Markup(re.sub(r"`(.+?)`", r"<span data-notx>\1</span>", re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(escape(s)))))
    days, seen = [], []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        date, *lines = block.rstrip().split("\n")
        rows = []
        for line in lines:
            if line.startswith("  ") and rows:
                rows[-1] += " " + line.strip()
            elif line.strip():
                rows.append(line.strip())
        day = dict(date=date.strip(), lead=None, parts=[dict(head=None, items=[])], nums=[])
        for r in rows:
            if r.startswith("### "):
                day["parts"].append(dict(head=r[4:], items=[]))
            elif r.startswith("- "):
                m = VZ_ITEM.fullmatch(r)
                spans = [(int(a), int(b or a)) for a, _, b in (s.partition("–") for s in m[1].split(", "))] if m[1] else []
                assert not m[2] or m[2] in VZ_TAGS, f"verzije.md: unknown tag [{m[2]}]"
                for a, b in spans:
                    day["nums"] += range(a, b + 1)
                day["parts"][-1]["items"].append(
                    dict(v=", ".join(f"0.{a}" if a == b else f"0.{a}–0.{b}" for a, b in spans), tag=VZ_TAGS.get(m[2]), html=inline(m[3]))
                )
            else:
                assert not day["lead"], f"verzije.md, {date}: one lead line a day, then the entries"
                day["lead"] = inline(r)
        lo, hi = min(day["nums"]), max(day["nums"])
        day.update(n=len(day["nums"]), span=f"0.{lo}" if lo == hi else f"0.{lo}–0.{hi}")
        seen += day.pop("nums")
        days.append(day)
    missing, twice = set(range(1, max(seen) + 1)) - set(seen), {n for n in seen if seen.count(n) > 1}
    assert not missing and not twice, f"verzije.md: commits missing {sorted(missing)}, listed twice {sorted(twice)}"
    return days


def css_colors(css):
    """style.css -> [(--name, light, dark)] of each variable holding a colour, first definition only (the old Safari
    block repeats them). A plain colour is the same in both themes."""
    seen = {}
    for name, value in re.findall(r"^\s*(--[\w-]+):\s*([^;]+);", css, re.M):
        if name in seen or not (value.startswith("light-dark(") or re.fullmatch(r"#[0-9a-fA-F]{3,8}", value)):
            continue
        if value.startswith("light-dark("):
            inner, depth = value[len("light-dark(") : -1], 0
            for i, c in enumerate(inner):  # the comma between the two, not one inside color-mix()
                depth += (c == "(") - (c == ")")
                if c == "," and not depth:
                    break
            seen[name] = (inner[:i].strip(), inner[i + 1 :].strip())
        else:
            seen[name] = (value, value)
    return [(n, *v) for n, v in seen.items()]


def png_size(path):
    head = path.read_bytes()[:24]  # the IHDR chunk: width and height, big-endian, at bytes 16 and 20
    return f"{int.from_bytes(head[16:20])}×{int.from_bytes(head[20:24])}"


def stil_data():
    static = HERE / "static"
    sprite = (static / "icons.svg").read_text(encoding="utf-8")
    # Each symbol as an SVG of its own, for its download link (a data: URL: no files to write).
    icons = [
        dict(id=i, svg=f'<svg xmlns="http://www.w3.org/2000/svg"{attrs}>{body}</svg>')
        for i, attrs, body in re.findall(r'<symbol id="([^"]+)"([^>]*)>(.*?)</symbol>', sprite, re.S)
    ]
    assert len(icons) == sprite.count("<symbol"), "icons.svg: a symbol /stil/ did not read"
    logos = [dict(name=n, size=png_size(static / n) if n.endswith(".png") else "SVG") for n in STIL_LOGOS]
    posters = sorted(p.name for p in static.iterdir() if p.name.startswith("og") and p.suffix in (".png", ".jpg"))
    fonts = [dict(name=n, family=f, files=files, weights=w, use=u) for n, f, files, w, u in STIL_FONTS]
    assert all((static / "fonts" / f).exists() for t in fonts for f in t["files"]), "STIL_FONTS: a file not in static/fonts"
    return dict(
        colors=css_colors((static / "style.css").read_text(encoding="utf-8")), icons=icons, logos=logos, posters=posters, fonts=fonts
    )


def main(db_path, out, dev_mode=False):
    output.dev = dev = dev_mode
    if dev:  # see Lazy
        env.template_class = LazyTemplate
        env.cache.clear()
        pages.clear()
    site = Path(out) / "site"
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(HERE / "static", site / "static")
    version_static(site / "static")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    place, smerovi, subjects = load_places(db)
    cent_items, cent_pushed = load_cent(db, smerovi, subjects)
    items = load_items(db, place) + cent_items + load_katedre(db, smerovi, subjects) + load_mail(subjects)
    teachers = load_teachers(db, subjects)
    if teachers:
        write_photos(db, site)
    katedra_pages.clear()
    katedra_pages.update(t["katedra"] for t in teachers if not t["gone"] and not t.get("aside") and t["katedra"])
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
    # The footer's "Provereno" (base.html): when nastava.py last read the board, not when this ran. UTC; site.js shows
    # local time. None (no line in the footer): a database from before the meta table.
    # Not "checked": raspored.html has its own (the schedule pages' last read), which would change the footer there.
    try:
        env.globals["forum_checked"] = (db.execute("SELECT value FROM meta WHERE key = 'forum_synced'").fetchone() or [None])[0]
    except sqlite3.OperationalError:
        env.globals["forum_checked"] = None
    output.site_dir = site
    output.shell = shell = split_page(str(env.get_template("base.html").render()))[0]
    (site / "shell.html").write_text(versioned(shell), encoding="utf-8")
    nav = shell[shell.index('<nav class="snav"') :]
    snav[:] = re.findall(r'<a href="([^"]+)"', nav[: nav.index("</nav>")])
    # join() marks the shell's first <a href="..."> with the link's href: that one must be in .snav.
    assert all(shell.index(f'<a href="{h}"') > shell.index('<nav class="snav"') for h in snav), "a link before .snav"
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
    titles = defaultdict(list)
    for t in topics:
        if t["subj"]:
            titles[t["subj"]["id"]].append(t["title"])
    for s in subjects.values():
        s["acr"] = acronyms(s["name"], titles[s["id"]])
    book = load_book(db, subjects, teachers)
    render_places(site, topics, smerovi, subjects)
    render_cent(site, subjects)
    write_feeds(site, items, subjects, cent_pushed)
    for it in items:
        write(site / "item" / it["id"] / "index.html", render_item(it), index=False)
    render_teachers(site, teachers, items, book)
    render_katedre(site, db, teachers, subjects, topics)
    render_book(site, book)
    raspored = render_study_pages(site, db)
    links = link_groups(archived_wiki(db))
    (site / "izbor.json").write_text(
        json.dumps(
            dict(
                picker(subjects, book, teachers, items),
                raspored=raspored,
                # The researchers and demonstrators for the header search: [name, page, title].
                istrazivaci=[[t["shown"], t["href"], t["title"]] for t in teachers if t.get("aside")],
                # Linkovi's cards for it too: [name, second line, href, data-domain].
                linkovi=[[n, shown, h, d] for _, group in links for n, h, _, d, shown in group],
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    write(site / "statistika" / "index.html", env.get_template("stats.html").render(st=archive_stats(items, topics, teachers)))
    write(site / "mojipredmeti" / "index.html", env.get_template("mojipredmeti.html").render(), index=False)
    about = env.get_template("o_sajtu.html").render()
    write(site / "o-sajtu" / "index.html", about)
    write(site / "about" / "index.html", about, canonical="/o-sajtu/")  # the English address, same page
    write(site / "stil" / "index.html", env.get_template("stil.html").render(**stil_data()))
    write(site / "link" / "index.html", env.get_template("link.html").render(icons=link_icons(), groups=links))
    days = lambda: load_verzije((HERE.parent / "verzije.md").read_text(encoding="utf-8"))
    page = env.get_template("verzije.html").render(days=days())
    if dev:
        page.fresh["days"] = days
    write(site / "verzije" / "index.html", page)
    vesti = load_vesti(db)
    render_vesti(site, vesti)
    render_objave(site, topics)
    write_page(site / "index.html", render_home(topics, smerovi, side, sum(not t["gone"] and not t.get("aside") for t in teachers), vesti))
    write_page(site / "404.html", env.get_template("error.html").render())
    if dev:
        return
    write_sitemap(site)
    print(
        f"{len(items)} items, {len(topics)} topics, {len(subjects)} subjects, "
        f"{len(smerovi)} smerovi, {len(teachers)} teachers, {len(book)} book subjects, {len(vesti)} vesti",
        flush=True,
    )
    npx = shutil.which("npx") or sys.exit("npx not found: Pagefind needs Node.js")
    subprocess.run([npx, "-y", PAGEFIND, "--site", str(site)], check=True)
    strip_pagefind(site)


if __name__ == "__main__":
    assert fold("Ђачки распоред, Čas") == "djacki raspored, cas"
    assert (
        wiki_title("УПИС 2026/2027.") == "Упис 2026/2027." and wiki_title("cenovnik") == "Cenovnik" and wiki_title("ОАС Упис") == "ОАС Упис"
    )
    hrefs = {"upis/oas": "/mf/upis/oas/", "biblioteka/start": "/mf/biblioteka/start/"}
    assert (
        wiki_link("/upis/oas#rok", hrefs) == "/mf/upis/oas/#rok"
        and wiki_link("https://www.mas.bg.ac.rs/biblioteka", hrefs) == "/mf/biblioteka/start/"
    )
    assert wiki_link("/doku.php?id=upis:oas", hrefs) == "/mf/upis/oas/" and wiki_link("https://ie.mas.bg.ac.rs/upis/oas", hrefs) is None
    assert wiki_link("/_media/upis/oas.pdf", hrefs) is None
    assert acronyms("Основи отпорности конструкција") == {"ook"} and acronyms("Машински елементи 1") == {"me1", "me"}
    assert acronyms("Математика 1", ["МАТ1 рок", "МИ - вежбе"]) == {"m1", "mat1"} and acronyms("Електротехника") == set()
    assert acronyms("Понашање заварених спојева у експлоатацији") == {"pzsue", "pzse"}
    assert acronyms("Биомедицинска инструментација и опрема", ["BMIO - испит", "ДОМАЋИ 2", "ОМ ПРВИ ДЕО", "ММ1 рок"]) == {
        "biio",
        "bio",
        "bmio",
    }
    assert css_colors(
        ":root {\n  --a: #fff;\n  --m: light-dark(color-mix(in srgb, #b 16%, transparent), #c);\n  --r: 6px;\n  --a: #000; }"
    ) == [("--a", "#fff", "#fff"), ("--m", "color-mix(in srgb, #b 16%, transparent)", "#c")]
    asset_v["site.js"] = "ab"
    assert versioned('<script src="/static/site.js"> `/static/site.js#${k}` /static/site.js?v=ab /static/sw.js /static/site.json') == (
        '<script src="/static/site.js?v=ab"> `/static/site.js?v=ab#${k}` /static/site.js?v=ab /static/sw.js /static/site.json'
    )
    asset_v.clear()
    assert snav_href("/nastavnik/x/", ["/", "/nastavnici/", "/vesti/"]) == "/nastavnici/"
    assert snav_href("/", ["/", "/vesti/"]) == "/" and snav_href("/tema/1/", ["/", "/vesti/"]) is None
    assert slug(" Душан Љ. Ђукић ") == "dusan-lj-djukic" and slug(short_smer("основне академске студије - МИ")) == "oas-mi"
    _r = [dict(id=1, n="Мата 1"), dict(id=7, n="Mata 1"), dict(id=9, n="Друго")]
    set_hrefs(_r, lambda r: f"/p/{slug(r['n'])}/")
    assert [r["href"] for r in _r] == ["/p/mata-1/", "/p/mata-1-7/", "/p/drugo/"]
    assert subject_name("﻿Цевни  водови (1044) ") == "Цевни водови"
    assert [
        plural(n, "thread") for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)
    ] == "thread threada threadova threadova threadova thread threada threadova threadova".split()
    assert [plural(n, "post") for n in (1, 2, 5, 21, 22)] == "post posta postova post posta".split()
    _v = load_verzije("note\n## 2. x\nLead **b**.\n- 2–3 [novo] **A** `B`\n  dalje\n### H\n- 1, 4 C <i>\n")[0]
    assert (_v["span"], _v["n"], _v["lead"]) == ("0.1–0.4", 4, Markup("Lead <b>b</b>.")), _v
    assert _v["parts"][0]["items"] == [dict(v="0.2–0.3", tag=("Novo", "new"), html=Markup("<b>A</b> <span data-notx>B</span> dalje"))]
    assert _v["parts"][1]["head"] == "H" and _v["parts"][1]["items"][0]["html"] == Markup("C &lt;i&gt;"), _v
    assert [
        katedra("Катедра за " + k)
        for k in (
            "термодинамику",
            "процесну технику",
            "теорију механизама и машина",
            "аутоматско управљање",
            "моторна возила",
            "моторе",
            "информационе технологије у машинству",
        )
    ] == [
        "термодинамика",
        "процесна техника",
        "теорија механизама и машина",
        "аутоматско управљање",
        "моторна возила",
        "мотори",
        "информационе технологије у машинству",
    ]
    assert env.filters["dmy"]("2026-11-08 10:00") == "08.11.2026."
    assert env.filters["katedra"]("Катедра за механику флуида") == "механика флуида" and env.filters["katedra"](None) == ""
    assert short_smer("основне академске студије - ИТМ") == "ОАС - ИТМ" and short_smer("катедре") == "катедре"
    assert (
        slot_label("Изборни предмет 5.4.5", "5.4") == "Изборни предмет 5.4"
        and slot_label("Изборни предмет 5.2", "5.2") == "Изборни предмет 5.2"
    )
    assert fold(short_smer(PROGRAMS[0].replace(" — ", " - "))) == fold("ОАС - МИ")
    assert [
        service(u)
        for u in (
            "https://teams.microsoft.com/l/x",
            "https://docs.google.com/document/d/1",
            "https://docs.google.com/forms/d/1",
            "https://us02web.zoom.us/j/1",
            "http://ie.mas.bg.ac.rs/x",
            "https://nastava.mas.bg.ac.rs/x",
            "https://masbgacrs-my.sharepoint.com/x",
            "https://youtu.be/x",
            "https://mat.mas.bg.ac.rs/moodle/login/",
            "http://it0.mas.bg.ac.rs/",
        )
    ] == ["Teams", "Google Drive", None, None, "ie.mas.bg.ac.rs", None, "OneDrive", "YouTube", "Moodle", "Moodle"]
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

    assert _marks(
        "https://youtu.be/a",
        "https://drive.google.com/drive/folders/x",
        "https://teams.microsoft.com/l/meetup-join/19x",
        "https://docs.google.com/spreadsheets/d/e/x/pubhtml",
    ) == ["Google Drive"]
    assert _marks("https://youtu.be/a", "https://youtu.be/b") == ["YouTube"] and _marks("https://youtu.be/a") == []
    assert service("https://solfins.sharepoint.com/x") is None
    _a = lambda v: re.search(r'href="([^"]*)"', clean_html(f'<a href="{v}">x</a>'))[1].replace("&amp;", "&")
    assert _a("viewtopic.php?p=1&hilit=%D1%81#p1") == f"{BASE}viewtopic.php?p=1#p1"
    assert _a("viewtopic.php?f=2&sid=0af3&t=9") == f"{BASE}viewtopic.php?f=2&t=9" and _a("viewtopic.php?sid=0af3") == f"{BASE}viewtopic.php"
    assert env.filters["slug"]("Катедра за математику") == "katedra-za-matematiku" and env.filters["slug"](None) == ""
    _t = lambda k: dict(katedra=k)
    _post = lambda k: dict(posts=[dict(teacher=_t(k)), dict(teacher=None)])
    assert row_katedra(dict(name="катедра за моторе", smer=dict(key="katedre")), []) == "катедра за моторе"
    assert row_katedra(dict(smer=dict(key="x"), info=dict(katedra=None, holder_t=_t("Б"), teachers=[])), []) == "Б"
    assert row_katedra(dict(smer=dict(key="moduli")), [_post("А"), _post("В"), _post("В")]) == "В"
    assert row_katedra(dict(smer=dict(key="x")), []) is None
    _m, _k = dict(name="основне академске студије - МИ"), dict(name="катедре")
    assert smer_label(_m["name"]) == "Основне академске студије - Машинско инжењерство" and smer_label("катедре") == "Катедре"
    _a, _b, _c, _e = (
        dict(id=i, name=n, href=f"/{i}/", count=1, smer=m) for i, n, m in ((1, "Б", _m), (2, "А", _m), (3, "В", _k), (4, "Г", _k))
    )
    _pl = dict(program=PROGRAMS[0], module=None, semester=3, i=0, slot=None)
    _bk = lambda f, places, **kw: dict(dict(forum=f, places=places, gone=0, id="b", href="/b/", name="Б"), **kw)
    _p = picker(
        {1: _a, 2: _b, 3: _c, 4: _e},
        [
            _bk(_a, [_pl, dict(_pl, i=1, slot="4.4", slot_name="Изборни предмет 4.4.5")]),
            _bk(_c, [dict(_pl, i=2, semester=4)]),
            _bk(None, [dict(_pl, i=3, semester=5)], id="b9", href="/b9/", name="Д"),
            _bk(None, [_pl], id="b8", gone=1),
        ],
        [
            dict(
                shown="Г",
                href="/g/",
                gone=1,
                courses=[dict(subj=_a)],
                thumb=None,
                title="доцент",
                katedra=None,
                span={"from": 1950, "to": 1980, "from_est": True},
                last_seen="1980",
                age=40,
            ),
            dict(
                shown="Н",
                href="/n/",
                gone=0,
                courses=[dict(subj=_b), dict(subj=None)],
                thumb="/foto/n.jpg",
                title="доцент",
                katedra="Катедра за математику",
            ),
            dict(
                shown="Ж", href="/z/", gone=1, courses=[], thumb=None, title=None, katedra=None, span={"to": 1990}, last_seen="0000", age=0
            ),
        ],
        [dict(subj=_b, teacher=dict(href="/n/"))] * 2
        + [dict(subj=_a, teacher=dict(href="/g/")), dict(subj=_b, teacher=None), dict(subj=None, teacher=dict(href="/n/"))],
    )
    assert _p["posters"] == [[[1, 1]], [[0, 2]], [], [], []], _p["posters"]
    _g = lambda n, s: dict(n=n, c=[], s=s)
    assert _p["tree"] == [
        dict(
            n=PROGRAMS[0],
            s=[],
            c=[
                dict(n="2. godina", s=[], c=[_g("", [0, 2]), _g("Изборни предмет 4.4", [0])]),
                dict(n="3. godina", s=[], c=[_g("", [4])]),
                dict(n="Stari predmeti", s=[], c=[_g("", [1])]),
            ],
        ),
        dict(n="Катедре", s=[], c=[_g("", [3])]),
    ], _p["tree"]
    assert _p["teachers"] == [["Н", [1]]] and _p["people"] == [
        ["Н", "/n/", "/foto/n.jpg", "доцент · математика"],
        ["Г", "/g/", None, "доцент · ~1950–1980", 40],
        ["Ж", "/z/", None, "do 1990", None],
    ], _p["people"]
    assert _p["katedre"] == [["Катедра за математику", "Математика", "katedra-za-matematiku", 1, katedra_href("Катедра за математику")]], (
        _p["katedre"]
    )
    katedra_pages.add("Катедра за математику")
    assert katedra_href("Катедра за математику") == "/katedra/matematika/", katedra_href("Катедра за математику")
    katedra_pages.clear()
    assert katedra_href("Катедра за моторе") == "/nastavnici/arhiva/?katedra=katedra-za-motore"
    _d = (
        '<h1 id="k">Катедра за x</h1><div class="level1"><div class="wrap_related wrap_right plugin_wrap"><p>'
        '<a href="http://x.mas.bg.ac.rs/" class="urlextern"> веб сајт</a></p></div><p>Текст.</p></div>'
        '<div class="plugin_include_content x"><h2>Наставници</h2></div>'
    )
    assert department_intro(_d) == ("<div><p>Текст.</p></div>", "http://x.mas.bg.ac.rs/"), department_intro(_d)
    _b = bibliography(
        '<div id="nastavnici-bibliografija"><h3>Радови у часописима ван SCI и SCIe листа</h3><div><p>\n'
        'Marić Ana, Lazović Tatjana M. (2014). <a href="https://m/h/1"> Wear</a>, Tribology, 3(2).<br/>\n'
        'ISSN: 1, <a href="https://dx.doi.org/10.1/x">10.1/x</a>, M24.\n</p></div></div>',
        [dict(title="Wear", year=2014, url="https://m/h/1"), dict(title="Old", year=1999, url="https://m/h/2")],
        "Татјана М. Лазовић-Капор",
    )
    assert _b == [
        dict(
            kind="časopis",
            authors=[("Marić Ana", False), ("Lazović Tatjana M.", True)],
            year=2014,
            title="Wear",
            url="https://m/h/1",
            venue="Tribology, 3(2)",
            doi="10.1/x",
            m="M24",
        ),
        dict(kind=None, authors=[], year=1999, title="Old", url="https://m/h/2", venue="", doi=None, m=None),
    ], _b
    # An ie notice is a post of the subject its page's h1 names, punctuation aside; its written links are links, its
    # files a post's; the page's "Literatura" is the subject's material; a page no subject has is left out.
    assert file_rows([("javascript:alert(1)", "x.pdf", None)]) == "" and "https://a/b.pdf" in file_rows([("https://a/b.pdf", "b", None)])
    assert linkify('Link: https://1drv.ms/x?e=V&amp;a=1. <a href="https://a/b">https://a/b</a>') == (
        'Link: <a href="https://1drv.ms/x?e=V&amp;a=1" rel="noopener noreferrer">https://1drv.ms/x?e=V&amp;a=1</a>. '
        '<a href="https://a/b">https://a/b</a>'
    )
    _db = sqlite3.connect(":memory:")
    _db.row_factory = sqlite3.Row
    _db.execute("CREATE TABLE katedre_pages (url, sha, site, title, html, first_seen, last_seen, gone)")
    _db.execute("CREATE TABLE katedre_notices (nid, key, site, url, title, label, date, html, files, first_seen, last_seen, gone)")
    _u = "https://ie.mas.bg.ac.rs/predmeti_p.php?SchoolSubjectID=19"
    _db.executemany(
        "INSERT INTO katedre_pages VALUES (?, 'ab', 'ie', 'IE', ?, '2026-11-11T05:00:00+00:00', '2026-11-11T05:00:00+00:00', 0)",
        [
            (
                _u,
                "<h1>Projektovanje sistema čovek-mašina</h1><section><h1>LITERATURA</h1><div><div>"
                '<a href="https://ie.mas.bg.ac.rs/data_store/upload/90_pz_1.pdf">90_pz_1.pdf</a><div>Predavanje 1</div></div></div></section>',
            ),
            ("https://ie.mas.bg.ac.rs/predmeti_p.php?SchoolSubjectID=38", "<h1>Engineering Management and Economics</h1>"),
        ],
    )
    _db.execute(
        "INSERT INTO katedre_notices VALUES (7, 'k', 'ie', ?, 'Kolokvijum', '05.11.2026', '2026-11-05', "
        "'Rezultati: https://1drv.ms/x', '[[\"https://ie.mas.bg.ac.rs/data_store/upload/1815_R_2.docx\", \"1815_R_2.docx\"]]', "
        "'2026-11-11T05:42:23+00:00', '2026-11-11T05:42:23+00:00', 0)",
        (_u,),
    )
    _sm = dict(key="mas-mi", short="МАС - МИ", href="/smer/mas-mi/")
    _subj = {1: dict(id=1, name="Пројектовање система човек - машина", smer=_sm, codes=["0520"])}
    import contextlib, io

    with contextlib.redirect_stderr(io.StringIO()):
        _k = load_katedre(_db, {1: _sm}, _subj)
    assert [(i["id"], i["subj"]["id"], i["date"], i["posted"], i["site"]["mark"]) for i in _k] == [
        ("k7", 1, "2026-11-05", "2026-11-05T10:00:00+00:00", "ie")
    ], _k
    assert (
        '<a href="https://1drv.ms/x"' in _k[0]["html"] and 'att__t--doc">DOCX</span><span class="att__n">R_2.docx</span>' in _k[0]["html"]
    )
    assert _subj[1]["site"] == _u and _subj[1]["lit"]["n"] == 1 and "Predavanje 1<small>pz_1.pdf</small>" in _subj[1]["lit"]["html"]
    # A department's notice is its forum's (made when the board has none), or the subject its title names.
    _db.execute(
        "INSERT INTO katedre_pages VALUES ('https://meh.mas.bg.ac.rs/vesti/', 'ab', 'meh', 'Вести', '', "
        "'2026-11-11T05:00:00+00:00', '2026-11-11T05:00:00+00:00', 0)"
    )
    _db.executemany(
        "INSERT INTO katedre_notices VALUES (?, ?, 'meh', 'https://meh.mas.bg.ac.rs/vesti/', ?, ?, '2026-06-11', "
        "'<p>a</p>', '[]', '2026-11-11T05:42:23+00:00', '2026-11-11T05:42:23+00:00', 0)",
        [(8, "k8", "Транспортни уређаји – резултати", "x"), (9, "k9", "Обавештење", "y")],
    )
    _kat = dict(id=2, key="katedre", href="/smer/katedre/", short="катедре")
    _subj = {1: dict(id=1, name="Транспортни уређаји", smer=_sm, codes=[])}
    with contextlib.redirect_stderr(io.StringIO()):
        _k = load_katedre(_db, {1: _sm, 2: _kat}, _subj)
    assert [(i["id"], i["subj"]["id"]) for i in _k] == [("k8", 1), ("k9", "k:meh")], _k
    assert _subj[(2, "катедра за механизацију")]["href"] == "/predmet/katedre/katedra-za-mehanizaciju/"
    # A mail's "Re:" is in the topic of the oldest mail it answers that is here; one answering a mail not here, or with
    # a new subject line, starts its own.
    import tempfile

    with tempfile.TemporaryDirectory() as _t:
        for _d, _id, _refs, _at, _ti in [
            ("2026-01-01-aaaaaaaa", "<a>", [], "09:00", "T"),
            ("2026-01-02-bbbbbbbb", "<b>", ["<x>", "<a>"], "09:00", "Re: T"),
            ("2026-01-03-cccccccc", "<c>", ["<a>", "<b>"], "08:00", "RE: T"),
            ("2026-01-04-dddddddd", "<d>", ["<x>"], "09:00", "Re: X"),
            ("2026-01-05-eeeeeeee", "<e>", ["<a>"], "09:00", "Novo"),
        ]:
            (Path(_t) / _d).mkdir()
            # No file on disk: the build has only post.json (the files are in the release).
            (Path(_t) / _d / "post.json").write_text(
                json.dumps(
                    dict(
                        id=_id,
                        refs=_refs,
                        page="/1/",
                        author="llecic",
                        posted=f"{_d[:10]}T{_at}:00+00:00",
                        when="",
                        title=_ti,
                        html='<div style="x">Hi <script>x</script></div>',
                        files=["r.pdf"] if _id == "<a>" else [],
                        sizes={"r.pdf": 2048} if _id == "<a>" else {},
                    )
                ),
                encoding="utf-8",
            )
        (Path(_t) / "teams-x").mkdir()
        (Path(_t) / "teams-x" / "material.json").write_text(
            json.dumps(dict(page="/1/", name="T 2025/2026. godina", files=["Predavanja/P 1.pdf", "a.docx"])), encoding="utf-8"
        )
        _ms = dict(id=1, name="S", smer=_sm, href="/1/")
        _m = load_mail({1: _ms}, Path(_t))
    assert _ms["lit"]["n"] == 2 and f'href="/files/mail/{asset_name("teams-x/Predavanja/P 1.pdf")}/P%201.pdf"' in _ms["lit"]["html"], _ms[
        "lit"
    ]
    assert "P 1.pdf<small>2025/2026 · Predavanja</small>" in _ms["lit"]["html"] and "a.docx<small>2025/2026</small>" in _ms["lit"]["html"]
    assert [(i["id"], i["topic"]) for i in _m] == [
        ("maaaaaaaa", "maaaaaaaa"),
        ("mbbbbbbbb", "maaaaaaaa"),
        ("mcccccccc", "maaaaaaaa"),
        ("mdddddddd", "mdddddddd"),
        ("meeeeeeee", "meeeeeeee"),
    ], _m
    assert _m[0]["num"] < _m[1]["num"] < _m[2]["num"] and "script" not in _m[0]["html"] and "style=" not in _m[0]["html"]
    assert (
        f'href="/files/mail/{asset_name("2026-01-01-aaaaaaaa/r.pdf")}/r.pdf"' in _m[0]["html"] and "<small>2.0 KiB</small>" in _m[0]["html"]
    ), _m[0]["html"]
    assert _p["subjects"][0] == ["/1/", "Б"] and _p["subjects"][4:] == [["/b9/", "Д", 0]], _p["subjects"]
    assert first_link('<h1>K</h1><a href="/f/k.pdf?a=1&amp;b=2">Календар  2026</a>') == ("Календар 2026", "/f/k.pdf?a=1&b=2")
    _pr = (
        "<h2>Raspored 2026</h2><h3>Jesenji semestar</h3><h4>OSNOVNE AKADEMSKE STUDIJE - <b>MAŠINSKO</b> INŽENjERSTVO</h4>"
        '<p>I god. <a href="/f/1.pdf">raspored</a> za obavezne<br/>II god. <a href="/f/2.pdf"> raspored</a></p>'
        '<p>Izborni predmeti: <a href="/f/54.pdf">5.4</a>, <a href="/f/55.pdf">5.5</a><br/>Računarska sala: <a href="/f/3.pdf">324</a></p>'
        '<h4>MASTER AKADEMSKE STUDIJE - INDUSTRIJA 4.0</h4><p>Obavezni (po modulima):<br/><a href="/f/b.pdf">BMI - Biomedicina</a><br/>'
        '<a href="/f/i.pdf">OAS - Informacione - 3. godina</a></p><h4>DOKTORSKE</h4><p>Biće objavljen!</p>'
    )
    _l = parse_lectures(_pr)
    assert (_l["title"], _l["semester"], [p["key"] for p in _l["programs"]]) == (
        "Raspored 2026",
        "Jesenji semestar",
        ["osnovne-akademske-studije-masinsko-inzenjerstvo", "master-akademske-studije-industrija-4-0", "doktorske"],
    )
    assert _l["programs"][0] == dict(
        key=_l["programs"][0]["key"],
        level="Osnovne akademske studije",
        name="Mašinsko inženjerstvo",
        cards=[("1", "1. godina", "/f/1.pdf"), ("2", "2. godina", "/f/2.pdf")],
        electives=[("5.4", "/f/54.pdf"), ("5.5", "/f/55.pdf")],
        rooms=[("324", "/f/3.pdf")],
        notes=[],
        short="OAS",
    ), _l["programs"][0]
    assert [
        p["short"] for p in parse_lectures(_pr.replace("DOKTORSKE", "MASTER AKADEMSKE STUDIJE - MAŠINSKO INŽENjERSTVO"))["programs"]
    ] == ["OAS", "MAS - IND4.0", "MAS - MI"]
    assert _l["programs"][1]["cards"] == [("BMI", "Biomedicina", "/f/b.pdf"), ("3", "3. godina", "/f/i.pdf")]
    assert _l["programs"][2]["notes"] == ["Biće objavljen!"] and parse_lectures("<p>x</p>") is None
    _at = attachments(
        clean_html(
            '<dl class="attachbox"><dt>Attachments</dt><dd><dl class="file"><dt><span class="imageset"></span> '
            '<a class="postlink" href="./download/file.php?id=7">Rok &amp; B.PDF</a></dt><dd>(58.7 KiB) Downloaded 4 times'
            "</dd></dl></dd></dl>"
        )
    )
    assert (
        '<a class="att" href="https://nastava.mas.bg.ac.rs/nastava/download/file.php?id=7" rel="noopener noreferrer">'
        '<span class="att__t att__t--pdf">PDF</span><span class="att__n">Rok &amp; B.PDF<small>58.7 KiB · preuzeto 4 puta</small>'
        "</span></a>"
    ) in _at and "<dt>Prilozi</dt>" in _at, _at
    assert attachments(None) is None and attachments("<p>x</p>") == "<p>x</p>"
    _dl = clean_html(
        '<dl class="file"><dt><a class="postlink" href="./download/file.php?id=11&amp;sid=b0c">R&amp;T.zip</a></dt>'
        "<dd><em>овде</em></dd> <dd>(45.16 KiB) Downloaded 642 times</dd></dl>"
        '<dl class="file"><dt><a href="./download/file.php?id=12">b.pdf</a></dt><dd>(1 KiB) Downloaded 1 time</dd></dl>'
    )
    assert downloads(_dl) == [(11, "R&T.zip", 642), (12, "b.pdf", 1)] and downloads(None) == [], downloads(_dl)
    assert bars([(2014, 5), (2015, 10)], str) == [
        dict(label=2014, n=5, pct=50.0, href="2014"),
        dict(label=2015, n=10, pct=100.0, href="2015"),
    ]
    assert ranking(Counter(a=4, b=1, c=2), lambda k: (k.upper(), None, None), k=2) == [
        dict(label="A", href=None, note=None, n=4, pct=100.0),
        dict(label="C", href=None, note=None, n=2, pct=50.0),
    ]
    assert env.filters["n"](23692) == "23.692" and plural(642, "preuzimanje") == "preuzimanja"
    _at = attachments(
        '<dl>\n<dt><span></span> <a href="/f?id=1" rel="x">a.docx</a></dt>\n<dd><em>Ocene</em></dd> <dd>(1 KiB) preuzeto 2 puta</dd>\n</dl>'
    )
    assert _at == (
        '<a class="att" href="/f?id=1" rel="noopener noreferrer"><span class="att__t att__t--doc">DOCX</span><span class="att__n">'
        'a.docx<span class="att__c"><em>Ocene</em></span><small>1 KiB · preuzeto 2 puta</small></span></a>'
    ), _at
    _ct = clean_html(
        cent_tidy(
            '<div class="et_pb_row responsive-buttons"><div class="et_pb_column et_clickable"><a href="https://c/s1.pdf"><div class="x">'
            '<p>Смена 1</p></div></a></div><div class="et_pb_column et_clickable"><p>Смена 2</p></div></div>'
            '<div class="et_pb_row"><div id="at-col-arrow"><img src="https://c/a.webp"></div><div id="at-col-head"><p>ПЛ-1</p></div>'
            '<div id="at-col"><p>Лаб 1</p></div><div id="at-col-attach"><a href="https://c/u/lab1.pdf">lab1.pdf</a></div>'
            '<div id="at-col"></div><div id="at-col-nedelja">I недеља</div></div>'
            '<div class="et_pb_toggle et_pb_toggle_open"><h4 class="et_pb_toggle_title"><span class="accordion_mark">ПЛ-3</span>'
            '<p class="accordion_title">Лаб 3</p><a href="https://c/u/lab3.PDF">lab3.PDF</a><span class="accordion-nedelja"></span></h4>'
            '<div class="et_pb_toggle_content"><ul><li>Упутство <a href="https://drive.google.com/x">video</a></li></ul></div></div>'
            '<div class="et_pb_text et_pb_text_align_center"><p>c</p></div>'
        ),
        "https://c/",
        classes=CENT_CLASSES,
    )
    assert _ct == (
        '<div class="cent-btns"><a class="cent-btn" href="https://c/s1.pdf" rel="noopener noreferrer">Смена 1</a>'
        '<span class="cent-btn" title="bez linka na sajtu katedre">Смена 2</span></div>'
        '<div class="cent-head"><b class="cent-code">ПЛ-1</b><span class="cent-t">Лаб 1</span><a class="cent-file" '
        'href="https://c/u/lab1.pdf" rel="noopener noreferrer"><span class="att__t att__t--pdf">PDF</span>lab1.pdf</a>'
        '<span class="cent-wk">I недеља</span></div>'
        '<details class="cent-acc"><summary class="cent-head"><b class="cent-code">ПЛ-3</b><span class="cent-t">Лаб 3</span>'
        '<a class="cent-file" href="https://c/u/lab3.PDF" rel="noopener noreferrer"><span class="att__t att__t--pdf">PDF</span>'
        'lab3.PDF</a></summary><div><ul><li>Упутство <a class="cent-file" href="https://drive.google.com/x" '
        'rel="noopener noreferrer"><span class="att__t att__t--video">▶</span>video</a></li></ul></div></details>'
        '<div class="cent-c"><p>c</p></div>'
    ), _ct
    _s, _f = split_page(f"<html><title>T</title><meta>{HEAD_END}<x>{MAIN}a</main><p></main></html>")
    assert (_s, _f) == (
        f"<html><title></title><x>{MAIN}<!--main--></main></html>",
        f'<html lang="sr"><title>T</title><meta>{HEAD_END}a</main><p></html>',
    ), (_s, _f)
    assert desc(" a\n b ") == "a b" and desc("aaa bbb ccc", 9) == "aaa bbb…"
    assert lat("Љиљана ЉУБА Ђорђе, Џ. Mašina 2") == "Ljiljana LJUBA Đorđe, Dž. Mašina 2" and lat(None) == ""
    assert lat(Markup("Ш &amp; A")) == Markup("Š &amp; A")
    _bc = breadcrumbs(
        '<nav class="crumbs"><a href="/"><svg></svg>Početna</a><svg></svg><a href="/smer/x/" title="A &amp; B">A &amp; B</a>'
        '<svg></svg><span class="crumbs__here" aria-current="page">Мата</span></nav>',
        f"{SITE_URL}/p/",
    )
    assert [(i["position"], i["name"], i["item"]) for i in json.loads(re.search(r">(.*)</script>", _bc)[1])["itemListElement"]] == [
        (1, "Početna", f"{SITE_URL}/"),
        (2, "A & B", f"{SITE_URL}/smer/x/"),
        (3, "Мата", f"{SITE_URL}/p/"),
    ], _bc
    assert breadcrumbs("<p>no crumbs</p>", SITE_URL) == "" and type(_bc) is str
    assert drop_empty_tables("<table><tr><th>Predmet</th></tr><tr><td> &nbsp;</td></tr></table><p>x</p>") == "<p>x</p>"
    assert drop_empty_tables("<table><tr><td></td><td><b>2.11.</b></td></tr></table>").startswith("<table>")
    assert (
        drop_empty_tables(
            '<h2>A</h2><div><table><td>1</td></table></div><h2>B</h2>\n<div class="l"><table><th>x</th><td> </td></table></div>'
        )
        == '<h2>A</h2><div><table><td>1</td></table></div>\n<div class="l"></div>'
    )
    assert preuzeto("(1 KiB) Downloaded 1 time, Downloaded 22 times") == "(1 KiB) preuzeto 1 puta, preuzeto 22 puta"
    assert post_words(
        dict(
            title="Rezultati ispita",
            files=[(1, "OPK 3. predavanje.pdf", 9)],
            body="Видети http://x.rs/a, www.mas.bg.ac.rs, a@b.rs i Moodle_2015.pdf\nOPK 3. predavanje.pdf\n(4.29 MiB) preuzeto 1021 puta",
        )
    ) == ["rezultati", "ispita", "videti"]
    _bp = book_page(
        '<h1>X</h1><h2 id="циљ">Циљ</h2>\n<div class="level2"><p>\n\nA &amp; b.\n\n</p></div>'
        "<h2>Фонд часова</h2><div><p>Укупан фонд часова: 30<br></p></div>"
        "<h4>Провера знања</h4><div><p>Тест: 0<br>\nЗавршни испит: 4<br></p></div>"
        "<h2>Провера знања (укупно 100 поена)</h2><div><p>Пројекат: 40<br>Рачунски задаци: 0<br>"
        "Услов за излазак на испит (потребан број поена): 30<br></p></div>"
        "<h2>Литература</h2><div><p>\n\nA, 1992.; B, 2010.\n</p></div>"
    )
    assert book_page("<h2>Ресурси</h2><div><p>Лекција 1: А\n2. Б</p></div>")["text"]["Ресурси"] == (["А", "Б"], True)
    assert book_page("<h2>Ресурси</h2><div><p>- А\n2. Б</p></div>")["text"]["Ресурси"] == (["А", "2. Б"], False)
    assert (_bp["text"]["Циљ"][0], _bp["hours"], _bp["points"], _bp["pass_min"], _bp["books"]) == (
        ["A & b."],
        dict(total=30, groups=[("Провера знања", [("Завршни испит", 4)])]),
        [("Пројекат", 40)],
        30,
        ["A, 1992.", "B, 2010."],
    ), _bp
    assert same_words(
        Counter(ispit=2, ispita=5, ispitu=1, ispitni=1, studenti=3, studenata=2, smene=5, smena=1, smen=1, kandidata=1)
    ) == Counter(ispit=8, ispitni=1, studenti=5, smene=7, kandidata=1)
    import xml.etree.ElementTree as ET

    _it = dict(
        id="p5",
        num=5,
        title="A & <b>",
        posted="2026-11-08T14:39:57+00:00",
        who="Ђ",
        html="<p>x &amp; y</p>",
        body="",
        subj=dict(name="Мата 1"),
        smer=None,
        thread=dict(href="/tema/3/", posts=[1, 2]),
    )
    _x = ET.fromstring(atom("T", "/predmet/m/", [_it]))
    _ns = {"a": "http://www.w3.org/2005/Atom"}
    assert _x.find("a:entry/a:link", _ns).get("href") == f"{SITE_URL}/tema/3/#p5" and _x.find("a:entry/a:title", _ns).text == "A & <b>"
    assert (
        _x.find("a:entry/a:content", _ns).text == "<p>x &amp; y</p>"
        and ET.fromstring(atom("T", "/", [])).find("a:updated", _ns) is not None
    )
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
