# /// script
# requires-python = ">=3.11"
# dependencies = ["pywebpush", "requests"]
# ///
"""The asserts of ci/push.py (were its __main__ block), no network: uv run test/push_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ci"))
import push  # noqa: E402
from push import PUSH_HOST, SITE, deliver, fcm_body, fcm_gone, message, nove, wait_url, wanted  # noqa: E402

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
_b = "/predmet/a/b/"
_p = [dict(s=_b, n="Биофизика", t="Резултати", u="/item/p9/"), dict(s=_b, n="Биофизика", t="Испит", u="/tema/3/#p2")]
assert message(_p[:1]) == dict(title="Биофизика", body="Резултати", url=SITE + "/item/p9/")
# Of one subject: its page; of several: the home page.
assert message(_p) == dict(title="Биофизика", body="2 nove objave: Резултати, Испит", url=SITE + _b)
assert message(_p * 2 + [dict(_p[0], t="A"), dict(_p[0], t="B")])["body"] == "6 novih objava: Резултати, Испит, A i još 1"
_x = dict(s="/predmet/a/c/", n="Хемија", t="X", u="/item/p8/")
assert message([*_p, _x]) == dict(title="3 nove objave", body="Биофизика, Хемија", url=SITE + "/")
assert wait_url([dict(k="s", id=3, u="/predmet/a/b/cent/x/"), dict(id=9, u="/tema/3/#p9")]) == SITE + "/item/p9/"
assert wait_url([dict(k="c", id=4, u="/item/c4/")]) == SITE + "/item/c4/" and wait_url([dict(k="s", id=3, u="/x/")]) is None
_s = dict(s=["/predmet/a/b/"], t={"/predmet/a/b/": ["pera"]})
assert wanted(_s, dict(s="/predmet/a/b/", a="pera")) and not wanted(_s, dict(s="/predmet/a/b/", a="mika"))
assert wanted(_s, dict(s="/predmet/a/b/")) and wanted(dict(s=_s["s"]), dict(s="/predmet/a/b/", a="mika"))
# A student's post: in a picked teacher's thread, or one no teacher posted in, yes; in another teacher's, no.
assert wanted(_s, dict(s="/predmet/a/b/", ta=["mika", "pera"])) and wanted(_s, dict(s="/predmet/a/b/", ta=[]))
assert not wanted(_s, dict(s="/predmet/a/b/", ta=["mika"]))
assert PUSH_HOST.match("https://fcm.googleapis.com/fcm/send/x") and not PUSH_HOST.match("https://evil.com/fcm.googleapis.com/")

# The Android app's subscriptions ("fcm:<token>"), through FCM: the message, a gone token dropped, a failure counted.
_m = message(_p[:1])
assert fcm_body("tok", _m) == {"message": {"token": "tok", "notification": {"title": "Биофизика", "body": "Резултати"},
                                           "data": {"url": SITE + "/item/p9/"}, "android": {"ttl": "86400s"}}}
_unreg = {"error": {"message": "x", "details": [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}]}}
assert fcm_gone(404, _unreg) and fcm_gone(400, {"error": {"message": "The registration token is not a valid FCM registration token"}})
assert not fcm_gone(500, {"error": {"message": "internal"}}) and not fcm_gone(400, {"error": {"message": "bad title"}}) and not fcm_gone(503, None)


class _R:
    def __init__(self, status, body=None):
        self.status_code, self.ok, self._body = status, status < 300, body
        self.headers = {"Content-Type": "application/json"} if body is not None else {}
        self.text = str(body)

    def json(self):
        return self._body


_drops, _got = [], []
push.requests.post = lambda url, json, timeout: _drops.append(json)
_answers = {"a" * 150: _R(200, {}), "b" * 150: _R(404, _unreg), "c" * 150: _R(500, {"error": {"message": "internal"}})}
_fcm = lambda token, msg: (_got.append((token, msg)), _answers[token])[1]
_subs = [{"endpoint": "fcm:" + t, "s": ["/predmet/a/b/"]} for t in _answers] + [{"endpoint": "fcm:" + "d" * 150, "s": ["/predmet/x/y/"]}]
_by = {"/predmet/a/b/": [dict(s="/predmet/a/b/", n="Биофизика", t="Резултати", u="/item/p9/")]}
assert deliver(_subs, _by, "vapid", _fcm) == (1, 1, 1, 0)  # the one following another subject gets nothing
assert [t for t, _ in _got] == ["a" * 150, "b" * 150, "c" * 150] and _got[0][1] == _m
assert _drops == [{"fcm": "b" * 150, "s": []}]
assert deliver(_subs, _by, "vapid", None) == (0, 0, 0, 3)  # no fcm-secret.json: skipped, not failed
