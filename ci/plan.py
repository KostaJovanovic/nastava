# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf"]
# ///
"""What a scheduled run (sync.yml) does, from the faculty's teaching calendar; and the database's fingerprint.

Usage: plan.py morning|noon|afternoon|evening|late | check | fingerprint
  morning … late  the run's slot: print the parts for ci/deploy.sh ("forum", "forum studije", ...)
  check           exit 1 when the calendar of this school year is missing or unreadable (after 15 October)
  fingerprint     a hash of what the scrapers store: equal before and after a scrape means nothing changed
Today is the UTC date (the runs are at 6:17 to 21:17 UTC, the same day in Belgrade); TODAY=2027-01-11 overrides it for
a test.
"""
import datetime as dt
import hashlib
import io
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.getenv("DB", ROOT / "nastava.db"))
AFTER = 7          # days after an exam period that stay hot: results and oral exams come then
YEARLY = (10, 1)   # teachers and subjects: the school year's first day
# "18.1.-31.1.", "3.2. и 4.2.", "(2.11.-4.11.)"
RANGE = re.compile(r"(\d{1,2})\.(\d{1,2})\.\s*(?:-|–|и|i)\s*(\d{1,2})\.(\d{1,2})\.")


def windows(text, y1):
    """[(kind, first day, last day)] of the school year y1/y1+1, by first day: kind "prijave" (registration) or "rok"
    (an exam period). October to December are in y1, the rest in y1+1. The smaller block (мањи блок) is left out:
    its registration and exam week are no busier than a normal day (2024: 5.6 posts a day, around it 4.6–6.6)."""
    day = lambda d, m: dt.date(y1 if m >= 10 else y1 + 1, m, d)
    out = []
    for line in text.splitlines():
        u, r = line.upper(), RANGE.search(line)
        if not r or "МАЊЕГ" in u or "MANJEG" in u:
            continue
        a, b = day(int(r[1]), int(r[2])), day(int(r[3]), int(r[4]))
        if "ПРИЈАВЕ" in u or "PRIJAVE" in u:
            out.append(("prijave", a, b))
        elif "ИСПИТНИ РОК" in u or "ISPITNI ROK" in u:
            out.append(("rok", a, b))
    return sorted(out, key=lambda w: w[1])


def school_year(d):
    return d.year if d.month >= 10 else d.year - 1


def calendars(db):
    """{school year: windows} of every calendar PDF the state has (studije.py archives them), newest version each."""
    from pypdf import PdfReader
    out = {}
    rows = db.execute("select path, data from study_files where path like 'studije/kalendar%.pdf' order by first_seen")
    for path, data in rows:
        # One bad PDF (cut short, a typo date such as 30.2.) must not stop every run: studije, which would fetch a
        # fixed one, runs only when this plans it. check still reports a year left without a calendar.
        try:
            text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
            m = re.search(r"_(\d\d)_\d\d\.pdf$", path) or re.search(r"школска\s+20(\d\d)/", text)
            if m:
                out[2000 + int(m[1])] = windows(text, 2000 + int(m[1]))
        except Exception as e:
            print(f"calendar {path} skipped: {type(e).__name__}: {e}", file=sys.stderr)
    return out


def for_year(cals, y):
    """This school year's windows; without its calendar, the nearest one's moved by whole years."""
    if y in cals or not cals:
        return cals.get(y, [])
    near = min(cals, key=lambda c: abs(c - y))
    # 29 February into a year without one: the 28th.
    move = lambda d: d.replace(year=d.year + y - near, day=28 if (d.month, d.day) == (2, 29) else d.day)
    return [(k, move(a), move(b)) for k, a, b in cals[near]]


def hot(d, wins):
    return any(a <= d <= b + dt.timedelta(days=AFTER if k == "rok" else 0) for k, a, b in wins)


def parts(slot, d, wins):
    """The scrapers for a run: "forum" (the board and the news) and those due today. All five runs scrape, every day;
    the morning run also takes the schedule pages (studije) on the 1st of the month and on the first day of a
    registration or an exam period, and on 1 October the teachers and the subjects. (The departments' sites run every
    time, in deploy.sh.)"""
    first = slot == "morning"
    p = ["forum"]
    if first and (d.day == 1 or any(d == a for _, a, _ in wins)):
        p.append("studije")
    if first and (d.month, d.day) == YEARLY:
        p += ["nastavnici", "predmeti"]
    return " ".join(p)


def fingerprint(db):
    """What the scrapers change, without the last_seen times that every run updates. shortcut: an edit that keeps a
    post's length is not seen; a hash of every post's html would be (slower)."""
    queries = [
        "select count(*), max(id), sum(gone), total(length(html)), total(length(title)) from posts",
        "select count(*), sum(gone), total(length(title)) from topics",
        "select count(*), sum(gone) from vesti",
        "select count(*) from study_pages", "select count(*) from study_files",
        "select count(*), sum(gone), total(length(html)) from wiki_pages",
        "select count(*), sum(gone), total(length(html)) from teachers", "select count(*) from teacher_subjects",
        "select count(*), sum(gone), total(length(html)) from subjects", "select count(*) from subject_places",
        "select count(*), sum(gone), total(length(html)) from cent_notices", "select count(*), sum(gone) from cent_pages",
        "select count(*), sum(gone) from katedre_pages",
        "select count(*), total(length(html)) from departments",
    ]
    out = []
    for q in queries:
        try:
            out.append(db.execute(q).fetchone())
        except sqlite3.OperationalError:  # a table a scraper has not made yet
            out.append(None)
    return hashlib.sha256(repr(out).encode()).hexdigest()[:16]


