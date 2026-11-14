# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2", "beautifulsoup4==4.15.0"]
# ///
"""Render nastava.db as a static site for GitHub Pages, with its Pagefind search index.

Usage: uv run pages/build.py <nastava.db> <out dir>
       uv run pages/build.py words <nastava.db>   (the word cloud into meta, when a week old: ci/deploy.sh)
Writes <out>/site, most pages as fragments of shell.html (split_page), runs Pagefind (needs Node's npx) into
<out>/site/pagefind, then removes the hidden text Pagefind read from the item pages.
"""

import json
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import date
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "scrapers"))
from translit import fold  # noqa: E402
from sitegen.feeds import write_feeds  # noqa: E402
from sitegen.links import mark_elsewhere  # noqa: E402
from sitegen.load_board import load_items, load_places, load_topics, side_panel  # noqa: E402
from sitegen.load_book import load_book  # noqa: E402
from sitegen.load_sources import load_cent, load_katedre, load_mail, load_vesti  # noqa: E402
from sitegen.load_teachers import load_teachers, write_photos  # noqa: E402
from sitegen.output import (
    LazyTemplate,
    PAGEFIND,
    env,
    katedra_pages,
    pages,
    snav,
    split_page,
    strip_pagefind,
    version_static,
    versioned,
    write,
    write_page,
    write_sitemap,
)  # noqa: E402
from sitegen.render import (
    load_verzije,
    picker,
    render_book,
    render_cent,
    render_home,
    render_item,
    render_katedre,
    render_objave,
    render_places,
    render_teachers,
    render_vesti,
)  # noqa: E402
from sitegen.schedule import render_study_pages  # noqa: E402
from sitegen.stats import archive_stats, cloud, saved_cloud  # noqa: E402
from sitegen.stil import stil_data  # noqa: E402
from sitegen.text import acronyms  # noqa: E402
from sitegen.wiki import archived_wiki, link_groups, link_icons  # noqa: E402
from sitegen import output  # noqa: E402


def load_all(db):
    """Every source's posts as items (and what they hang on): main's start, and words's."""
    place, smerovi, subjects = load_places(db)
    cent_items, cent_pushed = load_cent(db, smerovi, subjects)
    items = load_items(db, place) + cent_items + load_katedre(db, smerovi, subjects) + load_mail(subjects)
    return smerovi, subjects, items, cent_pushed


def words(db_path):
    """The word cloud into meta (words, words_at) when it is missing or WORDS_DAYS old, else nothing: ci/deploy.sh runs
    this before it saves the state, and the builds of the week use it (stats.saved_cloud) instead of making it."""
    db = sqlite3.connect(db_path, timeout=60)
    db.row_factory = sqlite3.Row
    today = date.today()
    if saved_cloud(db, today) is not None:
        print("word cloud: still fresh", flush=True)
        return
    posts = [it for it in load_all(db)[2] if it["kind"] == "post"]
    db.executemany(
        "insert or replace into meta (key, value) values (?, ?)",
        [("words", json.dumps(cloud(posts), ensure_ascii=False)), ("words_at", today.isoformat())],
    )
    db.commit()
    print(f"word cloud: made from {len(posts)} posts", flush=True)


