# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4", "pymupdf", "python-docx", "python-pptx", "openpyxl", "libarchive-c"]
# ///
"""Archive every attachment of nastava.mas.bg.ac.rs.

Usage: documents.py download | extract [--all] | sync | stats
  download  fetch the pending attachments: the ones the posts link, and every id from 1 up to
            the highest linked id that no post links (an attachment can outlive its post link)
  extract   extract text from the downloaded files (no network)
  sync      download + extract

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

from common import DELAY, ROOT, is_html_page, session
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


if __name__ == "__main__":
    main()
