"""Where a subject's material lives besides the board (Teams, Drive, Moodle, ...), from the links in its posts."""

import re
from collections import Counter
from urllib.parse import urlsplit
from .known import ELSEWHERE, FILE_HOSTS, FOLDER


def service(url):
    """The service a link is on (ELSEWHERE), or a department's site (its host: 'ie.mas.bg.ac.rs'); None for others.
    Not material: a Google form (a survey or a test; 'spreadsheet/viewform' the old ones), a published sheet (exam
    results), a Teams meeting (one class online)."""
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    if host == "docs.google.com" and re.search(r"^/forms|/viewform|/pubhtml", u.path):
        return None
    if "/meetup-join/" in u.path:
        return None
    for name, rx in ELSEWHERE:
        if re.search(rx, host):
            return name
    if host.endswith(".mas.bg.ac.rs") and host.split(".")[0] not in ("nastava", "www", "vesti"):
        # A department's Moodle (mat, motori: /moodle; it0 and cs are only one): needs a login, as the others.
        return "Moodle" if u.path.lower().startswith("/moodle") or host.split(".")[0] in ("it0", "cs") else host
    return None


def mark_elsewhere(items):
    """Each subject's material elsewhere, from its posts' links: s["elsewhere"] = {name: dict(name, first, last, who,
    users)}: the first and newest post that links it, who links it (shown names, most posts first) and their usernames
    (a teacher's page shows their own). A subject's teachers often split it, and only some use a service.
    A file host needs a folder or playlist, or two links: one video or file is not the subject's place there."""
    for it in items:
        if it["kind"] != "post" or not it["subj"]:
            continue
        for url in set(re.findall(r'href="(https?://[^"]+)"', it["html"] or "")):
            if name := service(url):
                e = (
                    it["subj"]
                    .setdefault("elsewhere", {})
                    .setdefault(name, dict(name=name, first=it, last=it, by=Counter(), users=set(), urls=set()))
                )
                e["first"] = min(e["first"], it, key=lambda r: r["posted"])
                e["last"] = max(e["last"], it, key=lambda r: r["posted"])
                e["by"][it["who"]] += 1
                e["urls"].add(url)
                if it["teacher"]:
                    e["users"].add(it["teacher"]["username"])
    for s in {id(it["subj"]): it["subj"] for it in items if (it.get("subj") or {}).get("elsewhere")}.values():
        for name, e in list(s["elsewhere"].items()):
            if "by" not in e:
                continue
            e["who"] = [w for w, _ in e.pop("by").most_common()]
            if name in FILE_HOSTS and len(e["urls"]) < 2 and not any(re.search(FOLDER, u) for u in e["urls"]):
                del s["elsewhere"][name]
        if not s["elsewhere"]:
            del s["elsewhere"]
