# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf", "numpy", "tzdata"]
# ///
"""The runs' log (ci/deploy.sh, here and on GitHub), and the schedule (sync.yml) against when posts appear.

Usage: runs.py snap | save EXIT ARGS... | report [--last N] [--file runs.jsonl] | schedule [--since DATE] [--delay MIN]
  snap      (deploy.sh, after the state pull) what the database holds before the scrape: RUN_DIR/before.json
  save      (deploy.sh, at its end) this run's line, from what RUN_DIR gathered: the steps' times (steps.tsv), every
            request (requests.jsonl, nastava.instrument), what is new since snap, the notifications (push.py), the
            sizes, and on GitHub how late the run started; appended to runs.jsonl on the "runs" release, and on
            GitHub the run page's summary
  report    the log: GitHub's delay, the steps, the scrapers and sites, which runs found something, how long a post
            waits to be found and to be on the site, the sizes, the notifications; GitHub's runs apart from local ones
  schedule  replay the board's posts since --since (default 2022-10-01, UTC times) against the schedule in use and
            against the best 2–6 runs a day for each season (hot: registration, an exam period and the 7 days after
            it; quiet: the rest; plan.py hot); --delay: minutes GitHub starts a run late, added to every run. The
            candidates are every hour's :52, as sync.yml. Times in UTC and in Belgrade (winter +1, summer +2).
"""

import bisect
import datetime as dt
import itertools
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan  # noqa: E402

DB = Path(os.getenv("DB", plan.ROOT / "nastava.db"))
BG = ZoneInfo("Europe/Belgrade")
# The schedule in use (pages/wrangler.toml crons, src/index.js SLOTS): UTC minute of day -> its slot, every day.
NOW = {6 * 60 + 17: "morning", 10 * 60 + 17: "noon", 14 * 60 + 17: "afternoon", 18 * 60 + 17: "evening", 21 * 60 + 17: "late"}
BIN = 10  # minutes: the optimizer's histogram


def hhmm(m):
    """UTC minute of day -> '05:52 UTC (6:52/7:52)': Belgrade in winter and in summer."""
    m %= 1440
    return f"{m // 60:02}:{m % 60:02} UTC ({(m // 60 + 1) % 24}:{m % 60:02}/{(m // 60 + 2) % 24}:{m % 60:02})"


def seasons(db):
    """A date -> 'hot' or 'quiet', as plan.py plans a run (by the UTC date); a year without a calendar uses the
    nearest one's dates (plan.for_year)."""
    cals, wins = plan.calendars(db), {}

    def season(d):
        y = plan.school_year(d)
        if y not in wins:
            wins[y] = plan.for_year(cals, y)
        return "hot" if plan.hot(d, wins[y]) else "quiet"

    return season


def load(db, since, season):
    """[(UTC datetime, season)] of the board's posts since `since`, by time."""
    out = []
    for (p,) in db.execute("select posted from posts where posted >= ? order by posted", (since,)):
        t = dt.datetime.fromisoformat(p).astimezone(dt.timezone.utc)
        out.append((t, season(t.date())))
    return out


