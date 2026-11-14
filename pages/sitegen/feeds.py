"""The Atom feeds: the board's newest posts and each subject's."""

import json
from collections import defaultdict
from markupsafe import escape
from .output import FEED, FEED_ALL
from .text import SITE_URL


def post_href(it):
    """A post's place: its anchor in a topic of several posts, else its own page."""
    return f"{it['thread']['href']}#p{it['num']}" if len(it["thread"]["posts"]) > 1 else f"/item/{it['id']}/"


def atom(title, path, posts):
    """An Atom feed of the newest posts (newest first) for a feed reader: the whole board, one subject or the news
    (an item with its own href). A reader needs whole URLs, so they are on the main domain."""

    def entry(it):
        href, page = it.get("href") or post_href(it), it.get("href") or f"/item/{it['id']}/"
        place = (it["subj"] and it["subj"]["name"]) or (it["smer"] and it["smer"]["label"]) or ", ".join(it.get("cats", []))
        return (
            f'<entry><title>{escape(it["title"] or "")}</title><link href="{SITE_URL}{escape(href)}"/>'
            f"<id>{SITE_URL}{escape(page)}</id><updated>{it['posted']}</updated>"
            f"<author><name>{escape(it['who'] or '')}</name></author>"
            + (f'<category term="{escape(place)}"/>' if place else "")
            + f'<content type="html">{escape(it["html"] or it["body"] or "")}</content></entry>'
        )

    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="sr">'
        f"<title>{escape(title)}</title><id>{SITE_URL}{escape(path)}</id>"
        f'<link rel="self" href="{SITE_URL}{escape(path)}feed.xml"/><link href="{SITE_URL}{escape(path)}"/>'
        f"<updated>{posts[0]['posted'] if posts else '1970-01-01T00:00:00+00:00'}</updated>"
        + "".join(entry(it) for it in posts)
        + "</feed>\n"
    )


def write_feeds(site, items, subjects, pushed=()):
    """/feed.xml: the board's newest posts; <subject page>/feed.xml: the subject's. Next to a page that exists."""
    posts = sorted((it for it in items if it["kind"] in ("post", "cent", "katedra")), key=lambda it: it["posted"], reverse=True)
    (site / "feed.xml").write_text(atom("Forum nastave · Mašinski fakultet", "/", posts[:FEED_ALL]), encoding="utf-8")
    of = defaultdict(list)
    for it in posts:
        if it["subj"] and len(of[it["subj"]["id"]]) < FEED:
            of[it["subj"]["id"]].append(it)
    for s in subjects.values():
        (site / s["href"].strip("/") / "feed.xml").write_text(
            atom(f"{s['name']} · forum nastave", s["href"], of[s["id"]]), encoding="utf-8"
        )
    # The subjects' newest posts, next to the site (not on it), for ci/push.py: it notifies those newer than a post id.
    # k: "p" a board post, "c" a cent notice, "s" a cent page version; ci/push.py keeps one "before" per kind.
    # a: the teacher who wrote it (their page's slug), for a browser that wants only some teachers' posts of a subject.
    # shortcut: the newest 1000 posts and notices only; a scrape that brings more new posts notifies only these.
    (site.parent / "push.json").write_text(
        json.dumps(
            [
                dict(
                    k=it["id"][0],
                    id=it["num"],
                    s=it["subj"]["href"],
                    n=it["subj"]["name"],
                    t=it["title"] or "",
                    u=post_href(it),
                    **({"a": it["teacher"]["href"].split("/")[2]} if it.get("teacher") else {}),
                )
                for it in posts
                if it["subj"]
            ][:1000]
            + list(pushed),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
