# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Teachers who left before the archive began (once, by hand): from the Wayback Machine's copies of the faculty's
teacher list (2014 on) and from masinac.org (2008 on), into nastavnici.py's tables.

Usage: nastavnici_istorija.py
"""

import re
import sys
import time
from urllib.parse import urljoin

from common import DELAY, session
from nastavnici import (
    EMERITUS,
    LIST,
    SITE,
    WAYBACK,
    name_key,
    open_db,
    parse_emeritus,
    parse_list,
    parse_profile,
    plain_name,
    save,
    store_photos,
)
from translit import to_cyr

MASINAC = "https://www.masinac.org/"


def person_keys(row):
    """What identifies a person across ids and sites: the name, the e-mail before @."""
    user = (row.get("email") or "").split("@")[0].lower()
    return {name_key(plain_name(row["full_name"]))} | ({user} if user else set())


def image_key(url):
    """The person an image file is named after, as a username or a name_key: '.../dmilutinovic.jpg' -> 'dmilutinovic',
    '.../photo_sonja_josipovic.jpg' -> 'sonja josipovic'."""
    words = re.split(r"[_\-.\s]+", url.split("?")[0].rsplit("/", 1)[1].lower())[:-1]
    return " ".join(words[-2:])


def parse_masinac(html):
    """A lecturer page of masinac.org (a student portal that copied the faculty's teacher data, 2008 on): its fields,
    the photo's URL and the table without the photo."""
    from bs4 import BeautifulSoup

    table = BeautifulSoup(html, "html.parser").select_one("table#zaposleni")
    if table is None:
        return None
    row = {
        tr.select_one("td.left").get_text(strip=True): " ".join(tr.select_one("td.right").get_text(" ", strip=True).split())
        for tr in table.select("tr")
        if tr.select_one("td.left")
    }
    img = table.select_one("td.slika img")
    photo = img and urljoin(MASINAC, img["src"])
    if img:
        img.find_parent("td").decompose()
    return dict(row, photo=photo, html=f'<div class="page">{table}</div>')


def wb_time(ts):
    """'20140629012301' -> '2014-06-29T01:23:01+00:00', the form of first_seen and last_seen."""
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}+00:00"


