# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf"]
# ///
"""pages/serve.py's /files/ from this PC's copies (local_file), one file of each kind, no network:
uv run test/serve_test.py"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pages"))
sys.path.insert(0, str(ROOT / "scrapers"))
import serve  # noqa: E402
from common import asset_name, thumb_asset  # noqa: E402

with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    serve.FILES, serve.MAIL, serve.WAYBACK = t / "files", t / "mail", t / "wb"
    # A board attachment through index.sqlite, and one at its old place files/<id>/<name>.
    (t / "files" / "blobs" / "ab").mkdir(parents=True)
    (t / "files" / "blobs" / "ab" / "ab1.pdf").write_bytes(b"board")
    with sqlite3.connect(t / "files" / "index.sqlite") as db:
        db.execute("create table files (path text primary key, sha256 text, size integer, blob text)")
        db.execute("insert into files values ('7/a b.pdf', 'ab1', 5, 'ab/ab1.pdf')")
    db.close()
    (t / "files" / "8").mkdir()
    (t / "files" / "8" / "c.doc").write_bytes(b"old")
    (t / "mail" / "2026-01-01-aaaaaaaa").mkdir(parents=True)
    (t / "mail" / "2026-01-01-aaaaaaaa" / "r.pdf").write_bytes(b"mail")
    (t / "mail" / "2026-01-01-aaaaaaaa" / "post.json").write_text("{}")
    (t / "wb" / "files" / "www").mkdir(parents=True)
    (t / "wb" / "files" / "www" / "x.pdf").write_bytes(b"stari")
    (t / "wb" / "files.jsonl").write_text(json.dumps(dict(key="www/x.pdf", ok=True, path="files/www/x.pdf")) + "\n")
    got = lambda p: (serve.local_file(p) or (None,))[0]
    assert got(f"/files/files-2026-2027/{asset_name('7/a b.pdf')}/a%20b.pdf") == b"board"
    assert got(f"/files/files-2026-2027-2/{asset_name('8/c.doc')}/c.doc") == b"old"
    assert got(f"/files/mail/{asset_name('2026-01-01-aaaaaaaa/r.pdf')}/r.pdf") == b"mail"
    assert got(f"/files/stari-www/{asset_name('www/x.pdf')}/x.pdf") == b"stari"
    # Not a PDF inside: no thumbnail, a 404, not an error.
    assert serve.local_file(f"/files/mail/{thumb_asset('2026-01-01-aaaaaaaa/r.pdf')}/thumb.jpg") is None
    assert serve.local_file("/files/mail/x.pdf") is None and serve.local_file(f"/files/mail/{asset_name('nope')}/n.pdf") is None
print("serve_test: ok")
