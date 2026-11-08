"""Serve the built site on this PC, with /static/ live from pages/static: python pages/serve.py [port]

An edit to the CSS, JS or icons shows on the next reload, with no build. The pages themselves (templates, the
database) still come from the last build in pages/.build/site.
"""
import posixpath
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
SITE = HERE / ".build" / "site"


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # pages/ + /static/... is pages/static/.... Decided on the resolved path: /static/../x is /x, from the build.
        clean = posixpath.normpath(unquote(urlsplit(path).path))
        self.directory = str(HERE if clean.startswith("/static/") else SITE)
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    print(f"http://localhost:{port}  (static: {HERE / 'static'})")
    ThreadingHTTPServer(("", port), partial(Handler, directory=str(SITE))).serve_forever()
