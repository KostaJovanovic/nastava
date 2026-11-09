"""Serve the built site on this PC, with /static/ live from pages/static: python pages/serve.py [port]

An edit to the CSS, JS or icons shows on the next reload, with no build. The pages themselves (templates, the
database) still come from the last build in pages/.build/site. Most are fragments: join() puts them into
shell.html, as the Worker (pages/src/index.js join) does on the live site.
"""
import ctypes
import os
import posixpath
import socket
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from qr import qr_terminal

HERE = Path(__file__).resolve().parent
SITE = HERE / ".build" / "site"
FRAGMENT = '<html lang="sr"><title>'


def join(shell, fragment):
    head, _, main = fragment[fragment.index("<title>"):fragment.rindex("</html>")].partition("<!--/head-->")
    return shell.replace("<title></title>", head, 1).replace("<!--main-->", main, 1)


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # pages/ + /static/... is pages/static/.... Decided on the resolved path: /static/../x is /x, from the build.
        clean = posixpath.normpath(unquote(urlsplit(path).path))
        self.directory = str(HERE if clean.startswith("/static/") else SITE)
        return super().translate_path(path)

    def do_GET(self):
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 15497  # server.bat's PORT, drawn at random
    lan = f"http://{lan_ip()}:{port}"
    if os.name == "nt":  # ANSI colours for the QR in the classic console; Windows Terminal has them already
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    print(qr_terminal(lan))
    print(f"\n  Local:   http://localhost:{port}\n  Network: {lan}  (scan the QR, same Wi-Fi)\n  static:  {HERE / 'static'}\n")
    ThreadingHTTPServer(("", port), partial(Handler, directory=str(SITE))).serve_forever()
