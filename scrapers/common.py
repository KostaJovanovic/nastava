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

ROOT = Path(__file__).resolve().parent.parent  # the repo (this file is in scrapers/)
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


REPO = "KostaJovanovic/nastava"
# The kinds the Worker serves inline (pages/src/index.js INLINE) and that get a thumbnail.
PREVIEW = {"pdf", "jpg", "jpeg", "png", "gif"}
THUMB_WIDTH = 240  # px: detail.html's card at 1x; four times a post's .att__img (style.css)


def asset_name(path):
    """A file's asset name, from its path: GitHub changes spaces and non-ASCII letters in a name (dlwms's)."""
    import hashlib

    base = path.rsplit("/", 1)[-1]
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    ext = ext if re.fullmatch(r"[a-z0-9]{1,8}", ext) else "bin"
    return f"{hashlib.sha256(path.encode()).hexdigest()[:20]}.{ext}"


def thumb_asset(path):
    """The asset name of a file's thumbnail (thumbnail): its own hash, so an image's thumbnail is not the image."""
    return asset_name(f"{path}#thumb.jpg")


def thumbnail(name, data):
    """A PDF's first page or an image as a small JPEG (THUMB_WIDTH wide), or None: another kind, or one PyMuPDF cannot
    open."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    # PyMuPDF "repairs" any bytes into a blank PDF page: a PDF must have its header (within 1 KiB, as readers allow).
    if ext not in PREVIEW or (ext == "pdf" and b"%PDF" not in data[:1024]):
        return None
    import pymupdf

    try:
        with pymupdf.open(stream=data, filetype=ext) as doc:
            page = doc[0]
            zoom = THUMB_WIDTH / page.rect.width
            return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("jpg", jpg_quality=75)
    except Exception:  # a broken or encrypted file: no thumbnail, the file is still published
        return None


def gh(*args):
    import subprocess

    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def release_assets(tag, title, notes):
    """The uploaded assets' names of the release tag in REPO; the release is made when missing. An asset an upload left
    half done (state "starter", a cancelled run) is deleted: its name would block the upload that sends it again."""
    import subprocess

    try:
        rid = json.loads(gh("api", f"repos/{REPO}/releases/tags/{tag}"))["id"]
    except subprocess.CalledProcessError:
        gh("release", "create", tag, "-R", REPO, "--latest=false", "--title", title, "--notes", notes)
        return set()
    q = '.[] | "\\(.state) \\(.id) \\(.name)"'
    have = set()
    for line in gh("api", "--paginate", f"repos/{REPO}/releases/{rid}/assets?per_page=100", "-q", q).split("\n"):
        if not line:
            continue
        state, asset_id, name = line.split(" ", 2)
        if state == "uploaded":
            have.add(name)
        else:
            gh("api", "-X", "DELETE", f"repos/{REPO}/releases/assets/{asset_id}")
    return have


def upload_assets(tag, files):
    """Upload {asset name: bytes} to the release tag, 20 to an upload (gh names an asset after its file)."""
    import tempfile

    names = list(files)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(0, len(names), 20):
            batch = []
            for name in names[i : i + 20]:
                (Path(tmp) / name).write_bytes(files[name])
                batch.append(str(Path(tmp) / name))
            gh("release", "upload", tag, "-R", REPO, "--clobber", *batch)
            print(f"{tag}: {min(i + 20, len(names))}/{len(names)}", flush=True)


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


# A student's index number (259/2023), not a school year (2025/2026): its first number is under 1900.
INDEX_NO = re.compile(r"\b(\d{1,4})\s*/\s*(20\d\d)\b")
# A spreadsheet's column of who a student is: index (ШПАН, Бр. Инд.) or surname. Only in a spreadsheet: a handout's
# "индекс" is a subscript.
# Anywhere in a short cell (roster_head): "Ime i prezime", "Broj indeksa" name a student as "Презиме" does.
_ROSTER = r"шпан|špan|span|индекс\w*|indeks\w*|index|бр\.?\s*инд\w*\.?|br\.?\s*ind\w*\.?|презиме|prezime"
ROSTER_HEAD = re.compile(rf"(?<!\w)({_ROSTER})(?!\w)", re.I)


def roster_head(c):
    """A spreadsheet cell that heads a column of students: short (a heading, not a sentence), with a ROSTER_HEAD word."""
    return isinstance(c, str) and len(c.strip()) <= 40 and ROSTER_HEAD.search(c)

SHEETS = (".xlsx", ".xlsm", ".xls", ".ods", ".csv")


def file_text(name, data):
    """A file's text, for lists_students: [cells] of a spreadsheet's rows, else [the text]; [] for another kind (an
    image, a CAD file) or one that cannot be read. The readers are imported here: only teams.py and moodle.py use them."""
    import io

    ext = os.path.splitext(name.lower())[1]
    try:
        if ext in (".xlsx", ".xlsm"):
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            return [str(c) for ws in wb.worksheets for row in ws.iter_rows(values_only=True) for c in row if c is not None]
        if ext == ".xls":
            import xlrd

            book = xlrd.open_workbook(file_contents=data)
            return [str(c) for s in book.sheets() for i in range(s.nrows) for c in s.row_values(i) if c != ""]
        if ext == ".csv":
            return [c for line in data.decode("utf-8", "ignore").splitlines() for c in re.split(r"[,;\t]", line)]
        if ext == ".pdf":
            from pypdf import PdfReader

            return ["\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)]
        if ext == ".docx":
            import docx

            d = docx.Document(io.BytesIO(data))
            return ["\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])]
        if ext == ".txt":
            return [data.decode("utf-8", "ignore")]
    except Exception:  # a file the reader cannot open is not a list it can see
        return []
    return []


def lists_students(name, data):
    """Why a file from a closed class (Teams, Moodle: only its students see it) must not be published here, or None:
    a spreadsheet with a column of index numbers or surnames, or any file with five index numbers or more (exam
    results). shortcut: a scan (a PDF with no text) or an .ods is not read; a list in one passes."""
    text = file_text(name, data)
    if name.lower().endswith(SHEETS) and (head := next((c for c in text if roster_head(c)), None)):
        return f"a list of students (column {head.strip()!r})"
    n = sum(int(m[1]) < 1900 for t in text for m in INDEX_NO.finditer(t))
    return f"{n} index numbers" if n >= 5 else None


# A spreadsheet's columns that name a student, blacked out: the index (ШПАН, Бр. Инд., and its year: Год., уписан),
# surname, name.
# Anywhere in the heading cell, as ROSTER_HEAD: "Ime i prezime", "Godina upisa" too.
WHO_HEAD = re.compile(rf"(?<!\w)({_ROSTER}|име|ime|студент\w*|student\w*|год\w*\.?|god\w*\.?|уписан\w*|upisan\w*)(?!\w)", re.I)


def blocks(s):
    """Each character a block, the spaces kept (as teams.py redact)."""
    return re.sub(r"\S", "█", s)


def redact_xlsx(data):
    """A results sheet with its students' columns (WHO_HEAD, in the row naming them) and any index number elsewhere
    blacked out; the points and grades stay. A column is blacked out in every row but its heading's, above it too
    (names left above the table). Returns (the file, how many cells)."""
    import io

    import openpyxl

    wb, n = openpyxl.load_workbook(io.BytesIO(data)), 0
    for ws in wb.worksheets:
        head = next((row for row in ws.iter_rows() if any(roster_head(c.value) for c in row)), None)
        cols = {c.column for c in head or () if isinstance(c.value, str) and len(c.value.strip()) <= 40 and WHO_HEAD.search(c.value)}
        for row in ws.iter_rows():
            if head and row[0].row == head[0].row:
                continue
            above = head and row[0].row < head[0].row
            for c in row:
                if c.value is None or isinstance(c.value, str) and c.value.startswith("="):
                    continue
                v = str(c.value)
                # Above the heading, a name has no digits; the sheet's title there has its school year.
                who = c.column in cols and not (above and re.search(r"\d", v))
                new = blocks(v) if who else INDEX_NO.sub(lambda m: blocks(m[0]) if int(m[1]) < 1900 else m[0], v)
                if new != v:
                    c.value, n = new, n + 1
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), n


def redact_pdf(data):
    """A results PDF with each index number and the words of its row that have letters (surname, name) removed, text
    and all (a black box over text would leave it to copy); the grades and points stay. A row: the words whose middle
    is within the index's height. Returns (the file, how many words)."""
    import pymupdf

    doc, n = pymupdf.open(stream=data, filetype="pdf"), 0
    for page in doc:
        words = page.get_text("words")
        for w in words:
            m = INDEX_NO.fullmatch(w[4])
            if not m or int(m[1]) >= 1900:
                continue
            for v in words:
                if w[1] - 1 <= (v[1] + v[3]) / 2 <= w[3] + 1 and (v is w or re.search(r"[^\W\d_]", v[4])):
                    page.add_redact_annot(pymupdf.Rect(v[:4]), fill=(0, 0, 0))
                    n += 1
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE)
    return doc.tobytes(garbage=3, deflate=True), n


def redact_students(name, data):
    """A file from a closed class (Teams, Moodle, a class's mail) as it may be published: unchanged when it lists no
    students (lists_students), else with their names and index numbers blacked out (a PDF, an .xlsx), else None (a
    kind not redacted here: .xls, .docx, .csv). Returns (data or None, what was done or None)."""
    why = lists_students(name, data)
    if not why:
        return data, None
    ext = os.path.splitext(name.lower())[1]
    if ext in (".xlsx", ".xlsm"):
        # Its students' columns are found by their heading (roster_head); found only by index numbers, the names
        # beside them would stay: not published.
        if not why.startswith("a list of students"):
            return None, f"{why}, no column heading names the students: not published"
        out, n = redact_xlsx(data)
    elif ext == ".pdf":
        out, n = redact_pdf(data)
    else:
        return None, f"{why}, a {ext} is not redacted: not published"
    # Still a list after it: the rows were not found (a scan's or another layout), so it is not published.
    if lists_students(name, out) and ext == ".pdf":
        return None, f"{why}, the redaction missed some: not published"
    return out, f"{why}: {n} redacted"


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
