"""The schedule pages (kalendar, raspored predavanja, raspored ispita) and their files."""

import re
from collections import defaultdict
from html import unescape
from urllib.parse import quote
from studije import PAGES as STUDY_PAGES, SITE as STUDY_SITE, media_path
from translit import fold
from .clean import clean_html, drop_empty_tables
from .output import env, write, write_bytes
from .text import LINK, slug, strip_tags
from .wiki import archived_wiki, link_groups, link_icons, render_wiki_pages


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
