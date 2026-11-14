# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the teacher pages of www.mas.bg.ac.rs: the list, every profile and the emeritus page.

Usage: nastavnici.py sync
       nastavnici.py photos    (the photos not stored yet; sync and nastavnici_istorija.py end with it)
       nastavnici.py departments   (only the department pages, for their pages here; sync reads them too)

One row per teacher (the newest version of the profile) and one row per subject the teacher has.
A teacher who leaves the list stays, marked gone unless a department page still lists them. The forum username is the part of the e-mail before @.
The teachers who left before the archive began: nastavnici_istorija.py (once, by hand).
"""

import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

from common import DELAY, connect, session
from translit import CYRILLIC, LATIN

SITE = "https://www.mas.bg.ac.rs/"
LIST = "fakultet/nastavnici/start"
EMERITUS = "fakultet/nastavnici/emeritus/start"

SCHEMA = """
create table if not exists teachers (id text primary key, name text, full_name text, title text, katedra text, katedra_id integer,
	office text, email text, username text, phone text, hours text, research text, emeritus integer, html text,
	first_seen text, last_seen text, gone integer default 0, photo text);
create table if not exists teacher_subjects (teacher text, code text, name text, primary key (teacher, code, name));
create table if not exists photos (url text primary key, data blob, type text, fetched text);
create table if not exists departments (id integer primary key, name text, html text, first_seen text, last_seen text);
"""


def photo_urls(html, stored):
    """(list size, page size) URLs of a teacher's photo: a departed one's stored copy (history), else the profile's,
    the faculty's 130 px copy and its original (about 600x700). build.py shows the local copy of each (photos)."""
    if stored:
        return stored, stored
    m = re.search(r'<img[^>]+src="([^"]*_media/fakultet/nastavnici/[^"]+)"', html or "")
    if not m:
        return None, None
    thumb = urljoin(SITE, unescape(m[1]))
    return thumb, thumb.split("?")[0]


def store_photos(db):
    """A local copy of each teacher photo, fetched once per URL (the faculty's changes with the file): the faculty
    removes a departed teacher's photo, and masinac.org or the Wayback Machine can lose theirs. A failed one is
    tried again on the next run."""

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    have = {r[0] for r in db.execute("select url from photos")}
    want = sorted({u for html, p in db.execute("select html, photo from teachers") for u in photo_urls(html, p) if u} - have)
    failed = 0
    for n, url in enumerate(want, 1):
        time.sleep(DELAY)
        try:
            # masinac.org sends a missing photo to its home page: a redirect is a miss, but on the Wayback Machine.
            r = session().get(url, timeout=90, allow_redirects=url.startswith(WAYBACK))
        except Exception as e:
            r = None
            print(f"photo {url}: {e}", flush=True)
        if r is not None and r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            db.execute("insert into photos values (?,?,?,?)", (url, r.content, r.headers["content-type"].split(";")[0], now))
        else:
            failed += 1
            print(f"photo {r is not None and r.status_code} {url}", flush=True)
        if n % 25 == 0:
            db.commit()
    db.commit()
    print(f"photos: {len(want) - failed} stored, {failed} failed", flush=True)


def split_title(text):
    """'др Душан Љ. Ђукић, ванредни професор' -> ('др Душан Љ. Ђукић', 'ванредни професор')."""
    full, _, title = " ".join(text.split()).partition(", ")
    return full.strip(), title


def plain_name(full):
    """'мастер маш. инж. Јована Р. Антић' -> 'Јована Р. Антић': the degree is in lower case, the name is not."""
    words = full.split()
    return " ".join(words[next((i for i, w in enumerate(words) if w[0].isupper()), 0) :])


def field(text, label):
    # The value is on the line of the colon; an empty one must not take the next line's label.
    m = re.search(rf"{label}\s*:[ \t]*(.*)", text)
    return (m and m.group(1).strip()) or None


def sections(main):
    """{h3 heading: text under it} of a profile."""
    out = {}
    for h in main.select("h3"):
        parts = []
        for sib in h.find_next_siblings():
            if sib.name in ("h2", "h3"):
                break
            parts.append(sib.get_text("\n"))
        out[h.get_text(strip=True)] = "\n".join(" ".join(l.split()) for l in "\n".join(parts).split("\n") if l.strip())
    return out


