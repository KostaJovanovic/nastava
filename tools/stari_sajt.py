# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4==4.15.0"]
# ///
"""The old faculty sites (mas.bg.ac.yu, to 2014) into the archive, from work/wayback/ (wayback_articles.py's items,
wayback_files.py's files).

uv run tools/stari_sajt.py vesti   data/stare-vesti.jsonl: each item, where it goes, its links made to work
uv run tools/stari_sajt.py host    upload the files the items link to the releases stari-<host> (gh, signed in)

An item of the faculty's news goes to /vesti/ (forum null); a department's, to its forum on the board (load_stare,
by the name in FORUM), or the subject its title names. In its text, a link to a file of the old sites is our copy when
wayback_files.py saved it (/files/stari-<host>/<asset>/<name>, the Worker serves the release), the name alone when
Wayback never had it; a link to a page of the old sites is that page's Wayback copy of the item's time.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from common import asset_name, release_assets, upload_assets  # noqa: E402
from wayback_files import key_of  # noqa: E402

WB = ROOT / "work" / "wayback"
OUT = ROOT / "data" / "stare-vesti.jsonl"
OLD = re.compile(r"(^|\.)mas\.bg\.ac\.(yu|rs)$")
PAGE = re.compile(r"(\.(html?|php\d?|aspx?|shtml|cgi)|/|^[^.]*)$", re.I)  # a path that is a page, not a file

# A department's news (the section wayback_articles.py gives it): its forum on the board.
FORUM = [
    (r"katedre/mehanika/", "катедра за механику"),
    (r"katedre/termomehanika/", "катедра за термомеханику"),
    (r"katedre/t-crtanje-mehanizmi/", "катедра за теорију механизама и машина"),
    (r"katedre/termoenergetika/", "катедра за термоенергетику"),
    (r"katedre/otpornost-konstr/", "катедра за отпорност конструкција"),
    (r"katedre/fizika-elek/", "катедра за физику и електротехнику"),
    (r"katedre/matematika/", "катедра за математику"),
    (r"katedre/opste-mas-konstr/|^omk$", "катедра за опште машинске конструкције"),
    (r"katedre/motorna vozila/", "катедра за моторна возила"),
    (r"katedre/ie/", "катедра за индустријско инжењерство"),
    (r"katedre/proizvodno/", "катедра за производно машинство"),
    (r"^(tribolab|motori)$", "катедра за моторе"),  # tribolab: the department's laboratory
    (r"^au$", "катедра за аутоматско управљање"),
]
UPIS = re.compile(r"^(www/upis|kolubara)")


def files():
    """{key: manifest row} of wayback_files.py's saved files."""
    rows = map(json.loads, (WB / "files.jsonl").read_text("utf-8").splitlines())
    return {r["key"]: r for r in rows if r.get("ok")}


def tag_of(key):
    return "stari-" + key.split("/")[0]


def href_of(key, row):
    name = unquote(urlsplit(row["url"]).path.rsplit("/", 1)[-1])  # as the site named it (the key is lowercase)
    return f"/files/{tag_of(key)}/{asset_name(key)}/{quote(name)}"


def is_old(url):
    u = urlsplit(url)
    return u.scheme in ("http", "https") and bool(OLD.search(u.hostname or ""))


def links(html):
    return [a for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if is_old(a["href"])]


def fix(html, ts, saved):
    """The item's links made to work (see the module's note)."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if not is_old(a["href"]):
            continue
        k = key_of(a["href"])
        if k in saved:
            a["href"] = href_of(k, saved[k])
        elif PAGE.search(urlsplit(a["href"]).path):
            a["href"] = f"https://web.archive.org/web/{ts}/{a['href']}"
        else:
            a.unwrap()
    return str(soup)


def vesti():
    saved = files()
    out = []
    for a in map(json.loads, (WB / "articles.jsonl").read_text("utf-8").splitlines()):
        last = a["copies"][-1]  # https://web.archive.org/web/<ts>/<url>, the newest copy
        ts = last.split("/")[4]
        forum = next((f for pat, f in FORUM if re.search(pat, a["section"])), None)
        out.append(
            dict(
                key=a["key"],
                date=a["date"],
                title=a["title"],
                author=a["author"] or None,
                html=fix(a["html"], ts, saved),
                full=fix(a["full"], ts, saved) if a["full"] else "",
                forum=forum,
                upis=bool(UPIS.match(a["section"])),
                wp=int(a["id"]) if a["kind"] == "wordpress" and a["id"] else None,
                host=urlsplit(last.split("/", 5)[5]).hostname.removeprefix("www."),
                wayback=last,
            )
        )
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"{OUT.name}: {len(out)} items, {sum(1 for r in out if r['forum'])} departments'")


def host():
    """Upload the saved files the items link to stari-<host>: those missing, or changed since."""
    saved = files()
    wanted = {k for a in map(json.loads, (WB / "articles.jsonl").read_text("utf-8").splitlines())
              for k in map(key_of, (x["href"] for x in links(a["html"] + a["full"]))) if k in saved}
    by_tag = {}
    for k in sorted(wanted):
        by_tag.setdefault(tag_of(k), []).append(k)
    for tag, keys in by_tag.items():
        have = release_assets(tag, tag, "Files of the old faculty sites (mas.bg.ac.yu), from the Wayback Machine (tools/stari_sajt.py).")
        todo = {}
        for k in keys:
            data = (WB / saved[k]["path"]).read_bytes()
            if have.get(asset_name(k)) not in (hashlib.sha256(data).hexdigest(), ""):
                todo[asset_name(k)] = data
        upload_assets(tag, todo)
        print(f"{tag}: {len(todo)} uploaded, {len(keys)} files")


if __name__ == "__main__":
    {"vesti": vesti, "host": host}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
