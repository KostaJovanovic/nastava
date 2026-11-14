"""The /statistika/ page: counts, charts and the word cloud."""

import re
from collections import Counter, defaultdict
from datetime import date
from urllib.parse import quote
from translit import fold, lat
from .known import CLOUD_STOP, MONTHS, RANKS, WEEKDAYS
from .load_board import attachment_files
from .output import env, katedra_href
from .text import short_smer


def bars(pairs, href=None):
    """[(label, count)] -> the rows of a bar chart (stats.html chart), each bar's height in % of the highest."""
    top = max((n for _, n in pairs), default=0) or 1
    return [dict(label=label, n=n, pct=round(n / top * 100, 1), href=href and href(label)) for label, n in pairs]


def ranking(counts, row, k=10):
    """The k highest counts as rows of a ranked list (stats.html rank); row(key) -> (label, href, note)."""
    top = counts.most_common(k)
    return [dict(zip(("label", "href", "note"), row(key)), n=n, pct=round(n / top[0][1] * 100, 1)) for key, n in top]


# What in a post's text is not its words: a link, an e-mail, a file's name, an attachment's "(1.2 MiB) preuzeto 5 puta".
NOT_WORDS = re.compile(
    r"\S*(?:://|www\.|@)\S*|\S+\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|7z|jpe?g|png|gif|txt|dwg|m)\b"
    r"|\([\d.,]+ [KMG]?i?B\) preuzeto \d+ puta",
    re.I,
)


def post_words(it):
    """A post's words for the word cloud (stats.html): its title and text in Latin, lower case, without its
    attachments' names, links and file names."""
    text = it["title"] + "\n" + it["body"]
    for _, name, _ in it["files"]:
        text = text.replace(name, " ")
    return [w for w in re.findall(r"[^\W\d_]{4,}", lat(NOT_WORDS.sub(" ", text)).lower()) if w not in CLOUD_STOP]


CASE_END = re.compile(r"(?:ima|ama|omu|ega|emu|om|em|og|oj|im|ih|a|e|i|u|o)$")


def same_words(counts):
    """{word: count} -> {word: count} with a word's cases as one (ispit, ispita, ispitu): the forms whose stem (the
    word without its case ending) is the same; each shown as its stem when that is a common form (ispit; not a typo or
    an abbreviation, smen.), else its most frequent.
    shortcut: endings only, no dictionary: a sound change (zadatak, zadaci) stays apart; a stemmer if that matters."""
    stems = defaultdict(Counter)
    for w, n in counts.items():
        s = CASE_END.sub("", w)
        stems[s if len(s) >= 3 else w][w] += n
    # The "a" a word has only in some cases (studenata, petak) goes when the stem without it is there (student, petk).
    for s in list(stems):
        if (t := re.sub(r"a(\w)$", r"\1", s)) != s and t in stems:
            stems[t].update(stems.pop(s))
    return Counter({max(c, key=lambda w: (w == s and c[w] * 4 >= max(c.values()), c[w])): c.total() for s, c in stems.items()})


