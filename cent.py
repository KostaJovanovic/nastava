# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the subject pages of cent.mas.bg.ac.rs (Катедра за производно машинство, WordPress with the Divi builder):
every page as it is shown (a new version when its content changes), and each notice (обавештење) on a page apart.
The site links its files (wp-content/uploads, Google Drive); they are not downloaded.

Usage: cent.py sync
  sync   list the pages (REST API, 3 requests), fetch each new or changed one (the list's "modified") and every
         notices page, store new versions and notices; a page or notice no longer there is marked gone.
"""
import copy
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from bs4 import BeautifulSoup

SITE = "https://cent.mas.bg.ac.rs"
DB = os.getenv("DB", str(Path(__file__).resolve().parent / "nastava.db"))
DELAY = float(os.getenv("DELAY", "1.0"))
SCHEMA = """
create table if not exists cent_pages (id integer, sha text, parent integer, menu_order integer, slug text, title text,
	link text, modified text, code text, html text, first_seen text, last_seen text, gone integer not null default 0,
	primary key (id, sha));
create table if not exists cent_notices (nid integer primary key autoincrement, key text unique, page integer,
	title text, date text, html text, files text, first_seen text, last_seen text, gone integer not null default 0);
"""
# A file link's icon (an image in the link) gives way to the file's name; these hosts are videos.
FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z|dwg|txt|m|py|csv|odt|ods|step|stp|igs|nc|jpe?g|png|gif|webp)$", re.I)
VIDEO = re.compile(r"(drive\.google\.com|docs\.google\.com|youtube\.com|youtu\.be|vimeo\.com)", re.I)
FOOTER = "ОАС МАС ДАС"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (personal archive)"
    return s


def get(s, url, **kw):
    r = s.get(url, timeout=60, **kw)
    time.sleep(DELAY)
    r.raise_for_status()
    return r


def list_pages(s):
    """Every published page: id, parent, menu_order, slug, title, link, modified (the REST API, 100 a request)."""
    out, page = [], 1
    while True:
        r = get(s, f"{SITE}/wp-json/wp/v2/pages", params=dict(per_page=100, page=page,
                _fields="id,parent,menu_order,slug,title,link,modified"))
        out += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            return out
        page += 1


def link_modules(soup):
    """Divi makes a whole module a link with a script (et_link_options_data: [{class, url}]), not an <a>: a
    shift's student list, say. Put those links into the page as <a>, so they survive without the script."""
    for script in soup.find_all("script"):
        m = re.search(r"et_link_options_data\s*=\s*(\[.*?\]);", script.string or "", re.S)
        if not m:
            continue
        for o in json.loads(m[1]):
            if not o.get("url") or o["url"].startswith("#"):
                continue
            for el in soup.select("." + o["class"]):
                # A row of clickable modules is clickable too (its first one's link): only the modules get theirs.
                if el.find("a") or el.select_one(".et_clickable") or not el.get_text(strip=True):
                    continue
                a = soup.new_tag("a", href=o["url"])
                for child in list(el.children):
                    a.append(child.extract())
                el.append(a)


def name_icons(soup, page_url):
    """A link whose content is only an icon gets text: the file's name, "video", or the image's alt. A link to the
    page itself (an icon in a heading) or to nowhere (href="", an icon with no file yet) goes."""
    for a in soup.find_all("a", href=True):
        if a.decomposed:  # inside a link that went
            continue
        href = a["href"].split("#")[0].strip()
        if (not href or href.rstrip("/") == page_url.rstrip("/")) and not a.get_text(strip=True):
            a.decompose()
            continue
        if a.get_text(strip=True):
            continue
        path = unquote(urlsplit(href).path)
        name = (path.rsplit("/", 1)[-1] if FILE.search(path) else "video" if VIDEO.search(href)
                else (a.img and a.img.get("alt")) or "link")
        a.clear()
        a.append(name)


def parse(html, page_url):
    """A rendered page -> (code, content html, notices). code: the subject's code in the header ("ID: 1617"), None on
    a page that is not a subject's. The content: the sections between the header and the footer, with Divi's
    script links made <a> and icons named. A notice: dict(title, date (ISO), html, files)."""
    soup = BeautifulSoup(html, "html.parser")
    link_modules(soup)
    main = soup.select_one("#main-content")
    if main is None:
        raise ValueError(f"{page_url}: no #main-content (the theme changed?)")
    sections = main.select(".et_pb_section")
    head = main.select_one("#brzilinkovi")
    m = head and re.search(r"\bID:\s*(\d{3,4})\b", head.get_text(" ", strip=True))
    code = m[1] if m else None
    body = [x for x in sections if x is not head and x.get_text(" ", strip=True) != FOOTER
            and (x.get_text(strip=True) or x.select("a[href]"))]
    for x in body:
        name_icons(x, page_url)
        for t in x.find_all(["script", "style", "noscript"]):
            t.decompose()
    page = "".join(str(x) for x in body)
    notices = []
    for it in main.select(".vesti_predmeta_item"):
        title = it.select_one(".vesti_predmeta_title")
        date = it.select_one(".vesti_predmeta_date")
        d = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date.get_text() if date else "")
        el = copy.copy(it)  # the page's copy keeps its title and date
        for t in el.select(".vesti_predmeta_title, .vesti_predmeta_date"):
            t.decompose()
        notices.append(dict(title=title.get_text(" ", strip=True) if title else "",
                            date=f"{d[3]}-{int(d[2]):02d}-{int(d[1]):02d}" if d else None,
                            files=[a["href"] for a in it.select(".vesti_predmeta_files a[href]")],
                            html=el.decode_contents().strip()))
    return code, page, notices


