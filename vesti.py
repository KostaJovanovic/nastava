# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the news of vesti.mas.bg.ac.rs (WordPress) through its REST API.

Usage: vesti.py sync

Every run lists all posts' ids and `modified` (about 46 small requests) and the categories, and reads the content of
the new or changed posts only: a post whose `modified` changed adds a version and the old one stays; a post no longer
listed is marked gone. The images and files stay on
vesti.mas.bg.ac.rs: the site links them.
"""

import json
import sys
import time
from datetime import datetime, timezone

from common import DELAY, connect, session

# The pretty /wp-json/ route answers 404 there; ?rest_route= is the same API.
API = "https://vesti.mas.bg.ac.rs/?rest_route=/wp/v2/"

SCHEMA = """
create table if not exists vesti (id integer, modified text, date text, date_gmt text, title text, html text, categories text, link text,
	first_seen text, last_seen text, gone integer default 0, primary key (id, modified));
create table if not exists vesti_categories (id integer primary key, name text, parent integer);
"""


def listing(what, fields):
    """Every row of a REST collection, 100 at a time; checks the count against X-WP-Total."""

    rows, page = [], 1
    while True:
        r = session().get(f"{API}{what}&per_page=100&page={page}&_fields={fields}", timeout=120)
        r.raise_for_status()
        rows += r.json()
        if page >= int(r.headers["X-WP-TotalPages"]):
            break
        page += 1
        time.sleep(DELAY)
    # A post published during the run shifts the pages by one: run again.
    if len(rows) != int(r.headers["X-WP-Total"]) or len({x["id"] for x in rows}) != len(rows):
        raise RuntimeError(f"{what}: {len(rows)} rows, the site has {r.headers['X-WP-Total']}")
    return rows


def sync(db):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cats = listing("categories", "id,name,parent")
    db.executemany("insert or replace into vesti_categories values (?,?,?)", [(c["id"], c["name"], c["parent"]) for c in cats])
    # Every post's id and modified (small); the content only of the posts new or changed since the last run.
    posts = listing("posts", "id,modified")
    have = set(db.execute("select id, modified from vesti"))
    need = [p["id"] for p in posts if (p["id"], p["modified"]) not in have]
    for i in range(0, len(need), 100):
        ids = ",".join(map(str, need[i : i + 100]))
        for p in listing(f"posts&include={ids}", "id,date,date_gmt,modified,title,content,categories,link"):
            db.execute(
                "insert into vesti (id, modified, date, date_gmt, title, html, categories, link, first_seen, last_seen) values (?,?,?,?,?,?,?,?,?,?) "
                "on conflict(id, modified) do update set last_seen = excluded.last_seen",
                (
                    p["id"],
                    p["modified"],
                    p["date"],
                    p["date_gmt"],
                    p["title"]["rendered"],
                    p["content"]["rendered"],
                    json.dumps(p["categories"]),
                    p["link"],
                    now,
                    now,
                ),
            )
    db.executemany("update vesti set last_seen = ? where id = ? and modified = ?", [(now, p["id"], p["modified"]) for p in posts])
    # Every version of a post seen in this run is current; a post not seen is gone (it stays in the archive).
    db.execute("update vesti set gone = id not in (select id from vesti where last_seen = ?)", (now,))
    db.commit()
    new = db.execute("select count(*) from vesti where first_seen = ?", (now,)).fetchone()[0]
    gone = db.execute("select count(distinct id) from vesti where gone").fetchone()[0]
    print(f"{len(posts)} posts ({new} new or changed), {len(cats)} categories, {gone} gone", flush=True)


def main():

    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    db.executescript(SCHEMA)
    if (sys.argv[1] if len(sys.argv) > 1 else "sync") != "sync":
        sys.exit(__doc__)
    sync(db)


if __name__ == "__main__":
    main()
