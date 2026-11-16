# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "openpyxl", "xlrd", "pypdf", "python-docx", "pymupdf"]
# ///
"""Mails a teacher sent a subject's students, as posts of that subject (build.py's load_mail): each mail is a folder
mail/<date>-<key>/ with post.json (sender, date, subject line, the text without the quoted mail it answers, the reply
headers) and its attachments. To and Cc are never read: they are the students' addresses. Git keeps only the .json
files of mail/; the attachments (and teams.py's files) are assets of the GitHub release "mail", which the Worker serves
under /files/mail/.

Usage: mail.py add <folder of .eml files> <subject page, as /predmet/oas-mi/pumpe-i-ventilatori/>
       mail.py upload
  add     a mail already here (by Message-ID) is skipped.
  upload  upload the files of mail/ that the release has not yet (gh, signed in).
"""

import email
import hashlib
import json
import re
import sys
from datetime import timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup

from common import ROOT, asset_name, redact_students, release_assets, thumb_asset, thumbnail, upload_assets

MAIL = ROOT / "mail"
TAG = "mail"
THUMBS = MAIL / "thumbs.json"  # the files of mail/ with a thumbnail asset (upload)


def upload():
    """The files of mail/ the release lacks, and a thumbnail of each PDF and image (common.thumbnail); the paths with
    one go into THUMBS (git keeps it), for the build's file rows."""
    have = release_assets(TAG, "Mails and Teams files", "The files of mail/ (mail.py, teams.py). An asset's name is a hash of its path in mail/.")
    thumbs = set(json.loads(THUMBS.read_text(encoding="utf-8"))) if THUMBS.exists() else set()
    todo = {}
    for p in MAIL.rglob("*"):
        if not p.is_file() or p.suffix == ".json":
            continue
        path = p.relative_to(MAIL).as_posix()
        if asset_name(path) not in have:
            todo[asset_name(path)] = p.read_bytes()
        if thumb_asset(path) not in have and (t := thumbnail(path, todo.get(asset_name(path)) or p.read_bytes())):
            todo[thumb_asset(path)] = t
        if thumb_asset(path) in have or thumb_asset(path) in todo:
            thumbs.add(path)
    upload_assets(TAG, todo)
    THUMBS.write_text(json.dumps(sorted(thumbs), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print(f"{len(todo)} uploaded, {len(have)} were there")


def text_of(m):
    """The mail's own text as HTML, without the mail it quotes (Gmail's "On … wrote:" block, Thunderbird's cite).
    shortcut: only Gmail's and Thunderbird's quote markup is known; another client's quote stays in the post."""
    body = m.get_body(("html", "plain"))
    if body is None:
        return ""
    if body.get_content_type() == "text/plain":
        lines = body.get_content().splitlines()
        cut = next((i for i, l in enumerate(lines) if re.match(r"On .+ wrote:$", l.strip()) or l.startswith(">")), len(lines))
        return "<br>".join(escape(l) for l in lines[:cut]).strip()
    soup = BeautifulSoup(body.get_content(), "html.parser")
    # A Gmail quote has its "On … wrote:" line (gmail_attr); a gmail_quote without one is text pasted from another mail.
    for q in soup.select(".gmail_quote"):
        if q.find(class_="gmail_attr", recursive=False):
            q.decompose()
    for q in soup.select(".moz-cite-prefix, blockquote[type=cite]"):
        q.decompose()
    return str(soup).strip()


def unique(name, taken):
    """name, or "name (2).ext", "name (3).ext"…: two attachments of a mail can share a name (Gmail's inline image.png)."""
    stem, dot, ext = name.rpartition(".") if "." in name else (name, "", "")
    n = 1
    while name in taken:
        n += 1
        name = f"{stem} ({n}){dot}{ext}"
    return name


def add(folder, page):
    MAIL.mkdir(exist_ok=True)
    added = 0
    for path in sorted(Path(folder).glob("*.eml")):
        m = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        mid = str(m["Message-ID"] or "").strip() or sys.exit(f"{path.name}: no Message-ID")
        key = hashlib.sha1(mid.encode()).hexdigest()[:8]
        if any(MAIL.glob(f"*-{key}")):
            continue
        sent = parsedate_to_datetime(m["Date"])
        out = MAIL / f"{sent.astimezone(timezone.utc):%Y-%m-%d}-{key}"
        out.mkdir()
        files = []
        for a in m.iter_attachments():
            # The file's own name only: a name with a path or a drive cannot write outside the folder.
            name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", a.get_filename() or f"prilog-{len(files) + 1}").strip(" .") or "prilog"
            # A mail goes to a class only: a results list or roster has its students' names and index numbers blacked
            # out (common.redact_students), or is not published when it cannot be.
            data, why = redact_students(name, a.get_payload(decode=True) or b"")
            if why:
                print(f"  {path.name}: {name}: {why}")
            if data is None:
                continue
            name = unique(name, files)
            (out / name).write_bytes(data)
            files.append(name)
        refs = list(dict.fromkeys(re.findall(r"<[^>]+>", f"{m['References'] or ''} {m['In-Reply-To'] or ''}")))
        post = dict(
            id=mid,
            refs=refs,
            page=page,
            author=parseaddr(str(m["From"]))[1].split("@")[0].lower(),
            posted=sent.astimezone(timezone.utc).isoformat(),
            when=f"{sent:%d.%m.%Y. %H:%M}",
            title=str(m["Subject"] or ""),
            html=text_of(m),
            files=files,
            sizes={f: (out / f).stat().st_size for f in files},
        )
        (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
        added += 1
    print(f"{added} mails added to {MAIL}")


if __name__ == "__main__":
    if sys.argv[1:] == ["upload"]:
        upload()
    elif len(sys.argv) == 4 and sys.argv[1] == "add" and re.fullmatch(r"/predmet/[^/]+/[^/]+/", sys.argv[3]):
        add(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
