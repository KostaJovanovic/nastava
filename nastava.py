# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive every post of nastava.mas.bg.ac.rs (phpBB, public, no login).

Usage: nastava.py sync | stats
  sync    walk the forum tree, then fetch the topics that changed (the first run fetches all)
  stats   compare the counts the board shows with the stored rows; exit 1 when posts are missing

Each forum page lists its subforums with their topic and post counts and last post id.
A forum is walked only when these differ from the last complete walk, and a topic is
fetched only when its last post id changed. So the first run and the daily run are the
same code, and the counts double as the completeness check.
"""

import json
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://nastava.mas.bg.ac.rs/nastava/"
DELAY = float(os.getenv("DELAY", "0.5"))
WORKERS = int(os.getenv("WORKERS", "2"))
DB = os.getenv("DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "nastava.db"))
LOCAL = threading.local()
# A logged run (ci/deploy.sh): the folder its log is gathered in, for ci/runs.py.
RUN_DIR = os.getenv("RUN_DIR")
_LOG = threading.Lock()
# A topic to fetch: never fetched, or its last post changed since.
PENDING = "(done_last_post is null or done_last_post != coalesce(last_post, -1))"

SCHEMA = """
create table if not exists forums (
	id integer primary key,
	parent integer,
	name text not null,
	topics integer, posts integer, last_post integer,  -- as the parent page shows them now
	done text,                                         -- "topics/posts/last_post" at the last complete walk
	own_topics integer                                 -- "N topics" on the forum's own page
);
create table if not exists topics (
	id integer primary key,
	forum integer,
	title text,
	replies integer,
	last_post integer,
	done_last_post integer,
	gone integer not null default 0
);
create table if not exists posts (
	id integer primary key,
	topic integer not null,
	forum integer,
	subject text,
	title text,
	author text,
	date text,      -- the board's local time, "07.11.2026. 15:42"
	posted text,    -- ISO UTC
	content text,
	html text,
	gone integer not null default 0
);
create table if not exists documents (
	id integer primary key,  -- the phpBB attachment id
	post integer,            -- the post that links it (null: found by the id sweep)
	title text,
	filename text, path text, size integer, mime text, uploaded_at text,
	text text, fetched integer not null default 0, error text
);
create table if not exists meta (key text primary key, value text);
"""


def session():
    # One session per thread; retries with backoff on server errors and timeouts.
    if not hasattr(LOCAL, "s"):
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0 (personal archive)"
        retry = Retry(total=6, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        LOCAL.s = instrument(s)
    return LOCAL.s


def instrument(s):
    """In a logged run (RUN_DIR), every request of the session is a line of RUN_DIR/requests.jsonl for ci/runs.py:
    the scraper, host, status or error, seconds, bytes, retries, and whether the server sends ETag / Last-Modified (so
    a request could ask for the page only if it changed). Returns s."""
    if not RUN_DIR:
        return s
    scraper = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    request = s.request

    def logged(method, url, *a, **kw):
        t = time.monotonic()
        rec = dict(scraper=scraper, method=method, url=url, host=urlsplit(url).hostname)
        try:
            r = request(method, url, *a, **kw)
        except requests.RequestException as e:
            rec.update(status=type(e).__name__, s=round(time.monotonic() - t, 3))
            raise
        else:
            h = r.headers
            # A streamed body (a file katedre.py does not download) by its header: reading it would download it.
            size = int(h.get("Content-Length") or 0) if kw.get("stream") else len(r.content)
            history = getattr(getattr(r.raw, "retries", None), "history", None) or ()
            rec.update(
                status=r.status_code,
                s=round(time.monotonic() - t, 3),
                bytes=size,
                retries=len(history),
                etag="ETag" in h,
                modified="Last-Modified" in h,
            )
            return r
        finally:
            with _LOG, open(os.path.join(RUN_DIR, "requests.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    s.request = logged
    return s


def get(path):
    """Return the page soup, or None for a 404 (a topic deleted between the list and the fetch)."""
    r = session().get(BASE + path, timeout=60)
    time.sleep(DELAY)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def text(node):
    return " ".join(node.get_text(" ").split()) if node else ""


def num(node):
    match = re.search(r"\d+", text(node))
    return int(match.group()) if match else 0


def param(href, name):
    match = re.search(rf"[?&;]{name}=(\d+)", href or "")
    return int(match.group(1)) if match else None


def next_page(soup):
    link = soup.find("a", rel="next")
    return re.sub(r"&sid=[0-9a-f]+", "", link["href"].replace("./", "")) if link else None


def read_rows(soup):
    """Yield ('forum' | 'topic', id, title, count fields, last post id) for each row of a list page."""
    for row in soup.select("li.row"):
        forum = row.select_one("a.forumtitle")
        topic = row.select_one("a.topictitle")
        last = row.select_one('dd.lastpost a[href*="viewtopic.php?p="]')
        last_post = param(last["href"], "p") if last else None
        if forum:
            yield (
                "forum",
                param(forum["href"], "f"),
                text(forum),
                num(row.select_one("dd.topics")),
                num(row.select_one("dd.posts")),
                last_post,
            )
        elif topic:
            yield "topic", param(topic["href"], "t"), text(topic), None, num(row.select_one("dd.posts")), last_post


def walk_pages(path):
    """Yield the soup of every page of one list."""
    while path:
        soup = get(path)
        if soup is None:
            return
        yield soup
        path = next_page(soup)


# ---------- forum tree ----------


def walk_forum(db, forum_id, path):
    """Read all pages of one forum; register changed subforums and topics. Return the changed subforum ids."""
    changed, own, listed = [], None, []
    for soup in walk_pages(path):
        if own is None:
            match = re.search(r"(\d+)\s+topics?", text(soup.select_one("div.action-bar.bar-top div.pagination")))
            own = int(match.group(1)) if match else 0
        for kind, id_, title, topics, posts, last_post in read_rows(soup):
            if kind == "forum":
                shown = f"{topics}/{posts}/{last_post}"
                db.execute(
                    "insert into forums (id, parent, name, topics, posts, last_post) values (?,?,?,?,?,?) "
                    "on conflict(id) do update set parent=excluded.parent, name=excluded.name, topics=excluded.topics, posts=excluded.posts, last_post=excluded.last_post",
                    (id_, forum_id, title, topics, posts, last_post),
                )
                done = db.execute("select done from forums where id = ?", (id_,)).fetchone()[0]
                if done != shown and (topics or posts):
                    changed.append(id_)
            else:
                listed.append(id_)
                # A global announcement shows in every forum; the topic page sets its real forum.
                # A topic back after it was gone (restored by a moderator) is fetched again: its posts are still marked gone.
                db.execute(
                    "insert into topics (id, forum, title, replies, last_post) values (?,?,?,?,?) "
                    "on conflict(id) do update set title=excluded.title, replies=excluded.replies, last_post=excluded.last_post, "
                    "done_last_post=case when topics.gone then null else topics.done_last_post end, gone=0",
                    (id_, forum_id, title, posts, last_post),
                )
    if forum_id is not None:
        db.execute("update forums set own_topics = ? where id = ?", (own or 0, forum_id))
        # A topic the list no longer shows was deleted or moved: fetch it again, its page tells which (gone or new forum).
        if own is not None:
            db.execute(
                f"update topics set done_last_post = null where forum = ? and gone = 0 and id not in ({','.join('?' * len(listed))})",
                (forum_id, *listed),
            )
    db.commit()
    return changed


def crawl_tree(db):
    queue = walk_forum(db, None, "index.php")
    # A run stopped mid-walk leaves subforums that its parent's page listed but no one walked.
    # Also a forum whose stored topics differ from its page (stats): a walk finds the deleted or moved ones.
    queue += [
        r[0]
        for r in db.execute(
            "select id from forums where (topics or posts) and "
            "(done is not (topics || '/' || posts || '/' || last_post) or own_topics != "
            "(select count(*) from topics t where t.forum = forums.id and t.gone = 0))"
        )
        if r[0] not in queue
    ]
    walked = 0
    while queue:
        forum_id = queue.pop()
        queue += walk_forum(db, forum_id, f"viewforum.php?f={forum_id}")
        # Fetch this forum's topics now, so the posts fill in as the walk goes, not only at its end.
        fetch_topics(db, quiet=True)
        # Mark the walk complete only after its topics are registered; a crash walks it again.
        db.execute("update forums set done = topics || '/' || posts || '/' || last_post where id = ?", (forum_id,))
        db.commit()
        walked += 1
        if walked % 25 == 0:
            print(f"forums walked {walked}, queued {len(queue)}", flush=True)
    print(f"tree done: {walked} forums walked", flush=True)


# ---------- topics ----------


def panel_text(node):
    # One line per table row keeps the cells of a row together for search and snippets.
    node = BeautifulSoup(str(node), "html.parser")
    for row in node.find_all("tr"):
        row.replace_with("\n" + " | ".join(text(c) for c in row.find_all(["td", "th"])) + "\n")
    for br in node.find_all("br"):
        br.replace_with("\n")
    lines = (" ".join(line.split()) for line in node.get_text("\n").splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def read_topic(topic_id):
    """Return (forum id, forum name, posts) of one topic, or None when the topic is gone."""
    forum = name = None
    posts = []
    for soup in walk_pages(f"viewtopic.php?t={topic_id}"):
        crumb = soup.select(".crumb[data-forum-id]")
        if crumb:
            forum, name = int(crumb[-1]["data-forum-id"]), text(crumb[-1])
        for post in soup.select("div.post[id^=p]"):
            content = post.select_one("div.content")
            if content is None:
                continue
            files = post.select_one("dl.attachbox")
            when = post.select_one("p.author time")
            html = str(content) + (str(files) if files else "")
            posts.append(
                {
                    "id": int(post["id"][1:]),
                    "title": text(post.select_one("h3 a")),
                    "author": text(post.select_one("p.author .username, p.author .username-coloured")),
                    "date": text(when),
                    "posted": when["datetime"] if when else None,
                    "content": panel_text(content),
                    "html": html,
                    "files": [
                        (int(i), text(a)) for a in post.select('a[href*="download/file.php?id="]') for i in [param(a["href"], "id")] if i
                    ],
                    "images": {
                        int(i)
                        for i in re.findall(
                            r"download/file\.php\?id=(\d+)", " ".join(img.get("src", "") for img in content.find_all("img"))
                        )
                    },
                }
            )
    if forum and not posts:
        # The page is there but no post parses: a markup change, not a deleted topic. Not stored, tried again next run.
        raise ValueError(f"topic {topic_id}: no posts parsed")
    return (forum, name, posts) if posts or forum else None


def store_topic(db, topic_id, last_post, result):
    if result is None:
        db.execute("update topics set gone = 1, done_last_post = coalesce(last_post, -1) where id = ?", (topic_id,))
        db.execute("update posts set gone = 1 where topic = ?", (topic_id,))
        return 0
    forum, name, posts = result
    for p in posts:
        db.execute(
            "insert into posts (id, topic, forum, subject, title, author, date, posted, content, html) values (?,?,?,?,?,?,?,?,?,?) "
            "on conflict(id) do update set topic=excluded.topic, forum=excluded.forum, subject=excluded.subject, title=excluded.title, "
            "author=excluded.author, date=excluded.date, posted=excluded.posted, content=excluded.content, html=excluded.html, gone=0",
            (p["id"], topic_id, forum, name, p["title"], p["author"], p["date"], p["posted"], p["content"], p["html"]),
        )
        # An inline image links its file with no text; the attachment box names it.
        for file_id, label in p["files"] + [(i, "") for i in p["images"]]:
            db.execute(
                "insert into documents (id, post, title) values (?,?,nullif(?, '')) on conflict(id) do update set "
                "post = coalesce(documents.post, excluded.post), title = coalesce(excluded.title, documents.title)",
                (file_id, p["id"], label),
            )
    # A post deleted on the board stays in the archive, marked gone.
    ids = [p["id"] for p in posts]
    db.execute(f"update posts set gone = 1 where topic = ? and id not in ({','.join('?' * len(ids))})", (topic_id, *ids))
    db.execute("update topics set forum = coalesce(?, forum), done_last_post = coalesce(?, -1) where id = ?", (forum, last_post, topic_id))
    return len(posts)


def fetch_topics(db, quiet=False, recent=False):
    """Fetch the pending topics. recent: also the ones with a post in the last 14 days, as an edit does not change
    the last post id. Only once per run: these stay "recent" after the fetch."""
    # shortcut: an edit to a post older than 14 days is not seen; a periodic full refetch would catch it.
    extra = " or id in (select topic from posts where posted >= strftime('%Y-%m-%dT%H:%M:%S', 'now', '-14 days'))" if recent else ""
    pending = db.execute(f"select id, last_post from topics where gone = 0 and ({PENDING}{extra})").fetchall()
    if not quiet or len(pending) >= 100:
        print(f"{len(pending)} topics to fetch", flush=True)
    done = posts = 0
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(read_topic, t): (t, last) for t, last in pending}
        for future in as_completed(futures):
            topic_id, last_post = futures[future]
            try:
                posts += store_topic(db, topic_id, last_post, future.result())
            except Exception as error:
                # One topic that fails (network, or a page the parser cannot read) must not stop the run. It is not
                # marked done, so the next run tries it again, and stats reports its missing posts.
                print(f"skip topic {topic_id}: {type(error).__name__}: {error}", flush=True)
                continue
            done += 1
            if done % 100 == 0 or done == len(pending):
                db.commit()
                print(f"topics {done}/{len(pending)}, {posts} posts", flush=True)
    db.commit()


# ---------- checks ----------


def board_totals():
    soup = get("index.php")
    stats = text(soup.select_one(".stat-block.statistics p"))
    found = dict(re.findall(r"Total (posts|topics) (\d+)", stats))
    return int(found.get("topics", 0)), int(found.get("posts", 0))


def show_stats(db):
    q = lambda sql: db.execute(sql).fetchone()
    topics, posts = board_totals()
    print(f"board shows {topics} topics, {posts} posts (guests see a little less: hidden forums)")
    stored_topics, stored_posts = q("select count(*) from topics where gone = 0")[0], q("select count(*) from posts where gone = 0")[0]
    print("stored topics, posts (not gone):", stored_topics, stored_posts)
    problems = []
    if not topics or topics > stored_topics or posts > stored_posts:
        problems.append("the board shows more than is stored (or its totals could not be read)")
    print(
        "kept after removal from the board: topics",
        q("select count(*) from topics where gone = 1")[0],
        "posts",
        q("select count(*) from posts where gone = 1")[0],
    )
    print("topics not fetched yet:", q(f"select count(*) from topics where gone = 0 and {PENDING}")[0])
    bad = db.execute(
        "select t.id, t.replies + 1, count(p.id) from topics t left join posts p on p.topic = t.id and p.gone = 0 "
        "where t.gone = 0 and t.done_last_post = coalesce(t.last_post, -1) group by t.id having count(p.id) != t.replies + 1"
    ).fetchall()
    print(f"topics whose stored posts differ from replies + 1: {len(bad)}", bad[:10])
    if bad:
        problems.append("topics with missing posts")
    bad = db.execute(
        "select f.id, f.name, f.own_topics, count(t.id) from forums f left join topics t on t.forum = f.id and t.gone = 0 "
        "where f.own_topics is not null group by f.id having count(t.id) != f.own_topics"
    ).fetchall()
    print(f"forums whose stored topics differ from the forum page: {len(bad)}", bad[:10])
    if bad:
        problems.append("forums with missing topics")
    print("documents: linked, fetched, errors:", q("select count(*), sum(fetched), sum(error is not null) from documents"))
    # A non-zero exit makes the daily run red, so a parser broken by a board change does not go unseen.
    if problems:
        sys.exit("incomplete: " + "; ".join(problems))


def connect():
    db = sqlite3.connect(DB, timeout=60)
    db.execute("pragma journal_mode = wal")
    db.executescript(SCHEMA)
    return db


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    command = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if command == "stats":
        show_stats(db)
    elif command == "sync":
        crawl_tree(db)
        fetch_topics(db, recent=True)
        # The footer's "Provereno" (pages/build.py): when the board was last read, whether or not it had new posts.
        db.execute("insert or replace into meta values ('forum_synced', strftime('%Y-%m-%dT%H:%MZ', 'now'))")
        db.commit()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
