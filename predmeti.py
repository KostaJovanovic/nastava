# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the subjects of www.mas.bg.ac.rs: the subject book, every subject page and where each is in the plans.

Usage: predmeti.py sync

One row per subject (the newest version of its page), one row per place in a plan: program, module (master MI only),
semester, the cell's position in the semester's column, and for an elective its slot ('5.4').
A subject that leaves the book stays, marked gone. The plans are read again on every sync.
"""

import re
import sys
import time
from datetime import datetime, timezone

SITE = "https://www.mas.bg.ac.rs/"
BOOK = "studije/predmeti/start"
# The plan pages: (program as the book names it, page, which plan table on the page). Master MI has one per module.
PLANS = [
    ("Основне академске студије — МИ", "studije/oas/start", 0),
    ("Основне академске студије — ИТМ", "studije/oas/start", 1),
    ("Мастер академске студије — Индустрија 4.0", "studije/mas/start", 0),
    ("Докторске студије — МИ", "studije/ds/start", 0),
]
MODULES = "studije/mas/start"
MODULE_PROGRAM = "Мастер академске студије — МИ"

SCHEMA = """
create table if not exists subjects (id text primary key, name text, program text, kind text, ects integer, exam text,
	katedra text, holder text, html text, first_seen text, last_seen text, gone integer default 0);
create table if not exists subject_places (program text, module text, semester integer, pos integer, slot text,
	slot_name text, subject text, name text);
"""


def soup(html):
    from bs4 import BeautifulSoup

    # The plan tables have stray </p> in their cells, which end the table early for html.parser.
    return BeautifulSoup(re.sub(r"</?p>", "", html), "html.parser")


def subject_id(href):
    m = re.search(r"/studije/predmeti/(\d+)$", href or "")
    return m and m.group(1)


def parse_book(html):
    """{subject id: (name, program)}: the book lists every subject once, under its program's heading."""
    main = soup(html).select_one("div.page")
    if main is None:
        raise RuntimeError("book: no div.page, the site changed")
    out, program = {}, None
    for el in main.find_all(["h2", "h3", "a"]):
        if el.name != "a":
            program = el.get_text(strip=True)
        elif (sid := subject_id(el.get("href"))) and program:
            out.setdefault(sid, (" ".join(el.get_text().split()), program))
    return out


def parse_plan(html, index=0):
    """The cells of a plan table: [(semester, position, cell)]. Columns after the first are the semesters; a cell
    spans the rows of its weekly hours, so the grid is laid out with rowspan and colspan as a browser does."""
    tables = soup(html).select("div.page table.kockice")
    if len(tables) <= index:
        raise RuntimeError(f"plan: no table {index}, the site changed")
    taken, cells = set(), []
    for r, tr in enumerate(tr for tr in tables[index].find_all("tr") if not tr.find_parent("thead")):
        c = 0
        for td in tr.find_all("td", recursive=False):
            while (r, c) in taken:
                c += 1
            rows, cols = int(td.get("rowspan") or 1), int(td.get("colspan") or 1)
            taken |= {(r + i, c + j) for i in range(rows) for j in range(cols)}
            if c >= 1:
                cells.append((c, r, td))
            c += cols
    # The position: the cell's place in its semester's column, top down.
    out, count = [], {}
    for sem, r, td in sorted(cells, key=lambda x: x[:2]):
        count[sem] = count.get(sem, 0) + 1
        out.append((sem, count[sem], td))
    return out


def parse_electives(html):
    """{'section54': [(subject id, name)]}: an elective list, one heading ('5.4') per slot, with each link's text.
    One page can be several choices: Завршни предмет 6.5 links 102 areas ('Завршни предмет - Трибологија') to 0361."""
    out, key = {}, None
    for el in soup(html).select_one("div.page").find_all(["h2", "h3", "h4", "a"]):
        if el.name != "a":
            m = re.fullmatch(r"(\d+)\.(\d+)", el.get_text(strip=True))
            key = m and f"section{m.group(1)}{m.group(2)}"
        elif key and (sid := subject_id(el.get("href"))):
            if (link := (sid, " ".join(el.get_text().split()))) not in out.setdefault(key, []):
                out[key].append(link)
    return out


def places(cells, electives):
    """The rows of subject_places for one plan (without program and module). electives(href) -> [(subject id, name)]."""
    rows = []
    for sem, pos, td in cells:
        name = " ".join(td.get_text().split())
        links = td.select("a[href]")
        # 'Завршни предмет (B.Sc. рад) 6.5.5' has no link in the cell; the page links its list elsewhere.
        if not links and (m := re.search(r"(\d)\.(\d+)(\.\d+)?$", name)):
            links = td.find_parent("div", class_="page").select(f'a[href$="#section{m.group(1)}{m.group(2)}"]')[:1]
        for a in links:
            if sid := subject_id(a["href"]):
                rows.append((sem, pos, None, None, sid, None))
            elif m := re.search(r"#section(\d)(\d+)$", a["href"]):
                rows += [(sem, pos, f"{m.group(1)}.{m.group(2)}", name, s, n) for s, n in electives(a["href"])]
    return rows