def main(db_path, out, dev_mode=False):
    output.dev = dev = dev_mode
    if dev:  # see Lazy
        env.template_class = LazyTemplate
        env.cache.clear()
        pages.clear()
    site = Path(out) / "site"
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(HERE / "static", site / "static")
    version_static(site / "static")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    smerovi, subjects, items, cent_pushed = load_all(db)
    teachers = load_teachers(db, subjects)
    if teachers:
        write_photos(db, site)
    katedra_pages.clear()
    katedra_pages.update(t["katedra"] for t in teachers if not t["gone"] and not t.get("aside") and t["katedra"])
    # A board author is a teacher when the username is the teacher's e-mail before @. When two rows share it (a
    # teacher who became emeritus), the one still listed comes last and wins.
    teacher_of = {t["username"]: t for t in sorted(teachers, key=lambda t: not t["gone"]) if t["username"]}
    for it in items:
        it["teacher"] = teacher_of.get((it["author"] or "").lower())
        # The shown name: no title or middle initial (those are on the teacher's own page only).
        it["who"] = it["teacher"]["shown"] if it["teacher"] else it["author"]
    topics = load_topics(db, items)
    mark_elsewhere(items)
    env.globals["side"] = side = side_panel(items)
    # The footer's "Provereno" (base.html): when nastava.py last read the board, not when this ran. UTC; site.js shows
    # local time. None (no line in the footer): a database from before the meta table.
    # Not "checked": raspored.html has its own (the schedule pages' last read), which would change the footer there.
    try:
        env.globals["forum_checked"] = (db.execute("SELECT value FROM meta WHERE key = 'forum_synced'").fetchone() or [None])[0]
    except sqlite3.OperationalError:
        env.globals["forum_checked"] = None
    output.site_dir = site
    output.shell = shell = split_page(str(env.get_template("base.html").render()))[0]
    (site / "shell.html").write_text(versioned(shell), encoding="utf-8")
    nav = shell[shell.index('<nav class="snav"') :]
    snav[:] = re.findall(r'<a href="([^"]+)"', nav[: nav.index("</nav>")])
    # join() marks the shell's first <a href="..."> with the link's href: that one must be in .snav.
    assert all(shell.index(f'<a href="{h}"') > shell.index('<nav class="snav"') for h in snav), "a link before .snav"
    # The faculty's subject code often differs from the board's: a subject of the same name the teacher posted in wins.
    posted = defaultdict(dict)
    for it in items:
        if it["teacher"] and it["subj"]:
            posted[it["teacher"]["username"]][fold(it["subj"]["name"])] = it["subj"]
    for t in teachers:
        for s in t["subjects"]:
            s["subj"] = posted[t["username"]].get(fold(s["name"])) or s["subj"]
    for t in teachers:
        if t["gone"]:
            continue
        for s in t["subjects"]:
            if s["subj"] and t not in s["subj"].setdefault("teachers", []):
                s["subj"]["teachers"].append(t)
    titles = defaultdict(list)
    for t in topics:
        if t["subj"]:
            titles[t["subj"]["id"]].append(t["title"])
    for s in subjects.values():
        s["acr"] = acronyms(s["name"], titles[s["id"]])
    book = load_book(db, subjects, teachers)
    render_places(site, topics, smerovi, subjects)
    render_cent(site, subjects)
    write_feeds(site, items, subjects, cent_pushed)
    for it in items:
        write(site / "item" / it["id"] / "index.html", render_item(it), index=False)
    render_teachers(site, teachers, items, book)
    render_katedre(site, db, teachers, subjects, topics)
    render_book(site, book)
    raspored = render_study_pages(site, db)
    links = link_groups(archived_wiki(db))
    (site / "izbor.json").write_text(
        json.dumps(
            dict(
                picker(subjects, book, teachers, items),
                raspored=raspored,
                # The researchers and demonstrators for the header search: [name, page, title].
                istrazivaci=[[t["shown"], t["href"], t["title"]] for t in teachers if t.get("aside")],
                # Linkovi's cards for it too: [name, second line, href, data-domain].
                linkovi=[[n, shown, h, d] for _, group in links for n, h, _, d, shown in group],
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    write(
        site / "statistika" / "index.html",
        env.get_template("stats.html").render(st=archive_stats(items, topics, teachers, saved_cloud(db, date.today()))),
    )
    write(site / "mojipredmeti" / "index.html", env.get_template("mojipredmeti.html").render(), index=False)
    about = env.get_template("o_sajtu.html").render()
    write(site / "o-sajtu" / "index.html", about)
    write(site / "about" / "index.html", about, canonical="/o-sajtu/")  # the English address, same page
    write(site / "stil" / "index.html", env.get_template("stil.html").render(**stil_data()))
    write(site / "link" / "index.html", env.get_template("link.html").render(icons=link_icons(), groups=links))
    days = lambda: load_verzije((HERE.parent / "verzije.md").read_text(encoding="utf-8"))
    page = env.get_template("verzije.html").render(days=days())
    if dev:
        page.fresh["days"] = days
    write(site / "verzije" / "index.html", page)
    vesti = load_vesti(db)
    render_vesti(site, vesti)
    render_objave(site, topics)
    write_page(site / "index.html", render_home(topics, smerovi, side, sum(not t["gone"] and not t.get("aside") for t in teachers), vesti))
    write_page(site / "404.html", env.get_template("error.html").render())
    if dev:
        return
    write_sitemap(site)
    print(
        f"{len(items)} items, {len(topics)} topics, {len(subjects)} subjects, "
        f"{len(smerovi)} smerovi, {len(teachers)} teachers, {len(book)} book subjects, {len(vesti)} vesti",
        flush=True,
    )
    npx = shutil.which("npx") or sys.exit("npx not found: Pagefind needs Node.js")
    subprocess.run([npx, "-y", PAGEFIND, "--site", str(site)], check=True)
    strip_pagefind(site)


if __name__ == "__main__":
    if sys.argv[1:2] == ["words"] and len(sys.argv) == 3:
        sys.exit(words(sys.argv[2]))
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