def archive_stats(items, topics, teachers):
    """The numbers of /statistika/: the board by time, who posts, what is downloaded, the teachers."""
    posts = [it for it in items if it["kind"] == "post"]
    dated = [it for it in posts if it["date"]]
    files = attachment_files(posts)
    by = {}  # a ranking's key (a username or a page's href) -> an item that names it
    tally = defaultdict(Counter)
    for it in posts:
        if it["author"]:
            tally["authors"][it["author"].lower()] += 1
            by.setdefault(it["author"].lower(), it)
        if it["subj"]:
            tally["subjects"][it["subj"]["href"]] += 1
            by.setdefault(it["subj"]["href"], it)
        if it["smer"]:
            tally["smerovi"][it["smer"]["href"]] += 1
            by.setdefault(it["smer"]["href"], it)
    for fid, (n, it) in files.items():
        tally["files"][fid] = n
        if it["teacher"]:
            tally["teacher_dl"][it["teacher"]["href"]] += n
            by.setdefault(it["teacher"]["href"], it)
        if it["subj"]:
            tally["subject_dl"][it["subj"]["href"]] += n
        if it["smer"]:
            tally["smer_dl"][it["smer"]["href"]] += n
    names = {fid: name for it in posts for fid, name, _ in it["files"]}
    author = lambda a: (by[a]["who"], by[a]["teacher"] and by[a]["teacher"]["href"], by[a]["teacher"] and "nastavnik")
    subject = lambda h: (by[h]["subj"]["name"], h, short_smer(by[h]["smer"]["name"]))
    smer = lambda h: (by[h]["smer"]["label"], h, None)
    teacher = lambda h: (by[h]["teacher"]["shown"], h, by[h]["teacher"]["title"])
    # A file's note has its post's date too: a teacher uploads a new copy of the same name for each exam.
    upload = lambda f: (
        names[f],
        f"/item/{files[f][1]['id']}/",
        " · ".join(filter(None, [files[f][1]["subject"] or files[f][1]["who"], env.filters["dmy"](files[f][1]["date"])])),
    )

    years = Counter(it["year"] for it in dated)
    months = Counter((it["year"], int(it["date"][5:7])) for it in dated)
    top_month = max(months.values(), default=1)
    hours = Counter(int(m[1]) for it in posts if (m := re.search(r"(\d{1,2}):\d\d", it["when"] or "")))
    days = Counter(date.fromisoformat(it["date"][:10]).weekday() for it in dated)
    busiest = Counter(it["date"][:10] for it in dated).most_common(1)
    topic = {t["href"]: t for t in topics}
    words = same_words(Counter(w for it in posts for w in post_words(it)))

    listed = [t for t in teachers if not t["gone"]]
    posting = {t["username"] for t in listed if t["username"] and t["username"] in tally["authors"]}
    by_teachers = sum(1 for it in posts if it["teacher"])
    return dict(
        first=min(dated, key=lambda it: it["date"], default=None),
        last=max(dated, key=lambda it: it["date"], default=None),
        totals=[
            (len(posts), "post"),
            (len(topics), "thread"),
            (len(tally["authors"]), "autor"),
            (len(tally["subjects"]), "predmet"),
            (len(files), "prilog"),
            (sum(tally["files"].values()), "preuzimanje"),
        ],
        years=bars(sorted(years.items()), lambda y: f"/?from={y}&to={y}"),
        heat=[
            dict(year=y, cells=[dict(m=MONTHS[m - 1], n=months[(y, m)], pct=round(months[(y, m)] / top_month * 100)) for m in range(1, 13)])
            for y in sorted(years)
        ],
        hours=bars([(h, hours[h]) for h in range(24)]),
        days=bars([(d, days[i]) for i, d in enumerate(WEEKDAYS)]),
        busiest=busiest[0] if busiest else None,
        words=sorted(ranking(words, lambda w: (w, f"/?q={quote(fold(w))}", None), k=60), key=lambda r: fold(r["label"])),
        authors=ranking(tally["authors"], author),
        subjects=ranking(tally["subjects"], subject),
        smerovi=ranking(tally["smerovi"], smer, k=20),
        files=ranking(tally["files"], upload),
        teacher_dl=ranking(tally["teacher_dl"], teacher),
        subject_dl=ranking(tally["subject_dl"], subject),
        smer_dl=ranking(tally["smer_dl"], smer, k=20),
        longest=ranking(
            Counter({t["href"]: len(t["posts"]) for t in topics}),
            lambda h: (topic[h]["title"], h, topic[h]["subj"] and topic[h]["subj"]["name"]),
        ),
        teachers=dict(
            listed=len(listed),
            emeritus=sum(1 for t in listed if t["emeritus"]),
            gone=len(teachers) - len(listed),
            posting=len(posting),
            share=round(by_teachers / (len(posts) or 1) * 100),
            titles=[(r, n) for r in RANKS if (n := sum(1 for t in listed if t["title"] == r))],
            katedre=ranking(
                Counter(t["katedra"] for t in listed if t["katedra"]),
                lambda k: (env.filters["katedra"](k).capitalize(), katedra_href(k), None),
            ),
        ),
    )