def store_page(db, p, code, html, seen):
    """A new version when the content differs from the newest stored; else that one is seen again."""
    sha = hashlib.sha1(html.encode()).hexdigest()
    title = unescape(p["title"]["rendered"])
    last = db.execute("select sha from cent_pages where id = ? order by last_seen desc limit 1", (p["id"],)).fetchone()
    if db.execute("select 1 from cent_pages where id = ? and sha = ?", (p["id"], sha)).fetchone():
        # The newest again, or back to an older version (that one becomes the newest).
        db.execute("update cent_pages set last_seen = ?, modified = ?, parent = ?, menu_order = ?, title = ?, link = ?, "
                   "code = ?, gone = 0 where id = ? and sha = ?",
                   (seen, p["modified"], p["parent"], p["menu_order"], title, p["link"], code, p["id"], sha))
        return last[0] != sha
    db.execute("insert into cent_pages values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
               (p["id"], sha, p["parent"], p["menu_order"], p["slug"], title, p["link"], p["modified"], code, html,
                seen, seen))
    return True


def store_notices(db, page_id, notices, seen):
    """A notice is its page, title and date; a changed text updates it. One no longer on its page is marked gone."""
    keys = []
    for n in notices:
        key = hashlib.sha1(f"{page_id}|{n['title']}|{n['date']}".encode()).hexdigest()
        keys.append(key)
        db.execute("insert into cent_notices (key, page, title, date, html, files, first_seen, last_seen) "
                   "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict (key) do update set html = excluded.html, "
                   "files = excluded.files, last_seen = excluded.last_seen, gone = 0",
                   (key, page_id, n["title"], n["date"], n["html"], json.dumps(n["files"]), seen, seen))
    db.execute(f"update cent_notices set gone = 1 where page = ? and key not in ({','.join('?' * len(keys))})",
               (page_id, *keys))


def sync():
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    s, seen = session(), now()
    pages = list_pages(s)
    known = dict(db.execute("select id, modified from cent_pages c where last_seen = "
                            "(select max(last_seen) from cent_pages where id = c.id)"))
    fetched = new = 0
    for p in pages:
        # The notices pages every time: a notice may not change the page's "modified".
        if known.get(p["id"]) == p["modified"] and "obavestenja" not in p["slug"]:
            db.execute("update cent_pages set last_seen = ? where id = ? and last_seen = "
                       "(select max(last_seen) from cent_pages where id = ?)", (seen, p["id"], p["id"]))
            continue
        code, html, notices = parse(get(s, p["link"]).text, p["link"])
        fetched += 1
        new += store_page(db, p, code, html, seen)
        store_notices(db, p["id"], notices, seen)
        db.commit()
    live = [p["id"] for p in pages]
    db.execute(f"update cent_pages set gone = 1 where id not in ({','.join('?' * len(live))})", live)
    db.commit()
    n = db.execute("select count(*), sum(gone = 0) from cent_notices").fetchone()
    print(f"cent: {len(pages)} pages, {fetched} fetched, {new} new versions; {n[0]} notices ({n[1]} on the site)")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["sync"]:
            sync()
        case _:
            sys.exit(__doc__)
