# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "tzdata"]
# ///
"""A Moodle course, as posts of its subject (build.py's load_mail, as mail.py's mails and teams.py's posts): each
note of the teacher's (a label, an activity's description, an assignment's text) a post with that activity's files;
the other files the subject's material (mail/moodle-<host>-<course>/material.json). Moodle shows no dates: a post is
dated by its section's week ("23. juni - 29. juni"; "4. nedelja": from week 1's Monday, given), at noon, in the
course's order.

The zip comes from the course page in the browser (tools/moodle/moodle-export.js).

Usage: moodle.py add <moodle-*.zip> <subject page, /predmet/…/> <teacher's board username> [week 1's Monday, YYYY-MM-DD]
       moodle.py help   the asserts
  add   a post already here is skipped; the course's material is written again. Not the forums (a student's post).
"""

import hashlib
import json
import re
import sys
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from common import ROOT

MAIL = ROOT / "mail"
TZ = ZoneInfo("Europe/Belgrade")
MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [("januar", "јануар"), ("februar", "фебруар"), ("mart", "март"), ("april", "април"), ("maj", "мај"),
         ("jun", "јун"), ("jul", "јул"), ("avgust", "август"), ("septembar", "септембар"), ("oktobar", "октобар"),
         ("novembar", "новембар"), ("decembar", "децембар")]
    )
    for m in names
}
DAY = re.compile(r"(\d{1,2})\.\s*([a-zčćšžđа-яђјљњћџ]+)", re.I)


def section_day(title, year, week1=None):
    """A section's first day from its title ("23. juni - 29. juni", "26.septembar.2025."); its own year, else year.
    A week's ("4. nedelja") is week1's Monday plus its weeks.
    shortcut: a course over New Year takes one year for the sections without theirs; fine while none is."""
    if week1 and (w := re.match(r"\s*(\d{1,2})\.\s*(nedelj|недељ)", title, re.I)):
        return week1 + timedelta(weeks=int(w[1]) - 1)
    m = DAY.search(title)
    month = m and next((n for k, n in MONTHS.items() if m[2].lower().startswith(k)), None)
    if not month:
        return None
    y = re.search(r"\b(20\d\d)\b", title)
    return date(int(y[1]) if y else year, month, int(m[1]))


def clean(s):
    """A name as moodle-export.js makes a folder's."""
    s = re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", s or "")).strip()[:100]
    return s or "_"


def text(html):
    return " ".join(BeautifulSoup(html or "", "html.parser").get_text(" ").split())


def title_of(name, html):
    """A label's first sentence (up to 80 characters); an activity's own name."""
    if name and name != "label":
        return name
    first = re.split(r"(?<=[.!?])\s", text(html), maxsplit=1)[0]
    return first if len(first) <= 80 else first[:80].rsplit(" ", 1)[0] + "…"


