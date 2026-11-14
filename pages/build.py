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
from itertools import groupby
from pathlib import Path
from xml.etree import ElementTree

from markupsafe import Markup, escape

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scrapers"))
from studije import SITE as STUDY_SITE  # noqa: E402
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
from sitegen.feeds import atom, write_feeds  # noqa: E402
from sitegen.known import HOME_ORDER, OWN_SITES, QUIET, VZ_ITEM, VZ_TAGS  # noqa: E402
from sitegen.links import mark_elsewhere, service  # noqa: E402
from sitegen.load_board import load_items, load_places, load_topics, row_katedra, side_panel, subject_name  # noqa: E402
from sitegen.load_book import load_book, plan_groups  # noqa: E402
from sitegen.load_sources import load_cent, load_katedre, load_mail, load_vesti  # noqa: E402
from sitegen.load_teachers import bibliography, department_intro, load_teachers, write_photos  # noqa: E402
from sitegen.output import (
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
    write_page,
    write_sitemap,
)  # noqa: E402
from sitegen.schedule import first_link, parse_lectures, render_study_pages  # noqa: E402
from sitegen.stats import archive_stats, bars, post_words, ranking, same_words  # noqa: E402
from sitegen.stil import css_colors, stil_data  # noqa: E402
from sitegen.text import (
    BASE,
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
)  # noqa: E402
from sitegen.wiki import archived_wiki, link_groups, link_icons, wiki_link, wiki_title  # noqa: E402
from sitegen import output  # noqa: E402
from mail import asset_name  # noqa: E402


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