if __name__ == "__main__":
    _t = """ПРИЈАВЕ испита мањег блока (2.11.-4.11.)
ИСПИТИ мањег блока (VI недеља)
ПРИЈАВЕ испита за јануарски рок (11.1.-13.1.)
ЈАНУАРСКИ ИСПИТНИ РОК 18.1.-31.1.
ПРИЈАВЕ испита за фебруарски рок (3.2. и 4.2.)
ФЕБРУАРСКИ ИСПИТНИ РОК 8.2.-21.2.
(испитни дани 14.2. и 21.2.- надокнада за 15.2. и 16.2.)
ПРИЈАВЕ испита мањег блока (22.3.-24.3.)
ПРИЈАВЕ испита за јунски рок (31.5.-2.6.)
ЈУНСКИ ИСПИТНИ РОК 7.6.-20.6.
ПРИЈАВЕ испита за јулски рок (23.6.-24.6.)
ЈУЛСКИ ИСПИТНИ РОК 28.6.-11.7.
ПРИЈАВЕ испита за септембарски рок (16.8.-18.8.)
СЕПТЕМБАРСКИ ИСПИТНИ РОК 23.8.-5.9.
ПРИЈАВЕ испита за октобарски рок (8.9.-9.9.)
ОКТОБАРСКИ ИСПИТНИ РОК 13.9.-26.9."""
    D = dt.date
    _w = windows(_t, 2026)
    assert _w == [
        ("prijave", D(2027, 1, 11), D(2027, 1, 13)), ("rok", D(2027, 1, 18), D(2027, 1, 31)),
        ("prijave", D(2027, 2, 3), D(2027, 2, 4)), ("rok", D(2027, 2, 8), D(2027, 2, 21)),
        ("prijave", D(2027, 5, 31), D(2027, 6, 2)), ("rok", D(2027, 6, 7), D(2027, 6, 20)),
        ("prijave", D(2027, 6, 23), D(2027, 6, 24)), ("rok", D(2027, 6, 28), D(2027, 7, 11)),
        ("prijave", D(2027, 8, 16), D(2027, 8, 18)), ("rok", D(2027, 8, 23), D(2027, 9, 5)),
        ("prijave", D(2027, 9, 8), D(2027, 9, 9)), ("rok", D(2027, 9, 13), D(2027, 9, 26))], _w
    _p = lambda slot, *ymd: parts(slot, D(*ymd), _w)
    assert _p("morning", 2027, 1, 18) == "forum studije" and _p("afternoon", 2027, 1, 18) == "forum"  # an exam period starts
    assert _p("morning", 2027, 3, 1) == "forum studije" and _p("noon", 2027, 3, 1) == "forum"  # the 1st: morning only
    assert _p("morning", 2026, 11, 10) == "forum" and _p("late", 2027, 3, 30) == "forum"    # every run scrapes
    assert _p("evening", 2026, 12, 5) == "forum" and _p("late", 2027, 3, 1) == "forum"
    assert _p("morning", 2027, 1, 11) == "forum studije" and _p("noon", 2027, 1, 11) == "forum"  # registration opens
    assert _p("noon", 2027, 2, 2) == "forum" and _p("morning", 2027, 2, 1) == "forum studije"  # after January's; the 1st
    assert _p("morning", 2027, 10, 1) == "forum studije nastavnici predmeti"  # the 1st, 1 October
    assert _p("noon", 2026, 10, 1) == "forum"
    assert hot(D(2026, 10, 3), [("rok", D(2026, 9, 13), D(2026, 9, 26))]) and not hot(D(2026, 10, 4), [("rok", D(2026, 9, 13), D(2026, 9, 26))])
    _c = {2026: _w}
    assert for_year(_c, 2027)[0] == ("prijave", D(2028, 1, 11), D(2028, 1, 13)) and for_year(_c, 2026) == _w and for_year({}, 2026) == []
    assert for_year({2027: [("rok", D(2028, 2, 15), D(2028, 2, 29))]}, 2028) == [("rok", D(2029, 2, 15), D(2029, 2, 28))]
    today = D.fromisoformat(os.environ["TODAY"]) if os.getenv("TODAY") else dt.datetime.now(dt.timezone.utc).date()
    match sys.argv[1:]:
        case ["fingerprint"]:
            print(fingerprint(sqlite3.connect(f"file:{DB}?mode=ro", uri=True)))
        case ["check"]:
            cals = calendars(sqlite3.connect(f"file:{DB}?mode=ro", uri=True))
            y = school_year(today)
            n = len(cals.get(y, []))
            print(f"calendar {y}/{y + 1}: {n} windows; have {sorted(cals)}")
            # The faculty may publish it late: no alarm before 15 October.
            if n < 12 and today >= D(y, 10, 15):
                sys.exit(f"no readable calendar for {y}/{y + 1} on www.mas.bg.ac.rs (kalendar nastave): the extra runs use the nearest year's dates")
        case [("morning" | "noon" | "afternoon" | "evening" | "late") as slot]:
            cals = calendars(sqlite3.connect(f"file:{DB}?mode=ro", uri=True))
            print(parts(slot, today, for_year(cals, school_year(today))))
        case _:
            sys.exit(__doc__)
