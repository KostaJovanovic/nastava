# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2", "beautifulsoup4==4.15.0", "pillow==12.1.1", "pymupdf"]
# ///
"""The site on this PC: uv run pages/serve.py [port] [--built]

Dev mode (the default): no build. build.py reads nastava.db in dev mode (main(dev=True), ~15 s) and keeps each page's
template and data; a page is rendered when asked for, from the templates as they are then, so an edit to a template,
the CSS, the JS or the icons shows on the next reload. A change to nastava.db or build.py restarts the server (a
child process: the parent watches them). /static/ is pages/static; the small files the build writes (izbor.json,
novo.json, the feeds, the photos) are in pages/.build/dev-<port>; the text search (Pagefind) is the last real build's.
build.py's devcheck.py checks that dev mode renders what a build writes.

--built: the last build in pages/.build/site, as deployed. Most pages are fragments there: join() puts them into
shell.html, as the Worker (pages/src/index.js join) does on the live site.
"""

import ctypes
import json
import os
import posixpath
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from qr import qr_terminal

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scrapers"))  # common.py (local_file)
SITE = HERE / ".build" / "site"
# The notification subscriptions made on this server (do_POST), kept across restarts.
PUSH_SUBS, PUSH_LOCK = HERE / ".build" / "push-subs.json", threading.Lock()
DEV = None  # dev mode's build.py out dir, .build/dev-<port> (set in __main__): its site/ has the small files, no pages
DB = HERE.parent / "nastava.db"
FRAGMENT = '<html lang="sr"><title>'
# What dev mode's data comes from: a change restarts it. build.py imports the three scrapers (and common.py, translit.py) and wiki_tidy.py. The database's -wal: a
# sync writes there first. Not the icons: their link's ?v= hash goes stale after an edit, but every reply here is
# no-cache (end_headers), so a reload fetches the new file anyway. Not verzije.md: /verzije/ reads it at each render
# (build.py Lazy.fresh). The teachers' files of history, photos and biographies: build.py reads them at the start.
WATCH = [
    HERE / "build.py",
    HERE / "wiki_tidy.py",
    *(
        HERE.parent / f
        for f in (
            "scrapers/studije.py",
            "scrapers/nastavnici.py",
            "scrapers/mail.py",
            "scrapers/common.py",
            "scrapers/translit.py",
            "nastava.db",
            "nastava.db-wal",
            "data/nastavnici-istorija.jsonl",
            "data/nastavnici-foto.jsonl",
            "data/nastavnici-biografije.jsonl",
            "data/nastavnici-sazetak.jsonl",
        )
    ),
]
build = None  # dev mode: the build module, its pages loaded (dev())


INLINE = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif"}
FILES, MAIL, WAYBACK = HERE.parent / "files", HERE.parent / "mail", HERE.parent / "work" / "wayback"
assets = None  # {(tag kind, asset name): file on disk}, made at the first /files/ request (file_assets)


