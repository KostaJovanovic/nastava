# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the pages of www.mas.bg.ac.rs and every file they link: the schedule pages (study_pages) and the rest of
the wiki that no other scraper keeps (wiki_pages, NOT_WIKI), found in the wiki's index.

Usage: studije.py sync

Each page and file is stored with its sha256; a changed page or file adds a version and the old one stays.
The site shows the newest version (pages/build.py).
"""

import hashlib
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote, unquote, urljoin, urlparse

SITE = "https://www.mas.bg.ac.rs/"
PAGES = {"kalendar-nastave": "Kalendar nastave", "raspored-predavanja": "Raspored predavanja", "raspored-ispita": "Raspored ispita"}
# Served from the archive's own origin, so only types that cannot run script there.
SAFE = {"pdf", "jpg", "jpeg", "png", "gif", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "rar", "txt", "csv"}

# The rest of the wiki (wiki_pages): every page its index lists but the English copies, the pages other scrapers keep
# (predmeti.py: the course book and the study plans; nastavnici.py: the teachers and the departments), the parts of
# other pages (-kockice, -include) and the wiki's own (its menus, its test pages).
NOT_WIKI = re.compile(
    r"^(en|eng|playground|wiki|wiki-renamed|studije/(predmeti|oas|mas|ds)|fakultet/nastavnici|organizacija/katedre)(/|$)"
    r"|-(kockice|include)$|^(start|menu|navigacija|sidebar|top|topitems|my-404-page|mapa)$"
)
# The wiki pages the site shows (pages/build.py LINKS, in Linkovi): what a student needs. Only theirs (and the schedule
# pages') files are stored here; the rest stay linked to the wiki (~5.8 GB of PDFs, 2026-11), site_files.py keeps a
# local copy of them. Every other page is kept too, not shown.
SHOWN = {
    "upis/start",
    "upis/oas",
    "upis/vaznidatumioas",
    "upis/vaznidatumioas/mi",
    "upis/vaznidatumioas/itm",
    "upis/mas",
    "upis/vaznidatumimas",
    "upis/das",
    "upis/vaznidatumidas",
    "studenti/start",
    "studenti/izbor-predmeta",
    "studenti/finansijsko-zaduzenje",
    "studenti/placanja",
    "studenti/prijava-ispita",
    "servisi/email-za-studente",
    "servisi/eduroam",
    "servisi/vpn",
    "servisi/microsoft-imagine",
    "fakultet/kontakt",
}

SCHEMA = """
create table if not exists study_pages (slug text, sha text, title text, html text, first_seen text, last_seen text, primary key (slug, sha));
create table if not exists study_files (path text, sha text, data blob, first_seen text, last_seen text, primary key (path, sha));
create table if not exists wiki_pages (path text, sha text, title text, html text, first_seen text, last_seen text,
	gone integer not null default 0, primary key (path, sha));
"""


def media_path(url):
    """'studije/i_godina.pdf' for a DokuWiki media link (/_media/... or fetch.php?media=ns:name), else None."""
    u = urlparse(urljoin(SITE, url))
    if u.netloc not in ("www.mas.bg.ac.rs", "mas.bg.ac.rs"):
        return None
    if u.path.startswith("/_media/"):
        return unquote(u.path[len("/_media/") :])
    match = re.search(r"(?:^|&)media=([^&]+)", u.query) if u.path.endswith("fetch.php") else None
    media = match and unquote(match.group(1))
    # fetch.php?media=https://www.mas.bg.ac.rs/_media/...: the wiki's own file, linked by its whole URL.
    return media_path(media) if media and media.startswith(("http:", "https:")) else media.replace(":", "/") if media else None


def safe(path):
    # The path becomes a file path under the built site: no way out of it.
    inside = ".." not in path and not path.startswith(("/", "\\")) and ":" not in path and "\\" not in path
    return inside and "." in path and path.rsplit(".", 1)[-1].lower() in SAFE


def store(db, table, key_col, key, sha, now, **cols):
    db.execute(
        f"insert into {table} ({key_col}, sha, first_seen, last_seen, {', '.join(cols)}) values (?,?,?,?{',?' * len(cols)}) "
        f"on conflict({key_col}, sha) do update set last_seen = excluded.last_seen",
        (key, sha, now, now, *cols.values()),
    )


def parse_index(html):
    """One namespace of the wiki's index (ajax.php call=index) -> ([its namespaces], {page path: its title})."""
    spaces = [unescape(m) for m in re.findall(r'title="([^"]+)" class="idx_dir"', html)]
    pages = {m[0].replace(":", "/"): " ".join(unescape(m[1]).split()) for m in re.findall(r'data-wiki-id="([^"]+)"[^>]*>([^<]*)<', html)}
    return spaces, pages