def run_times(first, last, sched, season, delay=0):
    """Every run from the day before `first` to the day after `last`: [(UTC datetime, slot, season of its day)].
    sched: {'hot': [minutes], 'quiet': [minutes]}; a run's day is its UTC date (the night run, after midnight UTC,
    plans with the new day, as plan.py does)."""
    out = []
    d = first.date() - dt.timedelta(days=1)
    while d <= last.date() + dt.timedelta(days=1):
        s = season(d)
        for m in sched[s]:
            t = dt.datetime.combine(d, dt.time(m // 60, m % 60), dt.timezone.utc) + dt.timedelta(minutes=delay)
            out.append((t, NOW.get(m, f"{m // 60:02}:{m % 60:02}"), s))
        d += dt.timedelta(days=1)
    return sorted(out)


def replay(posts, runs):
    """Each post's wait in minutes until the first run after it, and per run whether it found any post:
    ([(wait, season of the post)], Counter((slot, season) -> runs), Counter((slot, season) -> runs with a post))."""
    times = [r[0] for r in runs]
    waits, found = [], set()
    for t, s in posts:
        i = bisect.bisect_left(times, t)
        if i == len(times):
            continue
        waits.append(((times[i] - t).total_seconds() / 60, s))
        found.add(i)
    span = (posts[0][0], posts[-1][0])
    total, useful = Counter(), Counter()
    for i, (t, slot, s) in enumerate(runs):
        if span[0] <= t <= span[1]:
            total[slot, s] += 1
            useful[slot, s] += i in found
    return waits, total, useful


def stats(ws):
    """Minutes -> 'mean 2h05, median 1h40, 95% within 4h30, 62% within 3h'."""
    if not ws:
        return "no posts"
    a = np.sort(np.array(ws))
    f = lambda m: f"{int(m // 60)}h{int(m % 60):02}"
    return f"mean {f(a.mean())}, median {f(np.median(a))}, 95% within {f(np.percentile(a, 95))}, {(a <= 180).mean():.0%} within 3h"


def best(posts, season, n, delay=0, top=3):
    """The best n run times a day for the posts of a season, from every hour's :52, by the mean wait: [(mean minutes,
    [minutes])]. On a histogram of the minute of day (BIN), each run's next as the same season's (a shortcut: a
    season's last run of the day waits for the next day's first)."""
    hist = np.zeros(1440 // BIN)
    for t, s in posts:
        if s == season:
            hist[(t.hour * 60 + t.minute) // BIN] += 1
    cands = np.array([(h * 60 + 52 + delay) % 1440 for h in range(24)])
    centers = np.arange(1440 // BIN) * BIN + BIN / 2
    dist = (cands[None, :] - centers[:, None]) % 1440  # bins x candidates: minutes to that run
    res = []
    combos = np.array(list(itertools.combinations(range(24), n)))
    for chunk in np.array_split(combos, max(1, len(combos) // 5000)):
        w = dist[:, chunk].min(axis=2)  # bins x combos
        res.append(hist @ w / hist.sum())
    res = np.concatenate(res)
    order = np.argsort(res)[:top]
    return [(res[i], [int(cands[j]) - delay for j in combos[i]]) for i in order]


def schedule(since, delay):
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    season = seasons(db)
    posts = load(db, since, season)
    if not posts:
        sys.exit(f"no posts since {since}")
    per = Counter(s for _, s in posts)
    days = Counter(season(posts[0][0].date() + dt.timedelta(days=i)) for i in range((posts[-1][0].date() - posts[0][0].date()).days + 1))
    print(
        f"{len(posts)} posts since {since}: {per['hot']} on {days['hot']} hot days "
        f"({per['hot'] / max(days['hot'], 1):.1f} a day), {per['quiet']} on {days['quiet']} quiet days "
        f"({per['quiet'] / max(days['quiet'], 1):.1f} a day)\n"
    )

    # When posts appear (Belgrade time): the share per hour, per season.
    print("Posts by hour, Belgrade time (% of the season's posts):")
    for s in ("hot", "quiet"):
        h = Counter(t.astimezone(BG).hour for t, x in posts if x == s)
        n = sum(h.values()) or 1
        print(f"  {s:5} " + " ".join(f"{x:02}:{100 * h[x] / n:4.1f}" for x in range(24)))
    wd = Counter((t.astimezone(BG).weekday(), s) for t, s in posts)
    print(
        "Posts by weekday (Mon..Sun), hot | quiet: "
        + " ".join(f"{wd[d, 'hot']}" for d in range(7))
        + " | "
        + " ".join(f"{wd[d, 'quiet']}" for d in range(7))
    )
    mon = Counter(t.astimezone(BG).month for t, _ in posts)
    print("Posts by month (Jan..Dec): " + " ".join(str(mon[m]) for m in range(1, 13)) + "\n")

    cur = {"hot": sorted(NOW), "quiet": sorted(NOW)}
    runs = run_times(posts[0][0], posts[-1][0], cur, season, delay)
    waits, total, useful = replay(posts, runs)
    print(f"The schedule in use (+{delay} min GitHub delay):")
    for s in ("hot", "quiet"):
        print(f"  {s:5} {len(cur[s])} runs: {stats([w for w, x in waits if x == s])}")
    print("  runs that found a post (since the run before):")
    for (slot, s), n in sorted(total.items(), key=lambda x: (x[0][1], x[0][0])):
        print(f"    {s:5} {slot:9} {useful[slot, s]}/{n} = {useful[slot, s] / n:.0%}")

    print("\nThe best n runs a day (mean wait; every hour's :52):")
    for s in ("hot", "quiet"):
        for n in range(2, 7):
            for i, (mean, ms) in enumerate(best(posts, s, n, delay, top=1)):
                exact = run_times(posts[0][0], posts[-1][0], {**cur, s: sorted(ms)}, season, delay)
                w, _, _ = replay(posts, exact)
                print(f"  {s:5} {n}: {', '.join(hhmm(m) for m in sorted(ms))}\n           {stats([x for x, y in w if y == s])}")


# ---- The run log ----------------------------------------------------------------------------------------------------
REPO = os.getenv("GITHUB_REPOSITORY", "KostaJovanovic/nastava")
RUN_DIR = Path(os.getenv("RUN_DIR") or ".")
# What a scraper adds: a new row (a post, a page's new version) has a rowid above the snapshot's.
TABLES = [
    "posts",
    "vesti",
    "cent_notices",
    "cent_pages",
    "katedre_pages",
    "study_pages",
    "study_files",
    "teachers",
    "subjects",
    "wiki_pages",
    "departments",
]
UTC = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
iso = lambda t: t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def max_rowids(db):
    out = {}
    for t in TABLES:
        try:
            out[t] = db.execute(f"select max(rowid) from {t}").fetchone()[0] or 0
        except sqlite3.OperationalError:  # a scraper that has not run yet
            out[t] = 0
    return out


def snap():
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    (RUN_DIR / "before.json").write_text(json.dumps(dict(at=iso(dt.datetime.now(dt.timezone.utc)), rows=max_rowids(db))))


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")


def github():
    """On GitHub: when the run was due (its cron, CRON), created, and its job started: the delay GitHub adds."""
    if not os.getenv("GITHUB_RUN_ID"):
        return None
    out = dict(run=int(os.environ["GITHUB_RUN_ID"]))
    r = gh("run", "view", os.environ["GITHUB_RUN_ID"], "-R", REPO, "--json", "createdAt,jobs")
    if r.returncode == 0:
        j = json.loads(r.stdout)
        created = UTC(j["createdAt"])
        out["created"] = iso(created)
        if j["jobs"] and j["jobs"][0].get("startedAt"):
            out["job_started"] = j["jobs"][0]["startedAt"]
        if cron := os.getenv("CRON"):  # "52 10 * * *": the last time it was due, at or before the run was made
            m, h = map(int, cron.split()[:2])
            due = created.replace(hour=h, minute=m, second=0, microsecond=0)
            if due > created:
                due -= dt.timedelta(days=1)
            out["due"] = iso(due)
    return out


def scrapers(path):
    """requests.jsonl -> {scraper: {requests, seconds (network), bytes, retries, errors {status: n}, slowest
    [[s, url]], hosts {host: {n, s, errors, etag, modified}}}}: an error is a status 4xx/5xx or a failed request."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        x = out.setdefault(r["scraper"], dict(requests=0, seconds=0.0, bytes=0, retries=0, errors={}, slowest=[], hosts={}))
        h = x["hosts"].setdefault(r["host"], dict(n=0, s=0.0, errors=0, etag=0, modified=0))
        bad = not isinstance(r["status"], int) or r["status"] >= 400
        x["requests"] += 1
        x["seconds"] += r["s"]
        x["bytes"] += r.get("bytes", 0)
        x["retries"] += r.get("retries", 0)
        h["n"] += 1
        h["s"] += r["s"]
        h["errors"] += bad
        h["etag"] += bool(r.get("etag"))
        h["modified"] += bool(r.get("modified"))
        if bad:
            x["errors"][str(r["status"])] = x["errors"].get(str(r["status"]), 0) + 1
        x["slowest"] = sorted(x["slowest"] + [[r["s"], r["url"]]], reverse=True)[:10]
    for x in out.values():
        x["seconds"] = round(x["seconds"], 1)
        for h in x["hosts"].values():
            h["s"] = round(h["s"], 1)
    return out


def steps(path):
    """steps.tsv (deploy.sh step: name, start, end, exit) -> [{name, start, s, rc}]."""
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, a, b, rc = line.split("\t")
            out.append(
                dict(
                    name=name, start=iso(dt.datetime.fromtimestamp(float(a), dt.timezone.utc)), s=round(float(b) - float(a), 1), rc=int(rc)
                )
            )
    return out


def found(db, before, at):
    """What the scrape added since snap: new rows per table, katedre's per site, and each new board post's minutes
    from posted to found (`at`, when nastava.py ended), the posts of the last 7 days only (an older one is an edit or
    a topic fetched late)."""
    after = max_rowids(db)
    new = {t: after[t] - before.get(t, 0) for t in TABLES if after[t] > before.get(t, 0)}
    out = dict(new=new)
    if new.get("katedre_pages"):
        out["katedre"] = dict(
            db.execute("select site, count(*) from katedre_pages where rowid > ? group by site", (before["katedre_pages"],))
        )
    waits = []
    for (p,) in db.execute("select posted from posts where rowid > ?", (before.get("posts", 0),)):
        m = (at - UTC(p)).total_seconds() / 60
        if 0 <= m <= 7 * 1440:
            waits.append(round(m))
    out["post_waits"] = sorted(waits)[:500]
    return out


def size(p):
    p = Path(p)
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else None


def save(code, args):
    """This run's line: see the module's doc. Never fails the run: a log that cannot be saved is a warning."""
    now = dt.datetime.now(dt.timezone.utc)
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    st = steps(RUN_DIR / "steps.tsv")
    before = json.loads((RUN_DIR / "before.json").read_text()) if (RUN_DIR / "before.json").exists() else None
    plan_line = (RUN_DIR / "plan.txt").read_text().strip() if (RUN_DIR / "plan.txt").exists() else None
    today = now.date()
    entry = dict(
        v=1,
        started=st[0]["start"] if st else iso(now),
        ended=iso(now),
        where="github" if os.getenv("GITHUB_ACTIONS") else "local",
        commit=subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
        args=args,
        plan=plan_line,
        season=seasons(db)(today),
        weekday=today.weekday(),
        exit=int(code),
        failed=(RUN_DIR / "failed.txt").read_text().split() if (RUN_DIR / "failed.txt").exists() else [],
        github=github(),
        steps=st,
        scrapers=scrapers(RUN_DIR / "requests.jsonl"),
    )
    if before:
        nastava_end = next((s for s in st if s["name"] == "nastava"), None)
        at = UTC(nastava_end["start"]) + dt.timedelta(seconds=nastava_end["s"]) if nastava_end else now
        entry["found"] = found(db, before["rows"], at)
    if (RUN_DIR / "push.json").exists():
        entry["push"] = push = json.loads((RUN_DIR / "push.json").read_text())
        if push.get("live") and entry.get("found"):
            # posted -> on the site: the wait to be found plus found -> live.
            extra = (UTC(push["live"]) - at).total_seconds() / 60
            entry["found"]["post_live"] = [round(w + extra) for w in entry["found"]["post_waits"]]
    site = plan.ROOT / "pages" / ".build" / "site"
    entry["sizes"] = dict(
        db=size(DB),
        site_tar=int((RUN_DIR / "site_tar").read_text()) if (RUN_DIR / "site_tar").exists() else None,
        state=int((RUN_DIR / "state").read_text()) if (RUN_DIR / "state").exists() else None,
        pages=sum(1 for _ in site.rglob("index.html")) if site.exists() else None,
        pagefind=size(site / "pagefind"),
    )
    entry["down"] = sorted(h for x in entry["scrapers"].values() for h, v in x["hosts"].items() if v["errors"] == v["n"])
    line = json.dumps(entry, ensure_ascii=False)
    (RUN_DIR / "run.json").write_text(line, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary(entry))
    # Append to runs.jsonl on the "runs" release.
    # shortcut: download, append, upload: a local run and a GitHub run ending in the same minute can lose one line;
    # a lock (or one asset per run) if that ever matters.
    d = Path(tempfile.mkdtemp())
    if gh("release", "view", "runs", "-R", REPO).returncode:
        gh(
            "release",
            "create",
            "runs",
            "-R",
            REPO,
            "--latest=false",
            "--title",
            "runs",
            "--notes",
            "The scrape runs' log (ci/runs.py): one JSON line a run.",
        )
    gh("release", "download", "runs", "-R", REPO, "-p", "runs.jsonl", "-D", str(d))
    with open(d / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    r = gh("release", "upload", "runs", "-R", REPO, str(d / "runs.jsonl"), "--clobber")
    print("run log saved" if r.returncode == 0 else f"run log not saved: {r.stderr.strip()}", file=sys.stderr)


def mins(s):
    return f"{int(s // 60)}m{int(s % 60):02}s" if s >= 60 else f"{s:.0f}s"


def summary(e):
    """The run page's summary on GitHub (markdown)."""
    g = e.get("github") or {}
    out = [
        f"### Run {e['started']} · {e['plan'] or ' '.join(e['args'])} · {e['season']} · exit {e['exit']}"
        + (f" · failed: {', '.join(e['failed'])}" if e["failed"] else ""),
        "",
    ]
    if g.get("due") and g.get("created"):
        out.append(
            f"GitHub started it {mins((UTC(g['created']) - UTC(g['due'])).total_seconds())} late"
            + (
                f"; setup {mins((UTC(e['steps'][0]['start']) - UTC(g['job_started'])).total_seconds())}"
                if g.get("job_started") and e["steps"]
                else ""
            )
            + ".\n"
        )
    out += ["| step | time | exit |", "|---|---:|---:|"] + [f"| {s['name']} | {mins(s['s'])} | {s['rc']} |" for s in e["steps"]]
    if e["scrapers"]:
        out += ["", "| scraper | requests | network | MB | errors | retries |", "|---|---:|---:|---:|---|---:|"]
        out += [
            f"| {k} | {x['requests']} | {mins(x['seconds'])} | {x['bytes'] / 1e6:.1f} | {x['errors'] or ''} | {x['retries']} |"
            for k, x in e["scrapers"].items()
        ]
    f = e.get("found") or {}
    if f.get("new"):
        out += ["", "New: " + ", ".join(f"{k} {n}" for k, n in f["new"].items())]
    if f.get("post_waits"):
        out.append(f"Posts found after {stats(f['post_waits'])}.")
    if e.get("down"):
        out.append(f"No answer: {', '.join(e['down'])}.")
    return "\n".join(out) + "\n"


def report(last, file):
    if file:
        lines = Path(file).read_text(encoding="utf-8").splitlines()
    else:
        d = Path(tempfile.mkdtemp())
        if gh("release", "download", "runs", "-R", REPO, "-p", "runs.jsonl", "-D", str(d)).returncode:
            sys.exit("no run log yet (the runs release)")
        lines = (d / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    runs = [json.loads(x) for x in lines if x.strip()][-last:]
    print(f"{len(runs)} runs, {runs[0]['started']} to {runs[-1]['started']}")
    pct = lambda a, q: float(np.percentile(a, q)) if a else 0
    for where in ("github", "local"):
        rs = [r for r in runs if r["where"] == where]
        if not rs:
            continue
        print(
            f"\n== {where}: {len(rs)} runs, {sum(r['exit'] != 0 for r in rs)} red"
            + (
                f" ({', '.join(f'{k} {n}' for k, n in Counter(f for r in rs for f in r['failed']).most_common())})"
                if any(r["failed"] for r in rs)
                else ""
            )
        )
        late = [
            (UTC(r["github"]["created"]) - UTC(r["github"]["due"])).total_seconds() / 60 for r in rs if (r.get("github") or {}).get("due")
        ]
        if late:
            print(f"GitHub's delay: median {pct(late, 50):.0f} min, 90% within {pct(late, 90):.0f}, worst {max(late):.0f}")
        # Setup: the job's start to deploy.sh's first step (checkout, uv, the push keys).
        setup = [
            (UTC(r["steps"][0]["start"]) - UTC(r["github"]["job_started"])).total_seconds()
            for r in rs
            if (r.get("github") or {}).get("job_started") and r["steps"]
        ]
        if setup:
            print(f"GitHub's setup before the first step: median {mins(pct(setup, 50))}, worst {mins(max(setup))}")
        print("Steps (median / worst):")
        by = defaultdict(list)
        for r in rs:
            for s in r["steps"]:
                by[s["name"]].append(s["s"])
        for k, v in by.items():
            print(f"  {k:12} {mins(pct(v, 50)):>7} / {mins(max(v)):>7}  ({len(v)} runs)")
        print("Scrapers (median requests, network time; errors and retries in all runs):")
        sc = defaultdict(list)
        for r in rs:
            for k, x in r["scrapers"].items():
                sc[k].append(x)
        for k, xs in sc.items():
            err = Counter()
            for x in xs:
                err.update(x["errors"])
            print(
                f"  {k:12} {pct([x['requests'] for x in xs], 50):5.0f} req, {mins(pct([x['seconds'] for x in xs], 50)):>7}"
                f", {sum(x['retries'] for x in xs)} retries, errors {dict(err) or 0}"
            )
        hosts = defaultdict(lambda: Counter())
        for r in rs:
            for x in r["scrapers"].values():
                for h, v in x["hosts"].items():
                    hosts[h].update(v)
        print("Sites (requests, mean s, errors, ETag, Last-Modified):")
        for h, v in sorted(hosts.items(), key=lambda x: -x[1]["n"]):
            print(
                f"  {h:28} {v['n']:6} {v['s'] / v['n']:5.2f}s {v['errors'] / v['n']:5.1%} err "
                f"{v['etag'] / v['n']:4.0%} etag {v['modified'] / v['n']:4.0%} modified"
            )
        down = Counter(h for r in rs for h in r.get("down", []))
        if down:
            print("Did not answer (runs): " + ", ".join(f"{h} {n}" for h, n in down.most_common()))
        print("Runs that found something (slot, season: new posts / any new row):")
        use = defaultdict(lambda: [0, 0, 0])
        for r in rs:
            a = r["args"]  # a scheduled run by its slot ("auto noon"), another by its kind ("forum", "sync")
            key = (a[1] if a[:1] == ["auto"] and len(a) > 1 else a[0] if a else "build", r["season"])
            n = (r.get("found") or {}).get("new", {})
            use[key][0] += 1
            use[key][1] += bool(n.get("posts"))
            use[key][2] += bool(n)
        for (slot, season), (n, p, a) in sorted(use.items()):
            print(f"  {slot:9} {season:5} {p}/{n} posts, {a}/{n} anything")
        waits = [w for r in rs for w in (r.get("found") or {}).get("post_waits", [])]
        live = [w for r in rs for w in (r.get("found") or {}).get("post_live", [])]
        if waits:
            print(f"A post found after: {stats(waits)}")
        if live:
            print(f"A post on the site after: {stats(live)}")
        sz = [r["sizes"] for r in rs if r.get("sizes")]
        if sz:
            print(
                "Sizes, first -> last: "
                + ", ".join(
                    f"{k} {sz[0][k] / 1e6 if k != 'pages' else sz[0][k]:.0f} -> {sz[-1][k] / 1e6 if k != 'pages' else sz[-1][k]:.0f}"
                    for k in sz[0]
                    if sz[0][k] and sz[-1].get(k)
                )
                + " (MB; pages: count)"
            )
        ps = [r["push"] for r in rs if r.get("push")]
        if ps:
            subs = [p["subscribers"] for p in ps if "subscribers" in p]
            print(
                f"Notifications: {sum(p.get('sent', 0) for p in ps)} sent, {sum(p.get('gone', 0) for p in ps)} gone, "
                f"{sum(p.get('failed', 0) for p in ps)} failed" + (f"; subscribers {subs[0]} -> {subs[-1]}" if subs else "")
            )


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = lambda k, d: args[args.index(k) + 1] if k in args else d
    match args:
        case ["snap"]:
            snap()
        case ["save", code, *rest]:
            try:
                save(code, rest)
            except Exception as e:  # the log must not fail the run
                print(f"run log not saved: {type(e).__name__}: {e}", file=sys.stderr)
        case ["report", *_]:
            report(int(opt("--last", "100000")), opt("--file", None))
        case ["schedule", *_]:
            schedule(opt("--since", "2022-10-01"), int(opt("--delay", "0")))
        case _:
            sys.exit(__doc__)