def file_assets():
    """Every file the local build may link, by its release's kind ("files" for files-<year>, "mail", "stari") and its
    asset name: the board's attachments (files/index.sqlite -> files/blobs/, else files/<id>/<name>), mail/'s files,
    the old sites' saved files (work/wayback/files.jsonl). A thumbnail's asset (thumb_asset) maps to its file too,
    with "#thumb" after the kind."""
    import sqlite3
    from common import asset_name, thumb_asset

    out = {}

    def add(kind, path, file):
        out[(kind, asset_name(path))] = file
        out[(kind + "#thumb", thumb_asset(path))] = file

    if (FILES / "index.sqlite").exists():
        db = sqlite3.connect(FILES / "index.sqlite")
        for path, blob in db.execute("select path, blob from files"):
            add("files", path, FILES / "blobs" / blob)
        db.close()
    for d in FILES.iterdir() if FILES.exists() else ():
        if d.name.isdigit():  # the old place, files/<id>/<name>, of an attachment the index has no copy of
            for f in d.iterdir():
                out.setdefault(("files", asset_name(f"{d.name}/{f.name}")), f)
    for f in MAIL.rglob("*") if MAIL.exists() else ():
        if f.is_file() and f.parent != MAIL and f.name not in ("post.json", "material.json"):
            add("mail", f.relative_to(MAIL).as_posix(), f)
    if (WAYBACK / "files.jsonl").exists():
        for line in (WAYBACK / "files.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("ok"):
                add("stari", r["key"], WAYBACK / r["path"])
    return out


def local_file(path):
    """/files/<tag>/<asset>/<name> -> (bytes, name) from this PC, or None. A thumbnail (<name> thumb.jpg) is made from
    its file (common.thumbnail)."""
    global assets
    from common import thumbnail

    parts = path.removeprefix("/files/").split("/")
    if len(parts) != 3:
        return None
    tag, asset, name = parts[0], parts[1], unquote(parts[2])
    kind = "files" if tag.startswith("files-") else "stari" if tag.startswith("stari-") else tag
    if assets is None:
        assets = file_assets()
    if file := assets.get((kind, asset)):
        return (file.read_bytes(), name) if file.exists() else None
    if name == "thumb.jpg" and (file := assets.get((kind + "#thumb", asset))) and file.exists():
        thumb = thumbnail(file.name, file.read_bytes())
        return (thumb, name) if thumb else None
    return None


def join(shell, fragment):
    head, _, main = fragment[fragment.index("<title>") : fragment.rindex("</html>")].partition("<!--/head-->")
    if snav := re.search(r'<meta name="snav" content="([^"]+)">', head):
        a = f'<a href="{snav[1]}"'
        shell = shell.replace(a, a + ' aria-current="page"', 1)
    return shell.replace("<title></title>", head, 1).replace("<!--main-->", main, 1)


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # pages/ + /static/... is pages/static/.... Decided on the resolved path: /static/../x is /x, from the build.
        # Dev mode: Pagefind's index from the last build, the rest from dev mode's out dir.
        clean = posixpath.normpath(unquote(urlsplit(path).path))
        self.directory = str(
            HERE if clean.startswith("/static/") else SITE if not build or clean.startswith("/pagefind/") else DEV / "site"
        )
        return super().translate_path(path)

    def send_text(self, text):
        body = text.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, code, page):
        body = page.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_POST(self):
        """/push, as the Worker's (pages/src/index.js push): the app's and the browsers' subscriptions, kept in
        PUSH_SUBS so /push/test can notify them; an empty subject list drops one. Not checked as the Worker does."""
        if self.path != "/push":
            return self.send_error(404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            endpoint = f"fcm:{body['fcm']}" if "fcm" in body else body["endpoint"]
        except (ValueError, KeyError, TypeError):
            return self.send_error(400)
        with PUSH_LOCK:
            subs = json.loads(PUSH_SUBS.read_text()) if PUSH_SUBS.exists() else {}
            if body.get("s"):
                keys = body.get("keys") or {}
                subs[endpoint] = {"endpoint": endpoint, "s": body["s"], "t": body.get("t") or {}, "k": keys.get("p256dh"), "a": keys.get("auth")}
            else:
                subs.pop(endpoint, None)
            PUSH_SUBS.write_text(json.dumps(subs, indent=1))
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        # A test notification to each subscription above, through ci/push.py (its keys: push-secret.json and
        # fcm-secret.json in the repo); the page says what happened to each.
        if self.path == "/push/test":
            with PUSH_LOCK:
                subs = list(json.loads(PUSH_SUBS.read_text()).values()) if PUSH_SUBS.exists() else []
            if not subs:
                return self.send_text("No subscriptions yet: turn the bell on in the app or a browser on this server.")
            listed = PUSH_SUBS.with_name("push-test.json")
            listed.write_text(json.dumps(subs))
            run = subprocess.run(["uv", "run", "-q", str(HERE.parent / "ci" / "push.py"), "test", str(listed)],
                                 capture_output=True, text=True, encoding="utf-8", cwd=HERE.parent)
            # One the push service no longer has (push.py says "gone"): dropped here, as the Worker would.
            with PUSH_LOCK:
                kept = json.loads(PUSH_SUBS.read_text()) if PUSH_SUBS.exists() else {}
                PUSH_SUBS.write_text(json.dumps({e: s for e, s in kept.items() if f"{e[-12:]}: gone" not in run.stdout}, indent=1))
            return self.send_text(run.stdout + run.stderr)
        # The files the local build links (/files/<tag>/<asset>/<name>), from this PC's copies (local_file); the
        # public site links the originals instead (docs/PLAN-pravno.md 1).
        if self.path.startswith("/files/"):
            found = local_file(urlsplit(self.path).path)
            if not found:
                return self.send_error(404)
            body, name = found
            ext = name.rsplit(".", 1)[-1].lower()
            self.send_response(200)
            # As the Worker served them: a PDF or an image inline, anything else a download.
            self.send_header("Content-Type", INLINE.get(ext, "application/octet-stream"))
            self.send_header("Content-Disposition", f"{'inline' if ext in INLINE else 'attachment'}; filename*=UTF-8''{quote(name)}")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        if build:
            url = urlsplit(self.path)
            path = unquote(url.path)
            if not path.endswith("/") and path + "/" in build.output.pages:  # as GitHub Pages: /x is /x/
                self.send_response(301)
                self.send_header("Location", url.path + "/" + (f"?{url.query}" if url.query else ""))
                return self.end_headers()
            if page := build.output.pages.get(path):
                # The side panel link aria-current in the first frame, as join() marks it from the build's <meta>.
                page = str(page)
                if h := build.output.snav_href(path, build.output.snav):
                    a = f'<a href="{h}"'
                    page = page.replace(a, a + ' aria-current="page"', 1)
                return self.send_page(200, page)
            return super().do_GET()
        file = Path(self.translate_path(self.path))
        if file.is_dir() and urlsplit(self.path).path.endswith("/"):
            file = file / "index.html"
        page = file.read_text(encoding="utf-8") if file.suffix == ".html" and file.is_file() else ""
        if not page.startswith(FRAGMENT):
            return super().do_GET()
        body = join((SITE / "shell.html").read_text(encoding="utf-8"), page).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        # A missing page gets the site's 404.html, as on GitHub Pages.
        if build and code == 404:
            return self.send_page(404, str(build.output.pages["/404.html"]))
        page = SITE / "404.html"
        if code != 404 or not page.is_file():
            return super().send_error(code, message, explain)
        body = page.read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def lan_ip():
    """The address a phone on the same Wi-Fi would use: the source of the default route (connect() sends nothing).
    ipconfig's first or last IPv4 line can be a link-local or VirtualBox adapter instead."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


if __name__ == "__main__":
    assert (
        join("<title></title><b><!--main--></b>", f"{FRAGMENT}T</title><meta><!--/head-->$& M</html>")
        == "<title>T</title><meta><b>$& M</b>"
    )
    assert join(
        '<title></title><a href="/x/">X</a><a href="/x/"><!--main-->',
        f'{FRAGMENT}T</title><meta name="snav" content="/x/"><!--/head-->M</html>',
    ) == ('<title>T</title><meta name="snav" content="/x/"><a href="/x/" aria-current="page">X</a><a href="/x/">M')
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 15497  # server.bat's PORT, drawn at random
    DEV = HERE / ".build" / f"dev-{port}"  # one per server: two sharing it crash each other's restarts (rmtree vs copytree)
    if "--child" in sys.argv:
        # Dev mode's server: loads the data, then serves until the parent stops it.
        t = time.time()
        sys.path.insert(0, str(HERE))
        import build as _build

        _build.main(str(DB), str(DEV), dev_mode=True)
        build = _build
        print(f"  ready: {len(build.output.pages)} pages in {time.time() - t:.0f} s", flush=True)
        ThreadingHTTPServer(("", port), partial(Handler, directory=str(DEV / "site"))).serve_forever()
    lan = f"http://{lan_ip()}:{port}"
    if os.name == "nt":  # ANSI colours for the QR in the classic console; Windows Terminal has them already
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    print(qr_terminal(lan))
    print(f"\n  Local:   http://localhost:{port}\n  Network: {lan}  (scan the QR, same Wi-Fi)\n  static:  {HERE / 'static'}\n")
    if "--open" in sys.argv:  # server.bat: the browser once the site answers (dev mode loads for a while first)

        def open_when_up():
            while True:
                try:
                    socket.create_connection(("localhost", port), timeout=1).close()
                    return webbrowser.open(f"http://localhost:{port}")
                except OSError:
                    time.sleep(0.5)

        threading.Thread(target=open_when_up, daemon=True).start()
    if "--built" in sys.argv:
        ThreadingHTTPServer(("", port), partial(Handler, directory=str(SITE))).serve_forever()
    # Dev mode: the server is a child, started again whenever its data changes (WATCH), once the change has settled
    # (a sync writes the database for a while).
    stamp = lambda: [f.stat().st_mtime if f.exists() else 0 for f in WATCH]
    child, seen = None, None
    try:
        while True:
            now = stamp()
            if now != seen:
                if child:  # a change, not the first start: let it settle first
                    time.sleep(2)
                    if stamp() != now:
                        continue
                if child:
                    print("  " + ", ".join(f.name for f, a, b in zip(WATCH, seen, now) if a != b) + " changed: restarting", flush=True)
                    child.terminate()
                    child.wait()
                else:
                    print("  loading the data (dev mode, no build)...", flush=True)
                seen = now
                child = subprocess.Popen([sys.executable, __file__, str(port), "--child"])
            time.sleep(1)
    finally:
        if child:
            child.terminate()
