# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""Run the browser-console exports for you: opens Edge (its own profile, so a sign-in stays), waits while you sign in,
then runs the export in the page and saves what it downloads in Downloads/nastava-<what>-<date>/.

Usage: fetch.py teams                     teams-export.js and teams-files.js, then teams.py add on them
       fetch.py moodle <course url> …     moodle-export.js on each course page (enrol first)

The sign-in is yours, typed in the window; the script never sees or keeps a password. The profile (cookies) is in
~/.nastava-browser, outside the repository.
"""

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PROFILE = Path.home() / ".nastava-browser"
WAIT = 15 * 60 * 1000  # for the sign-in: 15 minutes


def js(name):
    """A console script as an expression whose promise evaluate() waits for."""
    return (ROOT / "tools" / name).read_text(encoding="utf-8").strip().rstrip(";")


def run(page, script, out):
    """Run a console script in the page and save every file it downloads into out."""
    downloads = []
    on_download = lambda d: downloads.append(d)  # a plain function: Playwright can't wrap list.append

    # Only the script's own messages (run by evaluate: no page file of its own), not the page's noise.
    def on_console(m):
        url = (m.location or {}).get("url") or ""
        if not url or "playwright" in url or "__puppeteer" in url:
            print(" ", m.text, flush=True)

    page.on("download", on_download)
    page.on("console", on_console)
    try:
        for attempt in range(3):
            try:
                page.evaluate(js(script))
                break
            except Error as e:
                # Teams reloads itself now and then, which ends a script running in it: start it again.
                if attempt == 2 or not re.search(r"context was destroyed|navigat|Target.*closed", str(e)):
                    raise
                print(f"  the page reloaded ({str(e).splitlines()[0]}); starting {script} again", flush=True)
                page.wait_for_load_state("load")
                page.wait_for_timeout(10000)
        page.wait_for_timeout(2000)  # the last click's download event
    finally:
        page.remove_listener("download", on_download)
        page.remove_listener("console", on_console)
    saved = []
    for d in downloads:
        d.save_as(out / d.suggested_filename)
        saved.append(out / d.suggested_filename)
        print(f"  saved {d.suggested_filename}")
    return saved


def teams(page, out):
    page.goto("https://teams.microsoft.com/v2/")
    print("Sign in to Teams in the window (as a student of the classes); the export starts once Teams has loaded.")
    # Signed in: the page holds a token for Teams' own chat service, what teams-export.js reads.
    page.wait_for_function(
        """() => [localStorage, sessionStorage].some(s => Object.keys(s).some(k => {
             try { const v = JSON.parse(s.getItem(k)); return v && v.secret && /chatsvcagg/.test(v.target || ''); } catch { return false; }
           }))""",
        timeout=WAIT,
        polling=2000,
    )
    page.wait_for_timeout(5000)  # the other tokens (Graph's, for the files) come a moment later
    export = [p for p in run(page, "teams/teams-export.js", out) if p.suffix == ".json"]
    run(page, "teams/teams-files.js", out)
    if export:
        print("\nteams.py add:")
        subprocess.run(["uv", "run", str(ROOT / "scrapers" / "teams.py"), "add", str(export[0]), str(out)], cwd=ROOT,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})  # the classes' names: cp1252 can't print š
        print("\nNext: read the students' replies in mail/ for names it missed, then mail.py upload and commit mail/ (README).")


def moodle(page, out, urls):
    for url in urls:
        page.goto(url)
        if "/course/view.php" not in page.url:
            print(f"Sign in to Moodle in the window; the export starts on the course page ({url}).")
        page.wait_for_url(re.compile(r"/course/view\.php\?id=\d+"), timeout=WAIT)
        page.wait_for_load_state("networkidle")
        run(page, "moodle/moodle-export.js", out)
    print(f"\nNext: moodle.py add <zip> /predmet/<smer>/<subject>/ <teacher's username> [week 1's Monday] (README).")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # the classes' names (š, ž), not cp1252's �
    what =sys.argv[1] if len(sys.argv) > 1 else ""
    if what not in ("teams", "moodle") or (what == "moodle" and len(sys.argv) < 3):
        sys.exit(__doc__)
    out = Path.home() / "Downloads" / f"nastava-{what}-{date.today()}"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, channel="msedge", headless=False, accept_downloads=True,
                                                   no_viewport=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            teams(page, out) if what == "teams" else moodle(page, out, sys.argv[2:])
        finally:
            ctx.close()
    print(f"Files: {out}")