def add(zpath, page, author, week1=None):
    z = zipfile.ZipFile(zpath)
    ix = json.loads(z.read("index.json"))
    host = re.match(r"https?://([^/.]+)", ix["url"])[1]
    course = re.search(r"[?&]id=(\d+)", ix["url"])[1]
    week1 = date.fromisoformat(week1) if week1 else None
    years = [int(y) for s in ix["sections"] for y in re.findall(r"\b(20\d\d)\b", s["title"])]
    year = min(years) if years else week1.year if week1 else int(ix["exported"][:4])
    days = [section_day(s["title"], year, week1) for s in ix["sections"]]
    if not any(days):
        sys.exit("No section has a date (\"23. juni - 29. juni\"); give week 1's Monday (YYYY-MM-DD) for \"N. nedelja\".")
    first = min(filter(None, days), default=date(year, 9, 1))
    school = f"{first.year - 1}/{first.year}" if first.month < 9 else f"{first.year}/{first.year + 1}"
    # The activities' descriptions from the course page: a zip from before index.json had them.
    page_soup = BeautifulSoup(z.read("course.html").decode("utf-8"), "html.parser") if "course.html" in z.namelist() else None
    described = {}
    for d in page_soup.select(".contentafterlink, .activity-description, .description-inner") if page_soup else []:
        act = d.find_parent("li", class_="activity")
        link = act and act.select_one('a[href*="/mod/"]')
        if link:
            described[link["href"]] = d.decode_contents().strip()
    MAIL.mkdir(exist_ok=True)
    material, added, order = [], 0, 0
    for si, (s, day) in enumerate(zip(ix["sections"], days)):
        day = day or first
        for ai, a in enumerate(s["activities"]):
            order += 1
            files = [f for f in a.get("files", []) if f in z.namelist()]
            if a["type"] == "forum":
                if a.get("discussions"):
                    print(f"  not published (a forum, students' posts too): {a['name']}")
                continue
            # The note: a label's text, an activity's description, else an assignment's or page's own text.
            html = a.get("html") if a["type"] == "label" else a.get("description") or described.get(a.get("url"), "")
            if not text(html) and a["type"] not in ("resource", "folder", "url"):
                # Its folder in the zip: "<NN> <section>/<activity>/page.html", named as moodle-export.js's clean().
                want = f"{clean(s['title'])}/{clean(a['name'])}/page.html"
                page_html = next((n for n in z.namelist() if n.split(" ", 1)[-1] == want), None)
                if page_html:
                    soup = BeautifulSoup(z.read(page_html).decode("utf-8"), "html.parser")
                    for h in soup.find_all(["h2", "h3"], limit=1):
                        h.decompose()  # the activity's name, the post's title
                    html = str(soup).replace("<!doctype html><meta charset=utf-8>", "").strip()
            if a["type"] == "url" and a.get("target"):
                html = (html or "") + f'<p><a href="{a["target"]}">{a["target"]}</a></p>'
            # A link to the course's own file needs Moodle's login: its text stays, the file is the post's.
            soup = BeautifulSoup(html or "", "html.parser")
            for x in soup.select('a[href*="pluginfile.php"]'):
                x.unwrap()
            for x in soup.select('img[src*="pluginfile.php"]'):
                x.decompose()
            html = str(soup)
            if not re.search(r"[^\W\d_]", text(html)):  # none, or a label that is only a line of dashes
                material += files
                continue
            cm = re.search(r"[?&]id=(\d+)", a.get("url") or "")
            mid = f"moodle:{host}:{course}:{cm[1] if cm else f's{si}a{ai}'}"
            key = hashlib.sha1(mid.encode()).hexdigest()[:8]
            if any(MAIL.glob(f"*-{key}")):
                continue
            sent = datetime.combine(day, time(12), TZ) + timedelta(minutes=order)
            out = MAIL / f"{day:%Y-%m-%d}-{key}"
            out.mkdir(parents=True, exist_ok=True)
            names = []
            for f in files:
                name = Path(f).name
                (out / name).write_bytes(z.read(f))
                names.append(name)
            post = dict(
                id=mid,
                refs=[],
                page=page,
                author=author,
                posted=sent.astimezone(ZoneInfo("UTC")).isoformat(),
                when=f"{day:%d.%m.%Y.}",
                title=title_of(a["name"], html),
                html=html,
                files=names,
                sizes={n: (out / n).stat().st_size for n in names},
            )
            (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
            added += 1
    # The rest: each file under its section's name, as the course has it ("21. juli - 27. juli/primer opp2.zip").
    out, rest = MAIL / f"moodle-{host}-{course}", []
    for f in material:
        p = re.sub(r"^\d+ ", "", f.split("/", 1)[0]) + "/" + Path(f).name
        if p in rest:
            p = re.sub(r"^\d+ ", "", f)
        (out / p).parent.mkdir(parents=True, exist_ok=True)
        (out / p).write_bytes(z.read(f))
        rest.append(p)
    if rest:
        (out / "material.json").write_text(
            json.dumps(dict(page=page, name=f"{ix['course']} {school}", source="moodle", files=rest), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    print(f"{ix['course']} ({school}): {added} posts, {len(rest)} files of material")


def selftest():
    assert section_day("23. juni - 29. juni", 2025) == date(2025, 6, 23)
    assert section_day("26.septembar.2025.", 2024) == date(2025, 9, 26)
    assert section_day("5.oktobar 20205.", 2025) == date(2025, 10, 5)
    assert section_day("Opšta sekcija", 2025) is None
    assert section_day("4. nedelja", 2026, date(2026, 3, 9)) == date(2026, 3, 30) == section_day("4. nedelj", 2026, date(2026, 3, 9))
    assert section_day("4. nedelja", 2026) is None
    assert section_day("1. март - 7. март", 2026) == date(2026, 3, 1)
    assert title_of("label", "<p>Kolokvijum u sredu u 14h u 453, prvi deo gradiva</p>") == "Kolokvijum u sredu u 14h u 453, prvi deo gradiva"
    assert title_of("Primer 2", "<p>x</p>") == "Primer 2"
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["help"]:
        selftest()
    elif len(sys.argv) in (5, 6) and sys.argv[1] == "add":
        add(*sys.argv[2:])
    else:
        sys.exit(__doc__)
