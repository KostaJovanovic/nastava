# /// script
# requires-python = ">=3.11"
# dependencies = ["pywebpush", "requests"]
# ///
"""Web push: tell the browsers that follow a subject (site.js subscribes, the Worker keeps them in KV) about its new posts.

Usage: push.py keys | last | send <post id>
  keys   make push-secret.json (git-ignored): the VAPID key pair and the key the Worker asks for. Keep a copy: a new
         pair drops every subscription. Prints where the public half and the Worker key go.
  last   print the newest post id in nastava.db (deploy.sh: before the scrape)
  send   once the newest is on the site, notify the posts after that id (pages/.build/push.json, from build.py)
shortcut: the secret is a file on this PC; when the daily run moves to Actions, make it a repository secret.
"""
import base64
import json
import re
import secrets
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from pywebpush import WebPushException, webpush

ROOT = Path(__file__).resolve().parent.parent
SECRET = ROOT / "push-secret.json"
SITE = "https://nastava.valjdakosta.com"
# As the Worker's PUSH_HOST: only the browsers' push services get a request.
PUSH_HOST = re.compile(r"^https://([a-z0-9-]+\.)*(fcm\.googleapis\.com|push\.services\.mozilla\.com|push\.apple\.com|notify\.windows\.com)/")


def nove(n):
    """'1 nova objava', '3 nove objave', '5 novih objava'."""
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} nova objava"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} nove objave"
    return f"{n} novih objava"


def message(posts):
    """One notification for a browser: one post opens itself; more open the home page, which lists the followed
    subjects' newest topics."""
    if len(posts) == 1:
        p = posts[0]
        return dict(title=p["n"], body=p["t"], url=SITE + p["u"])
    names = list(dict.fromkeys(p["n"] for p in posts))
    return dict(title=nove(len(posts)), body=", ".join(names), url=SITE + "/")


def keys():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    if SECRET.exists():
        sys.exit(f"{SECRET.name} exists: a new pair would drop every subscription")
    k = ec.generate_private_key(ec.SECP256R1())
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    public = b64(k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    SECRET.write_text(json.dumps(dict(vapid=b64(k.private_numbers().private_value.to_bytes(32, "big")), public=public,
                                      key=secrets.token_urlsafe(32)), indent=1))
    print(f"wrote {SECRET.name}\npublic key (PUSH_PUBLIC in pages/static/site.js): {public}\n"
          "Worker key: cd pages && npx wrangler secret put PUSH_KEY  (paste the \"key\" of push-secret.json)")


def last():
    db = sqlite3.connect(f"file:{ROOT / 'nastava.db'}?mode=ro", uri=True)
    print(db.execute("select coalesce(max(id), 0) from posts").fetchone()[0])


def subscriptions(key):
    subs, cursor = [], None
    while True:
        r = requests.get(f"{SITE}/push/subs", params={"cursor": cursor} if cursor else None,
                         headers={"Authorization": f"Bearer {key}"}, timeout=60)
        r.raise_for_status()
        j = r.json()
        subs += j["subs"]
        if not (cursor := j["cursor"]):
            return subs


def send(before):
    if before <= 0:
        sys.exit("no post id from before the scrape")
    secret = json.loads(SECRET.read_text())
    new = [p for p in json.loads((ROOT / "pages/.build/push.json").read_text(encoding="utf-8")) if p["id"] > before]
    if not new:
        print("push: no new posts")
        return
    # The deploy workflow publishes a few minutes after deploy.sh starts it: wait for the newest post's page.
    newest = f"{SITE}/item/p{max(p['id'] for p in new)}/"
    for _ in range(40):
        if requests.head(newest, timeout=30).status_code == 200:
            break
        time.sleep(30)
    else:
        sys.exit(f"push: {newest} is not on the site after 20 minutes")
    by_subject = defaultdict(list)
    for p in sorted(new, key=lambda p: p["id"]):
        by_subject[p["s"]].append(p)
    sent = gone = failed = 0
    for sub in subscriptions(secret["key"]):
        posts = [p for s in dict.fromkeys(sub.get("s", [])) for p in by_subject.get(s, [])]
        if not posts or not PUSH_HOST.match(sub["endpoint"]):
            continue
        try:
            # A new claims dict each time: pywebpush stores the push service's origin ("aud") in it.
            webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["k"], "auth": sub["a"]}},
                    json.dumps(message(posts), ensure_ascii=False), vapid_private_key=secret["vapid"],
                    vapid_claims={"sub": SITE}, ttl=86400, timeout=30)
            sent += 1
        except WebPushException as e:
            # The browser unsubscribed or the subscription expired: drop it as the browser would.
            if e.response is not None and e.response.status_code in (404, 410):
                requests.post(f"{SITE}/push", json={"endpoint": sub["endpoint"], "s": []}, timeout=30)
                gone += 1
            else:
                failed += 1
                print("push failed:", e, file=sys.stderr)
    print(f"push: {len(new)} new posts; {sent} sent, {gone} gone, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    assert [nove(n) for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)] == [
        "1 nova objava", "2 nove objave", "5 novih objava", "11 novih objava", "12 novih objava", "21 nova objava",
        "22 nove objave", "25 novih objava", "111 novih objava"]
    _p = [dict(n="Биофизика", t="Резултати", u="/item/p9/"), dict(n="Биофизика", t="Испит", u="/tema/3/#p2")]
    assert message(_p[:1]) == dict(title="Биофизика", body="Резултати", url=SITE + "/item/p9/")
    assert message(_p) == dict(title="2 nove objave", body="Биофизика", url=SITE + "/")
    assert PUSH_HOST.match("https://fcm.googleapis.com/fcm/send/x") and not PUSH_HOST.match("https://evil.com/fcm.googleapis.com/")
    match sys.argv[1:]:
        case ["keys"]:
            keys()
        case ["last"]:
            last()
        case ["send", n]:
            send(int(n))
        case _:
            sys.exit(__doc__)