def history(db):
    """Teachers who left before the archive began, from the Wayback Machine's copies of the list (2014 on) and from
    masinac.org (2008 on). Each one not listed today is stored gone, with their last archived profile and a photo that
    still loads; listed teachers are not touched."""
    from collections import Counter, defaultdict

    def get(url, tries=4):
        """The page's text; None after the tries (raises for the Wayback Machine, where every page asked for exists)."""
        for attempt in range(tries):
            time.sleep(1.5 * 2**attempt)
            try:
                # masinac.org sends a missing page to its home page: not followed.
                r = session().get(url, timeout=90, allow_redirects=url.startswith(WAYBACK))
            except Exception as e:
                print(f"retry {url}: {e}", flush=True)
                continue
            if r.status_code == 200 and r.text:
                return r.text
            print(f"retry {url}: {r.status_code}", flush=True)
        if url.startswith(WAYBACK):
            raise RuntimeError(f"wayback: no answer for {url}")

    def captures(url, prefix=False, match="", images=False):
        """[(timestamp, original url)] of each distinct 200 capture (match: 'domain' for every subdomain)."""
        q = f"{WAYBACK}cdx/search/cdx?url={url}&filter=statuscode:200&fl=timestamp,original"
        q += f"&matchType={match or 'prefix'}" if prefix or match else "&collapse=digest"
        q += "&filter=mimetype:image/.*&collapse=urlkey" if images else ""
        return sorted(tuple(l.split(" ")) for l in get(q).splitlines() if l)

    def page(ts, url):
        return get(f"{WAYBACK}web/{ts}id_/{url}")

    live = {r[0] for r in db.execute("select id from teachers where not gone")}
    seen = {}  # id -> [first ts, last ts, row of the last list]
    for path, parse in ((LIST, parse_list), (EMERITUS, parse_emeritus)):
        for ts, url in captures("www.mas.bg.ac.rs/" + path):
            rows = parse(page(ts, url))
            print(f"{path} {ts}: {len(rows)}", flush=True)
            for row in rows:
                seen.setdefault(row["id"], [ts, ts, row])[1:] = [ts, row]
    profiles = {}
    for ts, url in captures("www.mas.bg.ac.rs/fakultet/nastavnici/", prefix=True):
        m = re.search(r"/fakultet/nastavnici/(\d+)$", url.split("?")[0])
        if m:
            profiles[m[1]] = (ts, url)
    # One person under several ids (the faculty renumbered its pages in 2015; a teacher who became emeritus), matched
    # by name or e-mail: the newest id is kept, with the earliest first day. None if they are listed today.
    taken = {k for n, u in db.execute("select name, username from teachers where not gone") for k in (name_key(n), u) if k}
    people = []  # [keys, ids newest first]
    for i in sorted(seen, key=lambda i: seen[i][1], reverse=True):
        keys = person_keys(seen[i][2])
        p = next((p for p in people if p[0] & keys), None)
        if p:
            p[0] |= keys
            p[1].append(i)
        else:
            people.append([keys, [i]])
    left = {
        ids[0]: [min(seen[i][0] for i in ids), *seen[ids[0]][1:]] for keys, ids in people if not keys & taken and not live.intersection(ids)
    }
    print(f"{len(seen)} ids in the archived lists, {len(people)} people, {len(left)} not listed today", flush=True)
    for n, (i, (first, last, row)) in enumerate(left.items(), 1):
        subjects = []
        if i in profiles:
            try:
                profile, subjects = parse_profile(page(*profiles[i]))
                # The faculty reuses a page's number: a profile of someone else (153: Покрајац, later Бојовић) is not theirs.
                if name_key(profile["name"]) == name_key(plain_name(row["full_name"])):
                    row = dict(row, **{k: v for k, v in profile.items() if v or k not in row})
                else:
                    print(f"{i} {row['full_name']}: the profile is {profile['name']}, not used", flush=True)
                    subjects = []
            except RuntimeError as e:
                print(f"{i} {row['full_name']}: {e}", flush=True)
        if row.get("katedra"):
            row["katedra"] = row["katedra"][0].upper() + row["katedra"][1:]
        save(db, dict(row, name=row.get("name") or plain_name(row["full_name"]), emeritus=int(i.startswith("emeritus-"))), wb_time(last))
        db.execute("update teachers set first_seen = ?, gone = 1 where id = ?", (wb_time(first), i))
        db.execute("delete from teacher_subjects where teacher = ?", (i,))
        db.executemany("insert into teacher_subjects values (?,?,?)", [(i, c, s) for c, s in subjects])
        db.commit()
        print(f"{n}/{len(left)} {row['full_name']} {first[:4]}-{last[:4]}", flush=True)

    # masinac.org: its lecturers in no list here are added, gone; its photos fill the ones the faculty lost.
    pages = {}  # path -> [first ts, last ts, last url]
    for ts, url in captures("masinac.org/fakultet/katedre/", prefix=True):
        m = re.search(r"/fakultet/(katedre/([a-z]+)/predavaci/[a-z0-9-]+)$", url.split("?")[0])
        if m:
            pages.setdefault(m[1], [ts, ts, url])[1:] = [ts, url]
    known = {}  # name key or username -> (id, katedra)
    for i, name, user, kat in db.execute("select id, name, username, katedra from teachers"):
        known.update({k: (i, kat) for k in (name_key(name), user) if k})
    lecturers = []
    for path, (first, last, url) in pages.items():
        html = get(MASINAC + "fakultet/" + path, tries=1)
        try:
            html = html or page(last, url)
        except RuntimeError as e:
            print(e, flush=True)
        row = parse_masinac(html or "")
        if row is None:
            print(f"masinac.org {path}: no data table", flush=True)
            continue
        name, _, degree = row.get("Ime i prezime", "").partition(",")
        # 'Dragan Lj.Milanović' -> 'Драган Љ. Милановић'
        row.update(path=path, first=first, name=to_cyr(re.sub(r"\.(?=\S)", ". ", name.strip())), dr="dr" in degree)
        stem = row["photo"] and row["photo"].rsplit("/", 1)[1].split(".")[0].lower()
        # By e-mail or photo name; by name only without a middle initial ('Dragan Lj. Milanović' is not 'Драган Д.').
        row["keys"] = [k for k in ((row.get("Email") or "").split("@")[0].lower(), stem) if k]
        row["keys"] += [name_key(row["name"])] if "." not in row["name"] else []
        row["match"] = next((known[k] for k in row["keys"] if k in known), None)
        lecturers.append(row)
    katedra = defaultdict(Counter)  # masinac.org katedra -> the faculty's names of it, from the teachers in both
    for row in lecturers:
        if row["match"] and row["match"][1]:
            katedra[row["path"].split("/")[1]][row["match"][1]] += 1
    new = [row for row in lecturers if not row["match"]]
    for row in new:
        k, slug = row["path"].split("/")[1], row["path"].rsplit("/", 1)[1]
        title = row.get("Zvanje") or row.get("Naučno zvanje")
        i = f"masinac-{k}-{slug}"
        save(
            db,
            dict(
                id=i,
                full_name=("др " if row["dr"] else "") + row["name"],
                name=row["name"],
                title=title and to_cyr(title.lower()),
                katedra=katedra[k] and katedra[k].most_common(1)[0][0],
                email=row.get("Email"),
                phone=row.get("Broj telefona"),
                html=row["html"],
                emeritus=0,
            ),
            wb_time(row["first"]),
        )
        db.execute("update teachers set gone = 1 where id = ?", (i,))
    db.commit()
    print(f"masinac.org: {len(lecturers)} lecturers, {len(new)} added: {', '.join(r['name'] for r in new)}", flush=True)

    # A departed teacher's photo, the first that loads: the faculty's (stored none: the profile has it), its Wayback
    # copy, masinac.org's (live, then archived), last an archived image on another faculty site named after them
    # (the katedra sites, CeNT: 'dmilutinovic.jpg', 'photo_sonja_josipovic.jpg'). store_photos keeps a copy.
    def image(url):
        time.sleep(DELAY)
        try:
            r = session().head(url, timeout=60, allow_redirects=url.startswith(WAYBACK))
        except Exception:
            return False
        return r.status_code == 200 and r.headers.get("content-type", "").startswith("image")

    archived = {}  # the faculty's photo name or masinac.org's photo path -> its Wayback copy
    for ts, url in captures("www.mas.bg.ac.rs/_media/fakultet/nastavnici/", prefix=True):
        archived[url.split("?")[0].rsplit("/", 1)[1].lower()] = f"{WAYBACK}web/{ts}im_/{url}"
    for ts, url in captures("masinac.org/images/predavaci/", prefix=True):
        archived[url.split("?")[0].split("masinac.org/", 1)[1].lower()] = f"{WAYBACK}web/{ts}im_/{url}"
    elsewhere = {}  # username or 'first last' -> an archived image of that name on a *.mas.bg.ac.rs site
    for ts, url in captures("mas.bg.ac.rs", match="domain", images=True):
        elsewhere[image_key(url)] = f"{WAYBACK}web/{ts}im_/{url}"
    theirs = {k: row["photo"] for row in lecturers if row["photo"] for k in row["keys"]}
    found = Counter()
    for i, name, user, html in db.execute("select id, name, username, html from teachers where gone").fetchall():
        m = re.search(r'_media/fakultet/nastavnici/([^"?]+)', html or "")
        mine = next((theirs[k] for k in (user, name_key(name)) if k in theirs), None)
        candidates = [
            ("faculty", m and SITE + "_media/fakultet/nastavnici/" + m[1]),
            ("wayback", m and archived.get(m[1].lower())),
            ("masinac.org", mine),
            ("masinac.org", mine and archived.get(mine.split("masinac.org/", 1)[1].lower())),
            ("other site", next((elsewhere[k] for k in (user, name_key(name)) if k in elsewhere), None)),
        ]
        how, photo = next(((how, url) for how, url in candidates if url and image(url)), ("none", None))
        db.execute("update teachers set photo = ? where id = ?", (None if how == "faculty" else photo, i))
        found[how] += 1
    db.commit()
    print(f"photos of the departed: {dict(found)}", flush=True)
    store_photos(db)


if __name__ == "__main__":
    assert wb_time("20140629012301") == "2014-06-29T01:23:01+00:00"
    assert image_key("http://cent.mas.bg.ac.rs/ljudi/slike/velike/dmilutinovic.jpg") == "dmilutinovic"
    assert image_key("http://ie.mas.bg.ac.rs/data_store/images/zaposleni/photo_sonja_josipovic.jpg?x=1") == "sonja josipovic"
    assert person_keys(dict(full_name="др Зоран В. Стаменић", email="ZStamenic@mas.bg.ac.rs")) == {"zoran stamenic", "zstamenic"}
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        sys.exit(__doc__)
    history(open_db())
