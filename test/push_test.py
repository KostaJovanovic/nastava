# /// script
# requires-python = ">=3.11"
# dependencies = ["pywebpush", "requests"]
# ///
"""The asserts of ci/push.py (were its __main__ block), no network: uv run test/push_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ci"))
from push import PUSH_HOST, SITE, message, nove, wait_url, wanted  # noqa: E402

assert [nove(n) for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)] == [
    "1 nova objava",
    "2 nove objave",
    "5 novih objava",
    "11 novih objava",
    "12 novih objava",
    "21 nova objava",
    "22 nove objave",
    "25 novih objava",
    "111 novih objava",
]
_p = [dict(n="Биофизика", t="Резултати", u="/item/p9/"), dict(n="Биофизика", t="Испит", u="/tema/3/#p2")]
assert message(_p[:1]) == dict(title="Биофизика", body="Резултати", url=SITE + "/item/p9/")
assert message(_p) == dict(title="2 nove objave", body="Биофизика", url=SITE + "/")
assert wait_url([dict(k="s", id=3, u="/predmet/a/b/cent/x/"), dict(id=9, u="/tema/3/#p9")]) == SITE + "/item/p9/"
assert wait_url([dict(k="c", id=4, u="/item/c4/")]) == SITE + "/item/c4/" and wait_url([dict(k="s", id=3, u="/x/")]) is None
_s = dict(s=["/predmet/a/b/"], t={"/predmet/a/b/": ["pera"]})
assert wanted(_s, dict(s="/predmet/a/b/", a="pera")) and not wanted(_s, dict(s="/predmet/a/b/", a="mika"))
assert wanted(_s, dict(s="/predmet/a/b/")) and wanted(dict(s=_s["s"]), dict(s="/predmet/a/b/", a="mika"))
assert PUSH_HOST.match("https://fcm.googleapis.com/fcm/send/x") and not PUSH_HOST.match("https://evil.com/fcm.googleapis.com/")
