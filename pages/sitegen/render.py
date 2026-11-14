"""The pages: subjects, smerovi, topics, posts, teachers, katedre, the book, news, the home page, verzije."""

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import groupby
from xml.etree import ElementTree
from markupsafe import Markup, escape
from studije import SITE as STUDY_SITE
from translit import fold
from .clean import book_page, clean_html
from .feeds import atom
from .known import HOME_ORDER, OWN_SITES, QUIET, VZ_ITEM, VZ_TAGS
from .load_board import row_katedra
from .load_book import plan_groups
from .load_teachers import bibliography, department_intro
from .output import FEED_ALL, HERE, MINE, RECENT, VESTI_HOME, env, katedra_href, katedra_pages, mark_for_pagefind, versioned, write
from .text import PROGRAMS, azbuka, katedra, slot_label, slug


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
