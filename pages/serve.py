# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2", "beautifulsoup4==4.15.0"]
# ///
"""The site on this PC: uv run pages/serve.py [port] [--built]

Dev mode (the default): no build. build.py reads nastava.db in dev mode (main(dev=True), ~15 s) and keeps each page's
template and data; a page is rendered when asked for, from the templates as they are then, so an edit to a template,
the CSS or the JS shows on the next reload. A change to nastava.db, build.py or the icons restarts the server (a
child process: the parent watches them). /static/ is pages/static; the small files the build writes (izbor.json,
novo.json, the feeds, the photos) are in pages/.build/dev; the text search (Pagefind) is the last real build's.
build.py's devcheck.py checks that dev mode renders what a build writes.

--built: the last build in pages/.build/site, as deployed. Most pages are fragments there: join() puts them into
shell.html, as the Worker (pages/src/index.js join) does on the live site.
"""
import ctypes
import os
import posixpath
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from qr import qr_terminal

HERE = Path(__file__).resolve().parent
SITE = HERE / ".build" / "site"
DEV = HERE / ".build" / "dev"  # dev mode's build.py out dir: its site/ has the small files, no pages
DB = HERE.parent / "nastava.db"
FRAGMENT = '<html lang="sr"><title>'
# What dev mode's data comes from: a change restarts it. build.py imports the three modules; the icons are in the
# pages (build.py sprite). The database's -wal: a sync writes there first.
WATCH = [HERE / "build.py", HERE / "static" / "icons.svg", *(HERE.parent / f for f in (
    "studije.py", "nastavnici.py", "mail.py", "nastava.db", "nastava.db-wal", "verzije.md"))]
build = None  # dev mode: the build module, its pages loaded (dev())


def join(shell, fragment):
    head, _, main = fragment[fragment.index("<title>"):fragment.rindex("</html>")].partition("<!--/head-->")
    return shell.replace("<title></title>", head, 1).replace("<!--main-->", main, 1)


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # pages/ + /static/... is pages/static/.... Decided on the resolved path: /static/../x is /x, from the build.
        # Dev mode: Pagefind's index from the last build, the rest from dev mode's out dir.
        clean = posixpath.normpath(unquote(urlsplit(path).path))
        self.directory = str(HERE if clean.startswith("/static/") else
                             SITE if not build or clean.startswith("/pagefind/") else DEV / "site")
        return super().translate_path(path)

    def send_page(self, code, page):
        body = page.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        if build:
            url = urlsplit(self.path)
            path = unquote(url.path)
            if not path.endswith("/") and path + "/" in build.pages:  # as GitHub Pages: /x is /x/
                self.send_response(301)
                self.send_header("Location", url.path + "/" + (f"?{url.query}" if url.query else ""))
                return self.end_headers()
            if page := build.pages.get(path):
                # shortcut: no aria-current on the side panel link in the first frame (site.js adds it), unlike
                # join(); mark it here too once build.py's snav_href is committed.
                return self.send_page(200, str(page))
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
            return self.send_page(404, str(build.pages["/404.html"]))
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
    assert join("<title></title><b><!--main--></b>", f"{FRAGMENT}T</title><meta><!--/head-->$& M</html>") == "<title>T</title><meta><b>$& M</b>"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 15497  # server.bat's PORT, drawn at random
    if "--child" in sys.argv:
        # Dev mode's server: loads the data, then serves until the parent stops it.
        t = time.time()
        sys.path.insert(0, str(HERE))
        import build as _build
        _build.main(str(DB), str(DEV), dev_mode=True)
        build = _build
        print(f"  ready: {len(build.pages)} pages in {time.time() - t:.0f} s", flush=True)
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
