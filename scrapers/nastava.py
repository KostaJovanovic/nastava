# /// script
# requires-python = ">=3.11"
# dependencies = ["requests[socks]", "beautifulsoup4"]
# ///
"""Archive every post of nastava.mas.bg.ac.rs (phpBB, public, no login).

Usage: nastava.py feed | sync | stats
  feed    the frequent run: the board's Atom feed (its 30 newest posts, one request), then for each post not stored
          the page of its topic that has it. More than 30 new since the last run, or a forum not known yet: sync.
  sync    walk the forum tree, then fetch the topics that changed (the first run fetches all); the weekly check
          (ci/plan.py "provera"): it also finds deleted and moved topics
  stats   compare the counts the board shows with the stored rows; exit 1 when posts are missing

Each forum page lists its subforums with their topic and post counts and last post id.
A forum is walked only when these differ from the last complete walk, and a topic is
fetched only when its last post id changed. But a changed forum is walked whole (every
page) and so is each forum above it: that was 60-400 requests a run, so the frequent
runs read the feed instead (docs/PLAN-scraping.md).
"""

import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup

import common
from common import DELAY, session

BASE = "https://nastava.mas.bg.ac.rs/nastava/"
FEED = "app.php/feed"  # phpBB's Atom feed of the newest posts, all forums a guest sees
WORKERS = int(os.getenv("WORKERS", "1"))  # one request at a time (docs/PLAN-scraping.md)
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


def page_posts(soup):
    """The posts of one topic page."""
    posts = []
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
                "files": [(int(i), text(a)) for a in post.select('a[href*="download/file.php?id="]') for i in [param(a["href"], "id")] if i],
                "images": {
                    int(i)
                    for i in re.findall(r"download/file\.php\?id=(\d+)", " ".join(img.get("src", "") for img in content.find_all("img")))
                },
            }
        )
    return posts


def page_forum(soup):
    """(forum id, forum name) of a topic page, from its breadcrumb; (None, None) when it has none."""
    crumb = soup.select(".crumb[data-forum-id]")
    return (int(crumb[-1]["data-forum-id"]), text(crumb[-1])) if crumb else (None, None)


def read_topic(topic_id):
    """Return (forum id, forum name, posts) of one topic, or None when the topic is gone."""
    forum = name = None
    posts = []
    for soup in walk_pages(f"viewtopic.php?t={topic_id}"):
        forum, name = page_forum(soup) if soup.select(".crumb[data-forum-id]") else (forum, name)
        posts += page_posts(soup)
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
    store_posts(db, topic_id, forum, name, posts)
    # A post deleted on the board stays in the archive, marked gone.
    ids = [p["id"] for p in posts]
    db.execute(f"update posts set gone = 1 where topic = ? and id not in ({','.join('?' * len(ids))})", (topic_id, *ids))
    db.execute("update topics set forum = coalesce(?, forum), done_last_post = coalesce(?, -1) where id = ?", (forum, last_post, topic_id))
    return len(posts)


def store_posts(db, topic_id, forum, name, posts):
    """Store posts of a topic (all of it, or one page: nothing is marked gone here) and their attachments."""
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


# ---------- feed ----------


def feed_ids(xml):
    """The post ids of the board's Atom feed, newest first (each entry links viewtopic.php?p=<id>)."""
    atom = "{http://www.w3.org/2005/Atom}"
    ids = []
    for entry in ET.fromstring(xml).iter(f"{atom}entry"):
        link = entry.find(f"{atom}link")
        if link is not None and (i := param(link.get("href"), "p")):
            ids.append(i)
    return ids