def parse_modules(html):
    """[(module name, page)] of master MI, from its page."""
    return [(" ".join(a.get_text().split()), a["href"].lstrip("/")) for a in soup(html).select('div.page a[href^="/studije/mas/modul-"]')]


def parse_subject(html):
    from bs4 import BeautifulSoup
    from nastavnici import field

    # Not soup(): a subject page's paragraphs are its text and are kept.
    main = BeautifulSoup(html, "html.parser").select_one("div.page")
    if main is None:
        raise RuntimeError("subject: no div.page, the site changed")
    head = main.select_one("div.wrap_box")
    text = head.get_text("\n") if head else ""
    ects = field(text, "ЕСПБ")
    holder = head and head.find("strong", string=re.compile("Носилац"))
    holder = holder and holder.find_next("a", href=re.compile(r"^/fakultet/nastavnici/"))
    kat = head and head.select_one('a[href^="/organizacija/katedre/"]')
    return dict(
        name=" ".join(main.h1.get_text().split()),
        kind=field(text, "Врста предмета"),
        ects=int(ects) if ects and ects.isdigit() else None,
        exam=field(text, "Облик завршног испита"),
        katedra=kat and " ".join(kat.get_text().split()),
        holder=holder and holder["href"].rsplit("/", 1)[-1],
        html=str(main),
    )


def save(db, row, now):
    row = dict(row, first_seen=now, last_seen=now, gone=0)
    cols = list(row)
    db.execute(
        f"insert into subjects ({', '.join(cols)}) values ({', '.join('?' * len(cols))}) on conflict(id) do update set "
        + ", ".join(f"{c} = excluded.{c}" for c in cols if c != "first_seen"),
        list(row.values()),
    )


def sync(db):
    from nastava import DELAY, session

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cache = {}

    def page(path):
        """The page's HTML, or None for a 404. A plan page is read once per sync."""
        path = path.lstrip("/").split("#")[0]
        if path not in cache:
            time.sleep(DELAY)
            r = session().get(SITE + path, timeout=60)
            if r.status_code != 404:
                r.raise_for_status()
            cache[path] = None if r.status_code == 404 else r.text
        return cache[path]

    book = parse_book(page(BOOK) or "")
    if len(book) < 300:
        raise RuntimeError(f"only {len(book)} subjects in the book, the site changed")
    plans = [(program, None, path, i) for program, path, i in PLANS]
    plans += [(MODULE_PROGRAM, name, path, 0) for name, path in parse_modules(page(MODULES))]
    rows = []
    for program, module, path, i in plans:
        # An elective's link: '#section54' on the same page (a module) or 'oas-izborni#section54' on another.
        electives = lambda href: parse_electives(page(href.split("#")[0] or path)).get(href.split("#")[1], [])
        rows += [(program, module, *r) for r in places(parse_plan(page(path), i), electives)]
    # Made again on every sync, so a new column needs no migration.
    db.execute("drop table subject_places")
    db.executescript(SCHEMA)
    db.executemany("insert into subject_places values (?,?,?,?,?,?,?,?)", rows)
    # Now: the drop above is saved at once (outside a transaction), so a failed page below must not leave the table empty.
    db.commit()
    for i, (sid, (name, program)) in enumerate(book.items(), 1):
        html = page(f"studije/predmeti/{sid}")
        row = dict(id=sid, name=name, program=program)
        save(db, dict(row, **parse_subject(html)) if html else row, now)
        if i % 50 == 0:
            db.commit()
            print(f"{i}/{len(book)}", flush=True)
    gone = db.execute("update subjects set gone = 1 where last_seen != ?", (now,)).rowcount
    db.commit()
    print(f"{len(book)} subjects, {len(rows)} places in {len(plans)} plans, {gone} gone", flush=True)


def main():
    from nastava import connect

    sys.stdout.reconfigure(encoding="utf-8")
    if (sys.argv[1] if len(sys.argv) > 1 else "sync") != "sync":
        sys.exit(__doc__)
    db = connect()
    db.executescript(SCHEMA)
    sync(db)


if __name__ == "__main__":
    assert subject_id("/studije/predmeti/0642") == "0642" and subject_id("/studije/oas/start") is None
    main()