def wiki_index(get):
    """{path: title} of every page in the wiki not NOT_WIKI and not one of PAGES. get(namespace) -> its index html."""
    todo, seen, pages = [""], set(), {}
    while todo:
        ns = todo.pop()
        if ns not in seen:
            seen.add(ns)
            spaces, found = parse_index(get(ns))
            todo += spaces
            pages |= found
    return {p: t for p, t in pages.items() if not NOT_WIKI.search(p) and p.removeprefix("studije/") not in PAGES}


def sync(db):
    # Imported here: pages/build.py imports this module for media_path and has none of these installed.
    from bs4 import BeautifulSoup
    from documents import is_html_page
    from nastava import DELAY, session

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    files = set()

    def page(path):
        """The page's content (div.page), None when the wiki has no such page."""
        r = session().get(SITE + quote(path), timeout=60)
        if r.status_code in (403, 404):
            return None
        r.raise_for_status()
        main = BeautifulSoup(r.text, "html.parser").select_one("div.page")
        if main is None:
            raise RuntimeError(f"{path}: no div.page, the site changed")
        if path in SHOWN or path.removeprefix("studije/") in PAGES:
            files.update(
                p for tag in main.select("a[href], img[src]") for p in [media_path(tag.get("href") or tag.get("src"))] if p and safe(p)
            )
        return str(main)

    for slug, title in PAGES.items():
        html = page(f"studije/{slug}")
        if html is None:
            raise RuntimeError(f"studije/{slug}: not on the site")
        store(db, "study_pages", "slug", slug, hashlib.sha256(html.encode()).hexdigest(), now, title=title, html=html)
    index = wiki_index(lambda ns: session().post(SITE + "lib/exe/ajax.php", data={"call": "index", "idx": ns}, timeout=60).text)
    # A broken index (an error page) must not mark the whole wiki gone.
    if len(index) < 100:
        raise RuntimeError(f"the wiki index lists {len(index)} pages, the site changed")
    got = []
    for path, title in index.items():
        time.sleep(DELAY)
        html = page(path)
        if html is None:
            print(f"skip {path}: not readable", flush=True)
            continue
        store(db, "wiki_pages", "path", path, hashlib.sha256(html.encode()).hexdigest(), now, title=title or path, html=html)
        db.execute("update wiki_pages set gone = 0 where path = ?", (path,))
        got.append(path)
    db.execute(f"update wiki_pages set gone = 1 where path not in ({','.join('?' * len(got))})", got)
    ok = skipped = 0
    for path in sorted(files):
        time.sleep(DELAY)
        r = session().get(SITE + "_media/" + path, timeout=300)
        if r.status_code == 404 or is_html_page(r.content):
            print(f"skip {path}: {r.status_code}, html page" if r.ok else f"skip {path}: {r.status_code}", flush=True)
            skipped += 1
            continue
        r.raise_for_status()
        store(db, "study_files", "path", path, hashlib.sha256(r.content).hexdigest(), now, data=r.content)
        ok += 1
    db.commit()
    print(f"{len(PAGES)} schedule pages, {len(got)} wiki pages, {ok} files, {skipped} skipped", flush=True)


def main():
    from nastava import connect

    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    db.executescript(SCHEMA)
    if (sys.argv[1] if len(sys.argv) > 1 else "sync") != "sync":
        sys.exit(__doc__)
    sync(db)


if __name__ == "__main__":
    # media_path and safe are checked in test/parsers_test.py.
    main()
