"""The board from nastava.db: the forums as smerovi and subjects, the posts as items, the topics."""

import re
from collections import Counter, defaultdict
from translit import fold
from .clean import attachments, clean_html, downloads, has_kinds, preuzeto
from .known import RENAMED
from .output import PAGE_TEXT
from .text import BASE, KIND, parse_date, set_hrefs, short_smer, slug, smer_abbr, smer_label


def subject_name(forum_name):
    """'Цевни водови (1044)' -> 'Цевни водови': one subject for all the codes it had."""
    return " ".join(re.sub(r"\(\d+\)\s*$", "", forum_name.replace("﻿", "")).split())


def load_places(db):
    """Map each forum id to (smer, subject). A smer is a top forum; a subject merges the forums of one smer with one name.
    The subject is None for the smer's own notices."""
    forums = {r["id"]: dict(r) for r in db.execute("SELECT id, parent, name FROM forums")}
    smerovi, subjects, place = {}, {}, {}
    for f in sorted(forums.values(), key=lambda f: f["id"]):
        top = f
        while top["parent"] is not None:
            top = forums[top["parent"]]
        # label: the name as shown ('Основне академске студије - Машинско инжењерство'); short: its abbreviation, for
        # URLs and matching; abbr: the name on a phone's home page ('Основне академске студије - МИ', rows.html).
        smer = smerovi.setdefault(
            top["id"],
            {
                "id": top["id"],
                "name": top["name"],
                "short": short_smer(top["name"]),
                "label": smer_label(top["name"]),
                "abbr": smer_abbr(top["name"]),
            },
        )
        if f is top:
            place[f["id"]] = (smer, None)
            continue
        name = subject_name(f["name"])
        # The lowest forum id of the merged subject names its page.
        subject = subjects.setdefault((top["id"], name), {"id": f["id"], "name": name, "smer": smer, "codes": []})
        subject["codes"] += re.findall(r"\((\d+)\)\s*$", f["name"])
        place[f["id"]] = (smer, subject)
    # The same subject name is in several smerovi, so a subject's URL has its smer's.
    set_hrefs(smerovi.values(), lambda m: f"/smer/{slug(short_smer(m['name']))}/")
    for m in smerovi.values():
        # The smer in a search URL and in the index's filter: its URL's slug ('oas-mi'), never its Cyrillic name.
        m["key"] = m["href"].strip("/").split("/")[-1]
    set_hrefs(subjects.values(), lambda s: f"{s['smer']['href'].replace('/smer/', '/predmet/', 1)}{slug(s['name'])}/")
    for s in subjects.values():
        s["name"] = RENAMED.get(s["href"], s["name"])
    return place, smerovi, subjects


def load_items(db, place):
    docs = {r["id"]: dict(r) for r in db.execute("SELECT * FROM documents WHERE fetched = 1 AND error IS NULL")}
    posts = {r["id"]: dict(r) for r in db.execute("SELECT * FROM posts")}
    items = []
    for p in posts.values():
        iso, year = parse_date(p["date"], p["posted"])
        smer, subj = place.get(p["forum"], (None, None))
        html = clean_html(p["html"])
        items.append(
            dict(
                id=f"p{p['id']}",
                kind="post",
                title=p["title"],
                smer=smer,
                subj=subj,
                subject=subj and subj["name"],
                date=iso,
                year=year,
                topic=p["topic"],
                num=p["id"],
                when=p["date"],
                posted=p["posted"] or "",
                author=p["author"],
                body=preuzeto(p["content"]),
                html=attachments(html),
                files=downloads(html),
                gone=p["gone"],
                source_url=f"{BASE}viewtopic.php?p={p['id']}#p{p['id']}",
            )
        )
    for d in docs.values():
        p = posts.get(d["post"]) or {}
        iso, year = parse_date(p.get("date"), d["uploaded_at"])
        smer, subj = place.get(p.get("forum"), (None, None))
        items.append(
            dict(
                id=f"d{d['id']}",
                kind="document",
                title=d["title"] or d["filename"],
                smer=smer,
                subj=subj,
                files=[],
                subject=subj and subj["name"],
                topic=None,
                when=p.get("date"),
                posted=p.get("posted") or "",
                date=iso,
                year=year,
                author=p.get("author"),
                body=(d["text"] or "")[:PAGE_TEXT],
                html=None,
                source_url=f"{BASE}viewtopic.php?p={d['post']}#p{d['post']}" if d["post"] else None,
                doc=dict(filename=d["filename"], size=round((d["size"] or 0) / 1024), uploaded_at=d["uploaded_at"]),
                download_url=f"{BASE}download/file.php?id={d['id']}",
            )
        )
    return items