def parse_list(html):
    """The rows of the teacher list: id, full name, title, katedra, phone, email."""
    from bs4 import BeautifulSoup

    rows = []
    for p in BeautifulSoup(html, "html.parser").select("div.page p"):
        # Not .media: the 2014 list links the photo first, a link without the name.
        a = p.select_one('a[href^="/fakultet/nastavnici/"]:not(.media)')
        m = a and re.fullmatch(r"/fakultet/nastavnici/(\d+)", a["href"])
        if not m:
            continue
        lines = [l.strip() for l in p.get_text("\n").split("\n") if l.strip()]
        mail = p.select_one('a[href^="mailto:"]')
        full, title = split_title(a.get_text())
        rows.append(
            dict(
                id=m.group(1),
                full_name=full,
                title=title,
                katedra=next((l[0].upper() + l[1:] for l in lines if l.lower().startswith("катедра")), None),
                phone=field(p.get_text("\n"), "Телефон"),
                email=mail and mail.get_text(strip=True),
            )
        )
    return rows


def parse_profile(html):
    from bs4 import BeautifulSoup

    main = BeautifulSoup(html, "html.parser").select_one("div.page")
    if main is None:
        raise RuntimeError("profile: no div.page, the site changed")
    head = main.select_one("div.wrap_box p")
    text = head.get_text("\n") if head else ""
    kat = head and head.select_one('a[href^="/organizacija/katedre/"]')
    sec = sections(main)
    # [(code, name)]: one page can be several subjects, Завршни предмет's areas ('Завршни предмет - Трибологија', 0361).
    subjects = []
    for a in main.select('a[href^="/studije/predmeti/"]'):
        if (s := (a["href"].rsplit("/", 1)[-1], " ".join(a.get_text().split()))) not in subjects:
            subjects.append(s)
    return dict(
        name=main.select_one("h2").get_text(strip=True),
        katedra=kat and " ".join(kat.get_text().split()),
        katedra_id=kat and int(kat["href"].rsplit("/", 1)[-1]),
        office=field(text, "Кабинет"),
        hours=sec.get("Термини за пријем студената"),
        research=sec.get("Истраживачка област"),
        html=str(main),
    ), subjects


def parse_emeritus(html):
    from bs4 import BeautifulSoup

    rows = []
    for box in BeautifulSoup(html, "html.parser").select("div.page div.wrap_box"):
        mail = box.select_one('a[href^="mailto:"]')
        if not mail:
            continue
        email = mail.get_text(strip=True)
        line = next(l for l in box.get_text("\n").split("\n") if "," in l)
        full, title = split_title(line)
        rows.append(
            dict(
                id=f"emeritus-{email.split('@')[0]}",
                full_name=full,
                title=title,
                email=email,
                name=plain_name(full),
                emeritus=1,
                html=f'<div class="page">{box}</div>',
            )
        )
    return rows


def parse_katedra(html):
    """A department page's staff list, {name_key: title}: the untitled are its emeriti ('Мирољуб М. Аџић') and staff
    off the teachers' list ('Младен М. Регодић')."""
    from bs4 import BeautifulSoup

    h = BeautifulSoup(html, "html.parser").select_one('div.page h2[id^="наставници"]')
    if h is None:
        raise RuntimeError("katedra: no staff list, the site changed")
    lines = [split_title(l) for l in h.find_next("p").get_text("\n").split("\n") if l.strip()]
    return {name_key(plain_name(full)): title for full, title in lines}


def save(db, row, now):
    row = dict(row, username=row.get("email") and row["email"].split("@")[0].lower(), first_seen=now, last_seen=now, gone=0)
    cols = list(row)
    db.execute(
        f"insert into teachers ({', '.join(cols)}) values ({', '.join('?' * len(cols))}) on conflict(id) do update set "
        + ", ".join(f"{c} = excluded.{c}" for c in cols if c != "first_seen"),
        list(row.values()),
    )


