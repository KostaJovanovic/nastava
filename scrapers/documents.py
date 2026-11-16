# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4", "pymupdf", "python-docx", "python-pptx", "openpyxl", "libarchive-c"]
# ///
"""Archive every attachment of nastava.mas.bg.ac.rs.

Usage: documents.py download | extract [--all] | sync | stats | host
  download  fetch the pending attachments: the ones the posts link, and every id from 1 up to
            the highest linked id that no post links (an attachment can outlive its post link)
  extract   extract text from the downloaded files (no network)
  sync      download + extract
  host      the attachments of the posts since HOST_FROM: download, extract, thumbnail, upload to
            the release files-<school year> (ci/deploy.sh, every scrape)

Files go to files/<id>/<file name>. The download is a plain GET of download/file.php?id=N.
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote

import requests

from common import DELAY, ROOT, asset_name, is_html_page, release_assets, session, thumb_asset, thumbnail, upload_assets
from nastava import BASE, WORKERS, connect

FILES = os.getenv("FILES", str(ROOT / "files"))
TEXT_LIMIT = 5_000_000
MEMBER_LIMIT = 100_000_000
SOFFICE = shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"

TEXT_EXT = {
    "txt",
    "csv",
    "md",
    "json",
    "xml",
    "html",
    "htm",
    "sql",
    "py",
    "java",
    "c",
    "cpp",
    "h",
    "hpp",
    "cs",
    "js",
    "ts",
    "php",
    "css",
    "sh",
    "bat",
    "r",
    "m",
    "tex",
    "log",
    "ini",
    "yml",
    "yaml",
    "rtf",
    "asm",
    "pas",
    "vhd",
    "v",
    "ipynb",
    "tsv",
    "ino",
    "kt",
    "swift",
    "go",
    "rs",
    "rb",
    "cshtml",
    "aspx",
    "config",
    "properties",
    "srt",
}

MAGIC = [
    (b"%PDF", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG", "image/png"),
    (b"GIF8", "image/gif"),
    (b"BM", "image/bmp"),
    (b"PK\x03\x04", "application/zip"),
    (b"\xd0\xcf\x11\xe0", "application/x-ole"),
    (b"Rar!", "application/x-rar"),
    (b"{\\rtf", "text/rtf"),
    (b"7z\xbc\xaf", "application/x-7z"),
]
IMAGE_END = {"image/jpeg": b"\xff\xd9", "image/png": b"IEND\xaeB`\x82", "image/gif": b"\x00;"}


# ---------- download ----------


def safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .") or "file"
    return name[:180]


def header_filename(response):
    msg = Message()
    msg["content-disposition"] = response.headers.get("Content-Disposition", "")
    name = msg.get_filename()
    if name is None:
        return None
    try:  # requests decodes headers as latin-1; the server can send UTF-8 bytes
        name = name.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return unquote(name)


def sniff(data):
    return next((kind for magic, kind in MAGIC if data.startswith(magic)), None)


def trim_image(kind, data):
    # An image can come back with an HTML page after its bytes; cut at the image's end marker.
    end = IMAGE_END.get(kind)
    if end and b"<html" in data[-65536:].lower():
        cut = data.rfind(end)
        if cut > 0:
            return data[: cut + len(end)]
    return data


def fetch(file_id):
    """Return (file name, bytes, Last-Modified) or raise; a 404 returns None."""
    r = session().get(f"{BASE}download/file.php?id={file_id}", timeout=300)
    time.sleep(DELAY)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    modified = r.headers.get("Last-Modified")
    return header_filename(r), r.content, parsedate_to_datetime(modified).isoformat() if modified else None


def save(db, file_id, result):
    if result is None:
        db.execute("update documents set error = '404', fetched = 0 where id = ?", (file_id,))
        return "missing"
    name, data, modified = result
    if name is None or (is_html_page(data) and not name.lower().endswith((".htm", ".html"))):
        db.execute("update documents set error = ? where id = ?", ("html page, not a file" if name else "no file name", file_id))
        return "error"
    kind = sniff(data)
    if kind in IMAGE_END:
        data = trim_image(kind, data)
    folder = Path(FILES, str(file_id))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name(name)
    path.write_bytes(data)
    db.execute(
        "update documents set filename = ?, path = ?, size = ?, mime = ?, uploaded_at = ?, fetched = 1, error = null, "
        "title = coalesce(title, ?) where id = ?",
        (name, f"{file_id}/{path.name}", len(data), kind, modified, name, file_id),
    )
    return "ok"


def crawl_download(db):
    # Every id up to the highest linked one: an attachment that no visible post links can still be public.
    top = db.execute("select max(id) from documents where post is not null").fetchone()[0] or 0
    known = {r[0] for r in db.execute("select id from documents")}
    db.executemany("insert into documents (id) values (?)", [(i,) for i in range(1, top + 1) if i not in known])
    db.commit()
    # A 404 is final; other errors are tried again on the next run.
    pending = [r[0] for r in db.execute("select id from documents where fetched = 0 and (error is null or error != '404') order by id")]
    print(f"{len(pending)} attachments to fetch (ids 1..{top})", flush=True)
    counts = {"ok": 0, "missing": 0, "error": 0}
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(fetch, i): i for i in pending}
        for n, future in enumerate(as_completed(futures), 1):
            file_id = futures[future]
            try:
                counts[save(db, file_id, future.result())] += 1
            except (requests.RequestException, OSError) as error:
                db.execute("update documents set error = ? where id = ?", (f"{type(error).__name__}: {error}"[:500], file_id))
                counts["error"] += 1
            if n % 100 == 0 or n == len(pending):
                db.commit()
                print(f"download {n}/{len(pending)} {counts}", flush=True)
    db.commit()


# ---------- extract ----------


def pdf_text(data):
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def docx_text(data):
    import docx

    doc = docx.Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    parts += [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    return "\n".join(parts)


def shape_text(shape):
    parts = [shape.text_frame.text] if shape.has_text_frame else []
    if getattr(shape, "has_table", False) and shape.has_table:
        parts += [c.text for row in shape.table.rows for c in row.cells]
    return parts


def pptx_text(data):
    import pptx

    parts = []
    for slide in pptx.Presentation(io.BytesIO(data)).slides:
        parts += [t for shape in slide.shapes for t in shape_text(shape)]
        if slide.has_notes_slide:
            parts.append(slide.notes_slide.notes_text_frame.text)
    return "\n".join(parts)


def xlsx_text(data):
    import openpyxl

    book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines = []
    for sheet in book.worksheets:
        lines.append(f"# {sheet.title}")
        lines += ["\t".join("" if v is None else str(v) for v in row) for row in sheet.iter_rows(values_only=True)]
    return "\n".join(lines)


def plain_text(data):
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def zip_text(data):
    parts = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            parts.append(f"== {info.filename}")
            if info.file_size > MEMBER_LIMIT:
                continue
            try:
                parts.append(extract_bytes(info.filename, archive.read(info)))
            except Exception as error:  # a broken member must not hide the others
                parts.append(f"[extract failed: {type(error).__name__}]")
    return "\n".join(parts)


def rar_text(data):
    """Read rar through the system libarchive (the standard library cannot)."""
    import libarchive

    parts = []
    with libarchive.memory_reader(data) as entries:
        for entry in entries:
            if not entry.isfile:
                continue
            parts.append(f"== {entry.pathname}")
            if entry.size <= MEMBER_LIMIT:
                parts.append(extract_bytes(entry.pathname, b"".join(entry.get_blocks())))
    return "\n".join(parts)


def legacy_office(target, extractor):
    # LibreOffice converts the binary Office formats into the XML formats that we already read.
    def convert(data):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "in")
            with open(source, "wb") as f:
                f.write(data)
            subprocess.run(
                [
                    SOFFICE,
                    f"-env:UserInstallation={Path(tmp, 'profile').as_uri()}",
                    "--headless",
                    "--convert-to",
                    target,
                    "--outdir",
                    tmp,
                    source,
                ],
                check=True,
                capture_output=True,
                timeout=300,
            )
            with open(f"{source}.{target}", "rb") as f:
                return extractor(f.read())

    return convert


EXTRACTORS = {
    "pdf": pdf_text,
    "docx": docx_text,
    "pptx": pptx_text,
    "xlsx": xlsx_text,
    "xlsm": xlsx_text,
    "zip": zip_text,
    "rar": rar_text,
    "doc": legacy_office("docx", docx_text),
    "ppt": legacy_office("pptx", pptx_text),
    "xls": legacy_office("xlsx", xlsx_text),
}


def extract_bytes(name, data):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    func = EXTRACTORS.get(ext) or (plain_text if ext in TEXT_EXT else None)
    return func(data).replace("\x00", "")[:TEXT_LIMIT] if func else ""


def extract_file(args):
    doc_id, path = args
    try:
        with open(os.path.join(FILES, path), "rb") as f:
            return doc_id, extract_bytes(path, f.read()), None
    except Exception as error:  # extraction libraries raise anything
        # The text stays null, so a later run (with LibreOffice or libarchive installed) tries again.
        return doc_id, None, f"extract {type(error).__name__}: {error}"[:500]


def run_extract(db, everything):
    where = "" if everything else "and text is null"
    rows = db.execute(f"select id, path from documents where fetched = 1 and path is not null {where}").fetchall()
    # In CI the old files are in the releases, not on disk.
    todo = [r for r in rows if os.path.exists(os.path.join(FILES, r[1]))]
    print(f"extracting {len(todo)} files", flush=True)
    with ProcessPoolExecutor(max(WORKERS, os.cpu_count() or 1)) as pool:
        for index, (doc_id, content, error) in enumerate(pool.map(extract_file, todo, chunksize=4), 1):
            db.execute("update documents set text = ?, error = ? where id = ?", (content, error, doc_id))
            if index % 50 == 0 or index == len(todo):
                db.commit()
                print(f"extract {index}/{len(todo)}", flush=True)
    db.commit()


# ---------- host ----------

# The attachments of the posts from this day on are the site's own: assets of a release per school year, as dlwms's.
HOST_FROM = "2026-10-01"
# Files to a release: each has a thumbnail asset too, and a release holds at most 1000 assets.
PER_RELEASE = 490


def release_base(posted):
    """'files-2026-2027' for a post of that school year (from 1 October)."""
    y, m = int(posted[:4]), int(posted[5:7])
    y = y if m >= 10 else y - 1
    return f"files-{y}-{y + 1}"


def host(db):
    """Download the attachments of the posts since HOST_FROM that no release has yet, extract their text, render
    their thumbnails (common.thumbnail) and upload both. Then documents.release is the file's release tag and
    documents.thumb 1 when it has a thumbnail. A failed upload leaves release null: the next run tries again."""
    cols = {r[1] for r in db.execute("pragma table_info(documents)")}
    for col, kind in (("release", "text"), ("thumb", "integer not null default 0")):
        if col not in cols:
            db.execute(f"alter table documents add column {col} {kind}")
    rows = db.execute(
        "select d.id, p.posted, d.path from documents d join posts p on p.id = d.post "
        "where p.posted >= ? and d.release is null and (d.error is null or d.error != '404') order by d.id",
        (HOST_FROM,),
    ).fetchall()
    print(f"{len(rows)} attachments to host", flush=True)
    if not rows:
        return
    # In CI the files are not on disk: fetched again, as the first time.
    need = [i for i, _, path in rows if not (path and os.path.exists(os.path.join(FILES, path)))]
    with ThreadPoolExecutor(WORKERS) as pool:
        for file_id, result in zip(need, pool.map(_try_fetch, need)):
            if isinstance(result, Exception):
                db.execute("update documents set error = ? where id = ?", (f"{type(result).__name__}: {result}"[:500], file_id))
            else:
                save(db, file_id, result)
    db.commit()
    used = dict(db.execute("select release, count(*) from documents where release is not null group by release").fetchall())
    by_tag, done = {}, []
    for file_id, posted, _ in rows:
        path = db.execute("select path from documents where id = ? and fetched = 1 and error is null", (file_id,)).fetchone()
        if not path:
            continue
        path = path[0]
        data = Path(FILES, path).read_bytes()
        # A failed extraction (an old .doc without LibreOffice) leaves no text, not an error: an error hides the page.
        text = extract_file((file_id, path))[1]
        base = release_base(posted)
        tag = next(t for n in range(1, 100) if used.get(t := base if n == 1 else f"{base}-{n}", 0) < PER_RELEASE)
        used[tag] = used.get(tag, 0) + 1
        files = by_tag.setdefault(tag, {})
        files[asset_name(path)] = data
        if thumb := thumbnail(path, data):
            files[thumb_asset(path)] = thumb
        done.append((tag, int(bool(thumb)), text, file_id))
    for tag, files in by_tag.items():
        release_assets(tag, tag, "The board's attachments of one school year (documents.py host). An asset's name is a hash of the file's path.")
        upload_assets(tag, files)
    db.executemany("update documents set release = ?, thumb = ?, text = ? where id = ?", done)
    db.commit()
    print(f"hosted {len(done)} of {len(rows)}", flush=True)


def _try_fetch(file_id):
    try:
        return fetch(file_id)
    except (requests.RequestException, OSError) as error:
        return error


# ---------- stats ----------


def show_stats(db):
    q = lambda sql: db.execute(sql).fetchall()
    print("ids, fetched, bytes:", q("select count(*), sum(fetched), sum(size) from documents")[0])
    print("linked from a post, of them fetched:", q("select count(*), sum(fetched) from documents where post is not null")[0])
    print("404 (gone from the board):", q("select count(*) from documents where error = '404'")[0][0])
    print(
        "other errors:",
        q("select error, count(*) from documents where error is not null and error != '404' group by 1 order by 2 desc limit 10"),
    )
    print("types:", q("select mime, count(*) from documents where fetched = 1 group by 1 order by 2 desc"))
    print("with text:", q("select count(*) from documents where text is not null and text != ''")[0][0])
    # Scans and photos give no text: the OCR list.
    no_text = q("select path from documents where fetched = 1 and (text is null or trim(text) = '') order by id")
    Path(FILES).mkdir(exist_ok=True)
    Path(FILES, "no-text.txt").write_text("\n".join(r[0] for r in no_text), encoding="utf-8")
    print(f"no text (need OCR): {len(no_text)}, listed in files/no-text.txt")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    command = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if command in ("sync", "download"):
        crawl_download(db)
    if command in ("sync", "extract"):
        run_extract(db, "--all" in sys.argv)
    if command in ("sync", "stats"):
        show_stats(db)
    if command == "host":
        host(db)


if __name__ == "__main__":
    main()