def board_subject(by_code, by_name, code, name, program):
    """The board's subject of a subject-book entry: the same code, else the same name in the smer of its program."""
    return by_code.get(code) or by_name.get((fold(short_smer(program.replace(" — ", " - "))), fold(name)))


def book_subject(b, smerovi, subjects):
    """The board subject of a subject-book entry (a row of subjects: id, name, program; board_subject); one the board
    does not have is made here, in the smer of its program, and that smer too when the board has none (Индустрија
    4.0). A department site's page of a subject (cent, ie) is listed under it."""
    code, name, program = b["id"], b["name"], b["program"]
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    by_name = {(fold(s["smer"]["short"]), fold(s["name"])): s for s in subjects.values()}
    s = board_subject(by_code, by_name, code, name, program)
    if s:
        return s
    smer_name = program.replace(" — ", " - ")
    smer_name = smer_name[:1].lower() + smer_name[1:]
    m = next((m for m in smerovi.values() if fold(m["short"]) == fold(short_smer(smer_name))), None)
    if not m:
        m = dict(id=f"cent:{program}", name=smer_name, short=short_smer(smer_name), label=smer_label(smer_name), abbr=smer_abbr(smer_name))
        m["href"] = f"/smer/{slug(m['short'])}/"
        m["key"] = m["href"].strip("/").split("/")[-1]
        smerovi[m["id"]] = m
    s = dict(id=f"c{code}", name=name, smer=m, codes=[code])
    s["href"] = f"{m['href'].replace('/smer/', '/predmet/', 1)}{slug(name)}/"
    if any(o["href"] == s["href"] for o in subjects.values()):
        s["href"] = f"{s['href'][:-1]}-{code}/"
    subjects[(m["id"], name)] = s
    return s


def row_katedra(s, topics):
    """The katedra whose icon marks a forum subject's row (rows.html): in the forum Katedre the subject is one; else
    the subject book's, its holder's, or the one most of its teachers are in: by their profiles, then by their posts
    in it (the moduli). Only for the icon: the book's own field is left as the faculty wrote it."""
    if s["smer"]["key"] == "katedre":
        return s["name"]
    i = s.get("info") or {}
    if i.get("katedra") or (i.get("holder_t") or {}).get("katedra"):
        return i.get("katedra") or i["holder_t"]["katedra"]
    c = Counter(t["katedra"] for t in s.get("teachers", []) + i.get("teachers", []) if t["katedra"]) or Counter(
        p["teacher"]["katedra"] for t in topics for p in t["posts"] if p.get("teacher") and p["teacher"]["katedra"]
    )
    return c.most_common(1)[0][0] if c else None


def load_topics(db, items):
    """The board's topics, newest last post first. A topic of one post links to that post's page, a longer one to /tema/."""
    titles = dict(db.execute("SELECT id, title FROM topics"))
    posts = defaultdict(list)
    for it in items:
        if it["kind"] in ("post", "cent", "katedra"):
            posts[it["topic"]].append(it)
    topics = []
    for tid, rows in posts.items():
        rows.sort(key=lambda r: r["num"])
        t = dict(
            id=tid,
            title=titles.get(tid) or rows[0]["title"],
            posts=rows,
            first=rows[0],
            last=max(rows, key=lambda r: r["posted"]),
            subj=rows[0]["subj"],
            smer=rows[0]["smer"],
            gone=all(r["gone"] for r in rows),
            href=f"/tema/{tid}/" if len(rows) > 1 else f"/item/{rows[0]['id']}/",
            authors="|".join(sorted({(r["author"] or "").lower() for r in rows})),
            find=fold(" ".join([titles.get(tid) or ""] + [f"{r['title']} {r['who'] or ''}" for r in rows])),
        )
        kinds = [has_kinds(r) for r in rows]
        t["has_file"], t["has_link"] = any(f for f, _ in kinds), any(lk for _, lk in kinds)
        for i, r in enumerate(rows):
            # The posts before and after it in the topic, for a post's own page.
            r["thread"], r["prev"], r["next"] = t, rows[i - 1] if i else None, rows[i + 1] if i + 1 < len(rows) else None
        topics.append(t)
    return sorted(topics, key=lambda t: t["last"]["posted"], reverse=True)


def side_panel(items):
    """The counts of the side panel (sidebar.html), the same on every page."""
    years = Counter(r["year"] for r in items if r["year"])
    return dict(
        total=len(items),
        kinds=Counter(KIND[r["kind"]] for r in items),
        year_hist=sorted(years.items()),
        downloads=sum(n for n, _ in attachment_files(items).values()),
    )


def attachment_files(items):
    """{attachment id: (downloads, post)}: a file that two posts link counts once."""
    return {f: (n, it) for it in items for f, _, n in it["files"]}
