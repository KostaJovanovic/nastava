"""What the scrapers share: the database, the HTTP session and its run log, the time, file links.

A scraper imports this and translit.py, and no other scraper but the one of its own source (documents.py: nastava's
attachments; site_files.py: studije's files). requests is imported where it is used: build.py imports studije and
nastavnici for their URL helpers and does not install it.
"""

import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
DB = os.getenv("DB", str(ROOT / "nastava.db"))
# The pause between requests to www.mas.bg.ac.rs, the board and the news (cent.py and katedre.py have their own).
DELAY = float(os.getenv("DELAY", "0.5"))
USER_AGENT = "Mozilla/5.0 (personal archive)"
LOCAL = threading.local()
# A logged run (ci/deploy.sh): the folder its log is gathered in, for ci/runs.py.
RUN_DIR = os.getenv("RUN_DIR")
_LOG = threading.Lock()

# A file link's icon (an image in the link) gives way to the file's name; these hosts are videos.
FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z|dwg|txt|m|py|csv|odt|ods|step|stp|igs|nc|jpe?g|png|gif|webp)$", re.I)
VIDEO = re.compile(r"(drive\.google\.com|docs\.google\.com|youtube\.com|youtu\.be|vimeo\.com)", re.I)


def connect(schema=""):
    """nastava.db (DB), in WAL, with the scraper's tables made if missing."""
    db = sqlite3.connect(DB, timeout=60)
    db.execute("pragma journal_mode = wal")
    db.executescript(schema)
    return db


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def session():
    # One session per thread; retries with backoff on server errors and timeouts.
    if not hasattr(LOCAL, "s"):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        retry = Retry(total=6, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        LOCAL.s = instrument(s)
    return LOCAL.s


def plain_session():
    """No retries (katedre.py's crawl meets dead links, and backing off on each would take minutes apiece)."""
    import requests

    s = instrument(requests.Session())
    s.headers["User-Agent"] = USER_AGENT
    return s


def instrument(s):
    """In a logged run (RUN_DIR), every request of the session is a line of RUN_DIR/requests.jsonl for ci/runs.py:
    the scraper, host, status or error, seconds, bytes, retries, and whether the server sends ETag / Last-Modified (so
    a request could ask for the page only if it changed). Returns s."""
    if not RUN_DIR:
        return s
    import requests

    scraper = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    request = s.request

    def logged(method, url, *a, **kw):
        t = time.monotonic()
        rec = dict(scraper=scraper, method=method, url=url, host=urlsplit(url).hostname)
        try:
            r = request(method, url, *a, **kw)
        except requests.RequestException as e:
            rec.update(status=type(e).__name__, s=round(time.monotonic() - t, 3))
            raise
        else:
            h = r.headers
            # A streamed body (a file katedre.py does not download) by its header: reading it would download it.
            size = int(h.get("Content-Length") or 0) if kw.get("stream") else len(r.content)
            history = getattr(getattr(r.raw, "retries", None), "history", None) or ()
            rec.update(
                status=r.status_code,
                s=round(time.monotonic() - t, 3),
                bytes=size,
                retries=len(history),
                etag="ETag" in h,
                modified="Last-Modified" in h,
            )
            return r
        finally:
            with _LOG, open(os.path.join(RUN_DIR, "requests.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    s.request = logged
    return s


def is_html_page(data):
    """A download that is a web page (an error or login page), not the file."""
    head = data[:512].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html"))


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
        name = path.rsplit("/", 1)[-1] if FILE.search(path) else "video" if VIDEO.search(href) else (a.img and a.img.get("alt")) or "link"
        a.clear()
        a.append(name)