def page(path):
    """The page's HTML, or None for a 404."""

    time.sleep(DELAY)
    r = session().get(SITE + path, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


def save_department(db, k, name, html, now):
    """A department page (organizacija/katedre/<k>) as the wiki shows it, for its page here (build.py): its text and
    its own site's link."""
    m = re.search(r"<!-- wikipage start -->(.*?)<!-- wikipage stop -->", html, re.S)
    db.execute(
        "insert into departments values (?,?,?,?,?) on conflict(id) do update set name = excluded.name, "
        "html = excluded.html, last_seen = excluded.last_seen",
        (k, name, (m[1] if m else html).strip(), now, now),
    )


def departments(db):
    """Only the department pages (sync reads them too)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for k, name in db.execute("select distinct katedra_id, katedra from teachers where katedra_id is not null and not gone").fetchall():
        html = page(f"organizacija/katedre/{k}")
        if html:
            save_department(db, k, name, html, now)
    db.commit()
    print(db.execute("select count(*) from departments").fetchone()[0], "departments", flush=True)


def sync(db):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    listed = parse_list(page(LIST) or "")
    if len(listed) < 50:
        raise RuntimeError(f"only {len(listed)} teachers in the list, the site changed")
    for i, row in enumerate(listed, 1):
        html = page(f"fakultet/nastavnici/{row['id']}")
        if html is None:
            # Listed before its profile exists: keep the list's data, try the profile again tomorrow.
            print(f"no profile for {row['id']} {row['full_name']}", flush=True)
            save(db, dict(row, name=plain_name(row["full_name"]), emeritus=0), now)
            continue
        profile, subjects = parse_profile(html)
        save(db, dict(row, **{k: v for k, v in profile.items() if v or k not in row}, emeritus=0), now)
        db.execute("delete from teacher_subjects where teacher = ?", (row["id"],))
        db.executemany("insert into teacher_subjects values (?,?,?)", [(row["id"], c, n) for c, n in subjects])
        if i % 25 == 0:
            db.commit()
            print(f"{i}/{len(listed)}", flush=True)
    emeriti = parse_emeritus(page(EMERITUS))
    for row in emeriti:
        save(db, row, now)
    # The emeritus page names no department; the department pages list their emeriti, untitled. A name on two of them
    # is left without one. save keeps a found one (an emeritus row has no katedra).
    missing = {name_key(r["name"]): r["id"] for r in emeriti}
    missing = {k: i for k, i in missing.items() if not db.execute("select katedra from teachers where id = ?", (i,)).fetchone()[0]}
    found, staff = {}, {}
    katedre = dict(db.execute("select katedra_id, katedra from teachers where katedra_id is not null and not gone"))
    for k, name in katedre.items():
        html = page(f"organizacija/katedre/{k}")
        if html:
            save_department(db, k, name, html, now)
        for key, title in (parse_katedra(html) if html else {}).items():
            staff[key] = title
            if key in missing and not title:
                found.setdefault(key, []).append((name, k))
    for key, places in found.items():
        if len(places) == 1:
            db.execute("update teachers set katedra = ?, katedra_id = ? where id = ?", (*places[0], missing[key]))
    gone = db.execute("update teachers set gone = 1 where last_seen != ?", (now,)).rowcount
    # Off the teachers' list but on a department's (an assistant now a researcher): still at the faculty, not gone;
    # last_seen stays their last day on the list (the build links that day's Wayback copy of the profile). A name a
    # listed teacher has (an old id of an emeritus) is theirs.
    live = {name_key(n) for (n,) in db.execute("select name from teachers where not gone")}
    back = {}
    for i, n in db.execute("select id, name from teachers where gone order by last_seen"):
        if name_key(n) in staff.keys() - live:
            back[name_key(n)] = i  # of two ids, the newest
    for key, i in back.items():
        db.execute("update teachers set gone = 0, title = coalesce(?, title) where id = ?", (staff[key] or None, i))
    gone -= len(back)
    db.commit()
    n = db.execute("select count(*) from teacher_subjects").fetchone()[0]
    print(f"{len(listed)} teachers, {len(emeriti)} emeriti, {n} teacher subjects, {gone} gone", flush=True)
    store_photos(db)


WAYBACK = "https://web.archive.org/"


def name_key(name):
    """A name to match across scripts and spellings: Latin, no diacritics, no middle initial, lower case.
    'Весна К. Спасојевић-Бркић' and 'Vesna Spasojevic Brkic' -> 'vesna spasojevic brkic'."""
    lat = "".join(LATIN[CYRILLIC.index(c)] if c in CYRILLIC else c for c in name.lower())
    lat = lat.translate(str.maketrans("čćšžđ-", "ccszd "))
    return " ".join(w for w in lat.replace(".", ". ").split() if not w.endswith("."))


def main():

    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    commands = dict(sync=sync, photos=store_photos, departments=departments)
    if cmd not in commands:
        sys.exit(__doc__)
    commands[cmd](open_db())


def open_db():
    """nastava.db with the teachers' tables as they are now (nastavnici_istorija.py opens it this way too)."""
    db = connect()
    db.executescript(SCHEMA)
    # photo: added after the table (history); null but for a departed teacher whose photo the faculty lost.
    if "photo" not in {c[1] for c in db.execute("pragma table_info(teachers)")}:
        db.execute("alter table teachers add column photo text")
    # The key had no name (one area of Завршни предмет per teacher); the rows are kept, the departed ones' are slow to read.
    if "primary key (teacher, code))" in db.execute("select sql from sqlite_master where name = 'teacher_subjects'").fetchone()[0]:
        db.executescript(
            "alter table teacher_subjects rename to old_subjects;"
            + SCHEMA
            + "insert into teacher_subjects select * from old_subjects; drop table old_subjects;"
        )
    return db


if __name__ == "__main__":
    main()
