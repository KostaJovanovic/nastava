# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Every file (not page, not image) the Wayback Machine has of the old faculty sites: mas.bg.ac.yu (to 2010) and
mas.bg.ac.rs up to 2014 (the gap before this archive's own data), into work/wayback/ for review.

uv run tools/wayback_files.py [--list]   (--list: only the CDX listing and the counts)

One file per path: the hosts that were other names of www (www.simlab, ysm, ...) are www; .yu and .rs are one site;
paths compare without case (the old server ignored it). Of a path's captures, the newest good one. Resumable: what
work/wayback/files.jsonl has as ok is not fetched again. Not the sport forum and album, not alfa's personal pages.
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "work" / "wayback"
FILES = OUT / "files"
MANIFEST = OUT / "files.jsonl"
CDX = "https://web.archive.org/cdx/search/cdx"
DOMAINS = [("mas.bg.ac.yu", None), ("mas.bg.ac.rs", "2014")]
ALIASES = {"www.simlab", "www.cshs03", "cshs03", "ysm", "bgweekend", "mas", ""}  # other names of www
SKIP_HOSTS = {"sport", "alfa"}
SKIP_MIME = re.compile(r"^(text/|image/|warc/|application/(javascript|x-javascript|x-msdos-program))|^-$|unk")
DELAY = 1.5


def get(s, url, **kw):
    """GET with backoff: archive.org answers 429 and 5xx under load."""
    for n in range(6):
        try:
            r = s.get(url, timeout=300, **kw)
            if r.status_code not in (429, 500, 502, 503, 504):
                return r
            why = r.status_code
        except requests.RequestException as e:
            why = type(e).__name__
        print(f"  retry {n + 1} ({why}): {url[:100]}", file=sys.stderr, flush=True)
        time.sleep(min(300, 10 * 2**n))
    return None


def host_key(netloc):
    h = netloc.lower().split(":")[0]
    h = re.sub(r"\.?mas\.bg\.ac\.(yu|rs)$", "", h)
    return "www" if h in ALIASES else h


def key_of(url):
    u = urlsplit(url)
    return host_key(u.netloc) + "/" + unquote(u.path).lstrip("/").lower()


def listing(s):
    """The CDX rows of both domains, kept in work/wayback/cdx-<domain>.txt (a listing takes minutes; a server-side
    status filter made it time out)."""
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    for dom, to in DOMAINS:
        cache = OUT / f"cdx-{dom}.txt"
        if not cache.exists():
            print(f"listing {dom} ...", file=sys.stderr, flush=True)
            params = dict(url=dom, matchType="domain", fl="original,timestamp,mimetype,statuscode,length")
            if to:
                params["to"] = to
            r = get(s, CDX, params=params)
            if r is None or r.status_code != 200 or r.text.lstrip().startswith("<"):
                sys.exit(f"CDX listing of {dom} failed")
            cache.write_text(r.text, "utf-8")
        rows += [ln.split(" ") for ln in cache.read_text("utf-8").splitlines() if ln.count(" ") == 4]
    by = {}
    for orig, ts, mime, status, length in rows:
        k = key_of(orig)
        if status != "200" or k.split("/")[0] in SKIP_HOSTS or SKIP_MIME.search(mime.lower()) or k.endswith("/"):
            continue
        by.setdefault(k, []).append(dict(url=orig, ts=ts, mime=mime, length=length))
    for caps in by.values():
        caps.sort(key=lambda c: c["ts"], reverse=True)
    return by


def safe(part):
    part = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", part).strip(" .") or "_"
    return part[:150]


def looks_right(mime, body):
    """Wayback can answer a file's URL with its own HTML page: a PDF starts with %PDF, the rest are not HTML."""
    if "pdf" in mime:
        return body[:1024].lstrip().startswith(b"%PDF")
    return not body[:512].lstrip().lower().startswith((b"<!doctype html", b"<html"))


def main():
    s = requests.Session()
    s.headers["User-Agent"] = "nastava-archive (old faculty files)"
    by = listing(s)
    print(f"{len(by)} files", file=sys.stderr)
    if "--list" in sys.argv:
        for mime, n in sorted({m: sum(1 for c in by.values() if c[0]["mime"] == m) for m in {c[0]["mime"] for c in by.values()}}.items(), key=lambda x: -x[1]):
            print(n, mime)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    done = set()
    if MANIFEST.exists():
        done = {j["key"] for j in map(json.loads, MANIFEST.read_text("utf-8").splitlines()) if j.get("ok")}
    todo = [k for k in sorted(by) if k not in done]
    print(f"{len(done)} done, {len(todo)} to fetch", file=sys.stderr)
    with MANIFEST.open("a", encoding="utf-8") as log:
        for i, k in enumerate(todo, 1):
            row = dict(key=k, captures=len(by[k]))
            for c in by[k][:3]:
                r = get(s, f"https://web.archive.org/web/{c['ts']}id_/{c['url']}")
                time.sleep(DELAY)
                if r is None or r.status_code != 200 or not looks_right(c["mime"], r.content):
                    row["err"] = f"{c['ts']}: {r.status_code if r is not None else 'no answer'}"
                    continue
                path = FILES.joinpath(*map(safe, k.split("/")))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
                row = dict(row, ok=True, url=c["url"], ts=c["ts"], mime=c["mime"], size=len(r.content),
                           sha256=hashlib.sha256(r.content).hexdigest(), path=path.relative_to(OUT).as_posix())
                row.pop("err", None)
                break
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            if i % 50 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr)


if __name__ == "__main__":
    main()