def feed(db):
    """The frequent run: the feed, then the page of each new post's topic that has it (viewtopic.php?p=<id>), one
    request a page; a page with several new posts is read once. Falls back to sync (the walk) when the feed may have
    missed posts: all of its posts are new and the newest stored is older than its oldest (more than its 30 posts since
    the last run), or a post is in a forum not stored yet (its parent and place come from the walk)."""
    r = session().get(BASE + FEED, timeout=60)
    time.sleep(DELAY)
    r.raise_for_status()
    ids = feed_ids(r.text)
    if not ids:
        raise ValueError("feed: no entries (the board changed its feed?)")
    stored = {i for (i,) in db.execute(f"select id from posts where id in ({','.join('?' * len(ids))})", ids)}
    new = sorted(i for i in ids if i not in stored)
    newest = db.execute("select max(id) from posts").fetchone()[0] or 0
    print(f"feed: {len(ids)} posts, {len(new)} new", flush=True)
    if new and len(new) == len(ids) and newest < min(ids):
        print("feed: more new posts than it shows: walking the forums", flush=True)
        return sync(db)
    forums = {f for (f,) in db.execute("select id from forums")}
    for post_id in new:
        if post_id in stored:  # on a page read for an earlier one
            continue
        soup = get(f"viewtopic.php?p={post_id}")
        if soup is None:  # deleted since the feed listed it
            continue
        forum, name = page_forum(soup)
        title = soup.select_one("h2.topic-title a")
        topic_id = param(title["href"], "t") if title else None
        posts = page_posts(soup)
        if not (forum and topic_id and posts):
            raise ValueError(f"post {post_id}: no forum, topic or posts on its page (the board changed its markup?)")
        if forum not in forums:
            print(f"feed: post {post_id} is in a forum not stored yet ({forum}): walking the forums", flush=True)
            return sync(db)
        store_posts(db, topic_id, forum, name, posts)
        store_feed_topic(db, topic_id, forum, text(title), max(p["id"] for p in posts), bool(soup.find("a", rel="next")))
        stored |= {p["id"] for p in posts}
        db.commit()
    # Topics left to fetch whole (a run that failed, a new topic of more than one page): rare, so fetched now.
    fetch_topics(db)


def store_feed_topic(db, topic_id, forum, title, last_post, more_pages):
    """A topic after its page from the feed: its last post is the newest one seen. It stays done (no full fetch) when
    it was done before, or is new and all on this page; else fetch_topics reads it whole. Its replies follow the
    stored posts, so stats sees a done topic complete."""
    old = db.execute("select last_post, done_last_post from topics where id = ?", (topic_id,)).fetchone()
    last = max(last_post, (old and old[0]) or 0)
    done = old[0] == old[1] if old else not more_pages
    db.execute(
        "insert into topics (id, forum, title, last_post, done_last_post) values (?,?,?,?,?) on conflict(id) do update set "
        "forum = excluded.forum, title = excluded.title, last_post = excluded.last_post, "
        "done_last_post = case when ? then excluded.done_last_post else topics.done_last_post end, gone = 0",
        (topic_id, forum, title, last, last if done else None, done),
    )
    db.execute(
        "update topics set replies = (select count(*) - 1 from posts where topic = ? and gone = 0) where id = ? and done_last_post = last_post",
        (topic_id, topic_id),
    )


def sync(db):
    crawl_tree(db)
    fetch_topics(db)


def fetch_topics(db, quiet=False):
    """Fetch the pending topics: new ones and those with a new last post. An edit to a post is not seen (it does not
    change the last post id); re-reading recent topics for edits was most of each run's requests to the board."""
    pending = db.execute(f"select id, last_post from topics where gone = 0 and ({PENDING})").fetchall()
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
        # Fewer stored than the page showed: missing. More is a topic the feed brought since the last walk.
        "where f.own_topics is not null group by f.id having count(t.id) < f.own_topics"
    ).fetchall()
    print(f"forums whose stored topics differ from the forum page: {len(bad)}", bad[:10])
    if bad:
        problems.append("forums with missing topics")
    print("documents: linked, fetched, errors:", q("select count(*), sum(fetched), sum(error is not null) from documents"))
    # A non-zero exit makes the daily run red, so a parser broken by a board change does not go unseen.
    if problems:
        sys.exit("incomplete: " + "; ".join(problems))


def connect():
    return common.connect(SCHEMA)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect()
    command = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if command == "stats":
        show_stats(db)
    elif command in ("feed", "sync"):
        try:
            (feed if command == "feed" else sync)(db)
        except BaseException:  # common.Blocked too (a 403): the banner, then out
            # The site's red banner (build.py forum_failed) until a later read works.
            db.execute("insert or replace into meta values ('forum_failed', strftime('%Y-%m-%dT%H:%MZ', 'now'))")
            db.commit()
            raise
        # The footer's "Provereno" (pages/build.py): when the board was last read, whether or not it had new posts.
        db.execute("insert or replace into meta values ('forum_synced', strftime('%Y-%m-%dT%H:%MZ', 'now'))")
        db.commit()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
