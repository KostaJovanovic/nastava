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

# The contact form on this server: a good message kept (its page from the Referer), a bad one refused; the inbox
# behind $INBOX_PASSWORD, escaping the message.
import os  # noqa: E402
import threading  # noqa: E402
from functools import partial  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402
from urllib.error import HTTPError  # noqa: E402
from urllib.request import Request, urlopen  # noqa: E402

with tempfile.TemporaryDirectory() as t:
    serve.MESSAGES = Path(t) / "poruke.json"
    os.environ["INBOX_PASSWORD"] = "tajna"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(serve.Handler, directory=t))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, data, **headers):
        try:
            with urlopen(Request(base + path, data=data.encode(), headers=headers)) as r:
                return r.status, r.read().decode()
        except HTTPError as e:
            return e.code, e.read().decode()

    ok = post("/kontakt", "email=a%40b.rs&tema=ispravka&poruka=%3Cb%3Ex%3C%2Fb%3E", Accept="application/json", Referer=f"{base}/kontakt/?str=/vest/5/")
    assert ok == (200, '{"ok": true}'), ok
    assert post("/kontakt", "email=nije&tema=ispravka&poruka=x", Accept="application/json")[0] == 400
    assert [(m["page"], m["text"]) for m in json.loads(serve.MESSAGES.read_text(encoding="utf-8"))] == [("/vest/5/", "<b>x</b>")]
    try:
        urlopen(base + "/kontakt/poruke/")
        raise AssertionError("no 401")
    except HTTPError as e:
        assert e.code == 401
    import base64  # noqa: E402

    with urlopen(Request(base + "/kontakt/poruke/", headers={"Authorization": "Basic " + base64.b64encode(b"x:tajna").decode()})) as r:
        page = r.read().decode()
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "<b>x</b>" not in page, page
    server.shutdown()
print("serve_test: ok")
