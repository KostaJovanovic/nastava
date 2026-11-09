# Plan: the automatic update (scheduled sync on GitHub Actions)

Status: planned 2026-11-09, agreed with the user, not built. Instructions for the Claude that builds it: follow the steps
in order, copy the code as it is (it was tested against the real `nastava.db` and the real calendar PDF), run the
checks, commit. Do not redesign; if something here turns out wrong, stop and ask the user.

## Rules for this work (from the user)

- Commit locally without asking; commit messages 3–5 words. **Never push** (the user pushes), never run
  `wrangler deploy`, `ci/deploy.sh forum|sync`, or `gh workflow run` yourself: those publish.
- Files: Read/Edit/Write tools only, no `sed -i`, heredocs or redirects into files. Shell for git, uv, tests.
- Never write the word "corpus".
- Windows shell: Python prints `\r\n`, so `$(...)` keeps a `\r` (the code below strips it with `tr -d '\r'`); set
  `PYTHONIOENCODING=utf-8` for Cyrillic output; `python -I` ignores it.
- Other sessions edit this repo at the same time. Before committing, `git status`: commit only the files of this plan,
  never someone else's unstaged changes.

## What was decided

| # | Question | Decision |
|---|---|---|
| 1 | Where | GitHub Actions (`.github/workflows/sync.yml`), the same `ci/deploy.sh` as on the PC |
| 2 | How often | Hot days: 3 runs (noon, evening, night). Other days: 1 run (night). Times below. |
| 3 | Side scrapers | `studije.py` (schedule pages, exam schedules): the 1st of each month, the first day of each registration (prijave) and of each exam period (rok). `nastavnici.py` + `predmeti.py`: once a year, 1 October. |
| 4 | Nothing changed | Skip save, build, publish and push (compare a database fingerprint before and after the scrape) |
| 5 | PC override | Yes: `bash ci/deploy.sh forum` / `sync` / `forum studije` on the PC (it pulls the saved state first), or `gh workflow run sync.yml -f what=...` |
| 6 | Web push from Actions | Repository secret `PUSH_SECRET` = the content of `push-secret.json` |
| 7 | Failures | A red run → GitHub's e-mail (default) |

Hot day = a registration day, a day of an exam period, or one of the 7 days after an exam period ends. The dates come
from the faculty's teaching calendar PDF, which `studije.py` already archives in `nastava.db` (`study_files`, path
`studije/kalendar_nastave_oas_mas_26_27.pdf`). 2026/27 has 166 hot days.

### Why (the analysis, so nobody redoes it)

- Posts by hour, last 12 months (2,981 posts, Belgrade time): almost none 01–07; peak 11–18 (13:00 highest);
  88% are in by 21:00. Average wait from a post to the site: 1 run at 21–22 h → 8.7 h (the best single time; a
  morning run is 15 h); 2 runs 15 + 22 → 4.7 h; 3 runs 13 + 18 + 22 → 3.6 h. Weekends ~40% fewer posts.
- Posts per day, 2022–2026 without the protest months: exam period 10.9, registration 8.6, week after an exam period
  8.5, other days 6.4. The largest spikes (40–68 posts a day) are results and oral exam dates during an exam period and
  in the week after it.
- 2025/26's exam periods were moved by the student protests, so dates are read from the PDF, not fixed.

### The 2026/27 calendar (parsed from the PDF; the self-check below asserts exactly this)

| | Prijave (registration) | Rok (exam period) |
|---|---|---|
| Manji blok, autumn | Mon 2.11.–Wed 4.11.2026 | Mon 9.11.–Sun 15.11.2026 ("VI недеља": the week after registration) |
| Januarski | 11.1.–13.1.2027 | 18.1.–31.1.2027 |
| Februarski | 3.2.–4.2.2027 | 8.2.–21.2.2027 |
| Manji blok, spring | 22.3.–24.3.2027 | 29.3.–4.4.2027 (week after registration) |
| Junski | 31.5.–2.6.2027 | 7.6.–20.6.2027 |
| Julski | 23.6.–24.6.2027 | 28.6.–11.7.2027 |
| Septembarski | 16.8.–18.8.2027 | 23.8.–5.9.2027 |
| Oktobarski | 8.9.–9.9.2027 | 13.9.–26.9.2027 |

### Run times

GitHub's cron is UTC and has no daylight saving time; `:23` because GitHub delays runs at the top of the hour.

| Slot | Cron (UTC) | Belgrade winter | Belgrade summer | Runs on |
|---|---|---|---|---|
| noon | `23 11 * * *` | 12:23 | 13:23 | hot days |
| evening | `23 16 * * *` | 17:23 | 18:23 | hot days |
| night | `23 20 * * *` | 21:23 | 22:23 | every day |

On a day that is not hot, the noon and evening runs pull the state, see "skip" and stop (~1 minute of runner time).
The day's first run (noon on a hot day, night otherwise) also runs the side scrapers due that day.

## What exists now (as of 2026-11-09)

- `.github/workflows/sync.yml`: a draft from commit `6b4b7d6` (every 2 hours `forum`, Monday `sync`). It is replaced
  in step 3.
- `ci/deploy.sh`: modes `sync`, `forum`, none. Scrape modes: parsers test, `ci/state.sh pull`, `ci/push.py last`,
  `nastava.py sync`, `nastava.py stats`, `vesti.py sync`, (sync only: `studije.py`, `nastavnici.py`, `predmeti.py`),
  `ci/state.sh push`, then always build, upload to the `site` release, `gh workflow run deploy.yml`, `ci/push.py send`.
  `save.bat deploy [sync]` calls it with `sync` or nothing: keep those working.
- `ci/state.sh pull` removes `nastava.db-wal`/`-shm` before extracting (done in `6b4b7d6`).
- `ci/push.py`: `last` (newest post id), `send <id>` (waits until the site has the new posts, then pushes); skipped
  when `push-secret.json` is missing.
- `.github/workflows/deploy.yml`: publishes the newest `site` release asset to GitHub Pages. Unchanged.

## Step 1: create `ci/plan.py`

Create the file with exactly this content:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf"]
# ///
"""What a scheduled run (sync.yml) does, from the faculty's teaching calendar; and the database's fingerprint.

Usage: plan.py noon|evening|night | check | fingerprint
  noon, evening, night  the run's slot: print the parts for ci/deploy.sh ("forum", "forum studije", ...) or "skip"
  check                 exit 1 when the calendar of this school year is missing or unreadable (after 15 October)
  fingerprint           a hash of what the scrapers store: equal before and after a scrape means nothing changed
Today is the UTC date (the runs are 11–21 UTC: the same day in Belgrade); TODAY=2027-01-11 overrides it for a test.
"""
import datetime as dt
import hashlib
import io
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.getenv("DB", ROOT / "nastava.db"))
AFTER = 7          # days after an exam period that stay hot: results and oral exams come then
YEARLY = (10, 1)   # teachers and subjects: the school year's first day
# "18.1.-31.1.", "3.2. и 4.2.", "(2.11.-4.11.)"
RANGE = re.compile(r"(\d{1,2})\.(\d{1,2})\.\s*(?:-|–|и|i)\s*(\d{1,2})\.(\d{1,2})\.")


def windows(text, y1):
    """[(kind, first day, last day)] of the school year y1/y1+1, by first day: kind "prijave" (registration) or "rok"
    (an exam period). October to December are in y1, the rest in y1+1. A smaller block's exams are only "VI недеља":
    the Monday to Sunday after its registration."""
    day = lambda d, m: dt.date(y1 if m >= 10 else y1 + 1, m, d)
    out = []
    for line in text.splitlines():
        u, r = line.upper(), RANGE.search(line)
        if not r:
            continue
        a, b = day(int(r[1]), int(r[2])), day(int(r[3]), int(r[4]))
        if "ПРИЈАВЕ" in u or "PRIJAVE" in u:
            out.append(("prijave", a, b))
            if "МАЊЕГ" in u or "MANJEG" in u:
                monday = b + dt.timedelta(days=7 - b.weekday())
                out.append(("rok", monday, monday + dt.timedelta(days=6)))
        elif "ИСПИТНИ РОК" in u or "ISPITNI ROK" in u:
            out.append(("rok", a, b))
    return sorted(out, key=lambda w: w[1])


def school_year(d):
    return d.year if d.month >= 10 else d.year - 1


def calendars(db):
    """{school year: windows} of every calendar PDF the state has (studije.py archives them), newest version each."""
    from pypdf import PdfReader
    out = {}
    rows = db.execute("select path, data from study_files where path like 'studije/kalendar%.pdf' order by first_seen")
    for path, data in rows:
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        m = re.search(r"_(\d\d)_\d\d\.pdf$", path) or re.search(r"школска\s+20(\d\d)/", text)
        if m:
            out[2000 + int(m[1])] = windows(text, 2000 + int(m[1]))
    return out


def for_year(cals, y):
    """This school year's windows; without its calendar, the nearest one's moved by whole years."""
    if y in cals or not cals:
        return cals.get(y, [])
    near = min(cals, key=lambda c: abs(c - y))
    move = lambda d: d.replace(year=d.year + y - near)
    return [(k, move(a), move(b)) for k, a, b in cals[near]]


def hot(d, wins):
    return any(a <= d <= b + dt.timedelta(days=AFTER if k == "rok" else 0) for k, a, b in wins)


def parts(slot, d, wins):
    """The scrapers for a run: "forum" (the board and the news) and those due today, or "skip". A hot day has three
    runs (noon, evening, night), another day one (night); the day's first run takes the schedule pages (studije) on the
    1st of the month and on the first day of a registration or an exam period, and on 1 October the teachers and the
    subjects."""
    h = hot(d, wins)
    if slot != "night" and not h:
        return "skip"
    first = slot == ("noon" if h else "night")
    p = ["forum"]
    if first and (d.day == 1 or any(d == a for _, a, _ in wins)):
        p.append("studije")
    if first and (d.month, d.day) == YEARLY:
        p += ["nastavnici", "predmeti"]
    return " ".join(p)


def fingerprint(db):
    """What the scrapers change, without the last_seen times that every run updates. shortcut: an edit that keeps a
    post's length is not seen; a hash of every post's html would be (slower)."""
    queries = [
        "select count(*), max(id), sum(gone), total(length(html)), total(length(title)) from posts",
        "select count(*), sum(gone), total(length(title)) from topics",
        "select count(*), sum(gone) from vesti",
        "select count(*) from study_pages", "select count(*) from study_files",
        "select count(*), sum(gone), total(length(html)) from teachers", "select count(*) from teacher_subjects",
        "select count(*), sum(gone), total(length(html)) from subjects", "select count(*) from subject_places",
    ]
    out = []
    for q in queries:
        try:
            out.append(db.execute(q).fetchone())
        except sqlite3.OperationalError:  # a table a scraper has not made yet
            out.append(None)
    return hashlib.sha256(repr(out).encode()).hexdigest()[:16]


if __name__ == "__main__":
    _t = """ПРИЈАВЕ испита мањег блока (2.11.-4.11.)
ИСПИТИ мањег блока (VI недеља)
ПРИЈАВЕ испита за јануарски рок (11.1.-13.1.)
ЈАНУАРСКИ ИСПИТНИ РОК 18.1.-31.1.
ПРИЈАВЕ испита за фебруарски рок (3.2. и 4.2.)
ФЕБРУАРСКИ ИСПИТНИ РОК 8.2.-21.2.
(испитни дани 14.2. и 21.2.- надокнада за 15.2. и 16.2.)
ПРИЈАВЕ испита мањег блока (22.3.-24.3.)
ПРИЈАВЕ испита за јунски рок (31.5.-2.6.)
ЈУНСКИ ИСПИТНИ РОК 7.6.-20.6.
ПРИЈАВЕ испита за јулски рок (23.6.-24.6.)
ЈУЛСКИ ИСПИТНИ РОК 28.6.-11.7.
ПРИЈАВЕ испита за септембарски рок (16.8.-18.8.)
СЕПТЕМБАРСКИ ИСПИТНИ РОК 23.8.-5.9.
ПРИЈАВЕ испита за октобарски рок (8.9.-9.9.)
ОКТОБАРСКИ ИСПИТНИ РОК 13.9.-26.9."""
    D = dt.date
    _w = windows(_t, 2026)
    assert _w == [
        ("prijave", D(2026, 11, 2), D(2026, 11, 4)), ("rok", D(2026, 11, 9), D(2026, 11, 15)),
        ("prijave", D(2027, 1, 11), D(2027, 1, 13)), ("rok", D(2027, 1, 18), D(2027, 1, 31)),
        ("prijave", D(2027, 2, 3), D(2027, 2, 4)), ("rok", D(2027, 2, 8), D(2027, 2, 21)),
        ("prijave", D(2027, 3, 22), D(2027, 3, 24)), ("rok", D(2027, 3, 29), D(2027, 4, 4)),
        ("prijave", D(2027, 5, 31), D(2027, 6, 2)), ("rok", D(2027, 6, 7), D(2027, 6, 20)),
        ("prijave", D(2027, 6, 23), D(2027, 6, 24)), ("rok", D(2027, 6, 28), D(2027, 7, 11)),
        ("prijave", D(2027, 8, 16), D(2027, 8, 18)), ("rok", D(2027, 8, 23), D(2027, 9, 5)),
        ("prijave", D(2027, 9, 8), D(2027, 9, 9)), ("rok", D(2027, 9, 13), D(2027, 9, 26))], _w
    _p = lambda slot, *ymd: parts(slot, D(*ymd), _w)
    assert _p("noon", 2026, 11, 9) == "forum studije" and _p("night", 2026, 11, 9) == "forum"  # an exam period starts
    assert _p("evening", 2026, 11, 22) == "forum" and _p("noon", 2026, 11, 23) == "skip"       # 7 days after it, then not
    assert _p("night", 2026, 12, 1) == "forum studije" and _p("noon", 2026, 12, 1) == "skip"   # the 1st of a quiet month
    assert _p("night", 2026, 12, 5) == "forum" and _p("evening", 2026, 12, 5) == "skip"
    assert _p("noon", 2027, 1, 11) == "forum studije" and _p("evening", 2027, 1, 11) == "forum"  # registration opens
    assert _p("noon", 2027, 2, 2) == "forum" and _p("noon", 2027, 2, 1) == "forum studije"     # after January's; the 1st
    assert _p("noon", 2027, 10, 1) == "forum studije nastavnici predmeti"  # hot (after October's), the 1st, 1 October
    assert _p("night", 2026, 10, 1) == "forum studije nastavnici predmeti"
    assert hot(D(2026, 10, 3), [("rok", D(2026, 9, 13), D(2026, 9, 26))]) and not hot(D(2026, 10, 4), [("rok", D(2026, 9, 13), D(2026, 9, 26))])
    _c = {2026: _w}
    assert for_year(_c, 2027)[0] == ("prijave", D(2027, 11, 2), D(2027, 11, 4)) and for_year(_c, 2026) == _w and for_year({}, 2026) == []
    today = D.fromisoformat(os.environ["TODAY"]) if os.getenv("TODAY") else dt.datetime.now(dt.timezone.utc).date()
    match sys.argv[1:]:
        case ["fingerprint"]:
            print(fingerprint(sqlite3.connect(f"file:{DB}?mode=ro", uri=True)))
        case ["check"]:
            cals = calendars(sqlite3.connect(f"file:{DB}?mode=ro", uri=True))
            y = school_year(today)
            n = len(cals.get(y, []))
            print(f"calendar {y}/{y + 1}: {n} windows; have {sorted(cals)}")
            # The faculty may publish it late: no alarm before 15 October.
            if n < 12 and today >= D(y, 10, 15):
                sys.exit(f"no readable calendar for {y}/{y + 1} on www.mas.bg.ac.rs (kalendar nastave): the extra runs use the nearest year's dates")
        case [("noon" | "evening" | "night") as slot]:
            cals = calendars(sqlite3.connect(f"file:{DB}?mode=ro", uri=True))
            print(parts(slot, today, for_year(cals, school_year(today))))
        case _:
            sys.exit(__doc__)
```

Check (from the repo root, Git Bash; expected output after `->`):

    export PYTHONIOENCODING=utf-8
    uv run -q ci/plan.py fingerprint                    -> 16 hex characters (the self-check asserts passed)
    uv run -q ci/plan.py check                          -> calendar 2026/2027: 16 windows; have [2026]
    TODAY=2026-12-15 uv run -q ci/plan.py noon          -> skip
    TODAY=2026-12-01 uv run -q ci/plan.py night         -> forum studije
    TODAY=2027-01-11 uv run -q ci/plan.py noon          -> forum studije
    TODAY=2027-01-11 uv run -q ci/plan.py evening       -> forum
    TODAY=2027-03-29 uv run -q ci/plan.py noon          -> forum studije

(Later school years: `check` names that year; when the state has no newer calendar PDF yet, it says so and exits 1
only from 15 October.)

## Step 2: replace `ci/deploy.sh`

Read the current file first. If it differs from "What exists now" above beyond comments (someone added a scraper,
say), keep their addition in the matching place below and tell the user. Otherwise write exactly this:

```bash
#!/usr/bin/env bash
# Scrape, build and publish: the scheduled run (sync.yml) and this PC (by hand, as an override) run the same steps.
# The site goes up as an asset of the "site" release, and the deploy workflow puts it on GitHub Pages as it is.
# Usage: bash ci/deploy.sh [auto SLOT | sync | forum [studije] [nastavnici] [predmeti]]   (from the repo root)
#   auto SLOT  the scheduled run: SLOT is noon, evening or night; ci/plan.py picks the scrapers from the faculty's
#              teaching calendar, or "skip" (stop at once)
#   sync       every scraper: the board, the news, the schedule pages, the teachers, the subjects
#   forum ...  the board and the news, and the scrapers named after it
#   (none)     build and publish this copy's nastava.db, nothing scraped
# A scrape first gets the saved state (ci/state.sh pull), so this PC goes on from the last scheduled run. When the
# scrapers changed nothing (ci/plan.py fingerprint), nothing is saved, built or published. Otherwise: save the state,
# build, publish, then the web push of the new posts. Missing posts, a failed scraper, a failed push or an unreadable
# calendar do not stop the rest, but the script exits 1 at the end (a red run: GitHub's e-mail).
set -euo pipefail
repo=KostaJovanovic/nastava
export PYTHONIOENCODING=utf-8
failed=()
finish() {
	if ((${#failed[@]})); then
		echo "failed: ${failed[*]}" >&2
		exit 1
	fi
	exit 0
}

if [[ ${1:-} == auto || ${1:-} == sync || ${1:-} == forum ]]; then
	# The saved state, not this PC's copy: the scheduled run may be newer, and an older copy would scrape and notify
	# its posts again.
	bash ci/state.sh pull
	parts=("$@")
	if [[ $1 == auto ]]; then
		# tr: on Windows, Python ends its lines with \r\n.
		plan=$(uv run -q ci/plan.py "${2:?usage: deploy.sh auto noon|evening|night}" | tr -d '\r')
		echo "plan for the $2 run: $plan"
		read -ra parts <<< "$plan"
		[[ ${parts[0]} == skip ]] && exit 0
		# Once a day: a calendar the next days' runs can read.
		if [[ $2 == night ]]; then
			uv run -q ci/plan.py check || failed+=(kalendar)
		fi
	elif [[ $1 == sync ]]; then
		parts=(forum studije nastavnici predmeti)
	fi
	for p in "${parts[@]:1}"; do
		[[ $p == studije || $p == nastavnici || $p == predmeti ]] || { echo "unknown scraper: $p" >&2; exit 2; }
	done
	uv run test/parsers_test.py
	# The newest post before the scrape: the posts after it get a web push once published (ci/push.py).
	before=$(uv run -q ci/push.py last | tr -d '\r') || before=
	print=$(uv run -q ci/plan.py fingerprint | tr -d '\r')
	uv run nastava.py sync
	# Right after the scrape, so a post made since then does not count as missing.
	uv run nastava.py stats || failed+=(stats)
	# The news change daily too, and all of them are ~46 requests.
	uv run vesti.py sync || failed+=(vesti)
	for p in "${parts[@]:1}"; do
		uv run "$p.py" sync || failed+=("$p")
	done
	if [[ $(uv run -q ci/plan.py fingerprint | tr -d '\r') == "$print" ]]; then
		echo "nothing changed: no save, build or publish"
		finish
	fi
	bash ci/state.sh push
fi

uv run pages/build.py nastava.db pages/.build

name=site-$(date -u +%Y%m%d-%H%M%S).tar.gz
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
tar -czf "$tmp/$name" -C pages/.build/site .
gh release view site -R "$repo" >/dev/null 2>&1 ||
	gh release create site -R "$repo" --latest=false --title site --notes "The built site, published by the deploy workflow."
gh release upload site -R "$repo" "$tmp/$name"
# Keep the two newest, so a bad build can be published back over.
gh release view site -R "$repo" --json assets -q '.assets[].name' | sort | head -n -2 |
	xargs -r -I{} gh release delete-asset site {} -R "$repo" -y
gh workflow run deploy.yml -R "$repo"
echo "uploaded $name ($(du -h "$tmp/$name" | cut -f1)); deploy started: gh run list -R $repo -w deploy"
# It waits until the new posts are on the site. Without the keys (push-secret.json; on Actions the secret PUSH_SECRET)
# there is no push.
if [[ -n ${before:-} && -f push-secret.json ]]; then
	uv run -q ci/push.py send "$before" || failed+=(push)
fi
finish
```

Check: `bash -n ci/deploy.sh` prints nothing. Then one safe real run, which only pulls the state and stops (it
replaces the local `nastava.db` with the saved state, which every scrape run does anyway; if `git log`/the user
suggests a local scrape that was not saved, ask first):

    TODAY=2026-12-15 bash ci/deploy.sh auto evening     -> "pulled state-...", "plan for the evening run: skip", exit 0

Do not run `forum`, `sync` or a non-skip `auto` locally: they publish.

## Step 3: replace `.github/workflows/sync.yml`

```yaml
name: sync

# The automatic update. Three scheduled runs a day; ci/plan.py (through ci/deploy.sh auto) decides from the faculty's
# teaching calendar what each one does: on a hot day (registration, an exam period and the 7 days after it) all three
# scrape the board and the news, on another day only the night run. The schedule pages also on the 1st of the month
# and on the first day of a registration or an exam period; the teachers and the subjects on 1 October.
# GitHub's cron is UTC: 12:23, 17:23 and 21:23 in Belgrade in winter, an hour later in summer. GitHub may start a
# scheduled run late, and turns the schedule off after 60 days without a commit.
on:
  schedule:
    - cron: "23 11 * * *"  # noon
    - cron: "23 16 * * *"  # evening
    - cron: "23 20 * * *"  # night
  workflow_dispatch:
    inputs:
      what:
        description: "forum: the board and the news; sync: every scraper; auto: as a scheduled run"
        type: choice
        options: ["forum", "forum studije", "sync", "auto noon", "auto evening", "auto night"]
        default: forum

permissions:
  contents: write  # the state and site releases
  actions: write   # ci/deploy.sh starts deploy.yml

concurrency:
  group: sync
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    env:
      GH_TOKEN: ${{ github.token }}
      WHAT: >-
        ${{ github.event_name != 'schedule' && inputs.what
        || github.event.schedule == '23 11 * * *' && 'auto noon'
        || github.event.schedule == '23 16 * * *' && 'auto evening'
        || 'auto night' }}
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "**/*.py"
      # push-secret.json (ci/push.py keys) as the repository secret PUSH_SECRET; without it there is no web push.
      - name: Get the web push keys
        env:
          PUSH_SECRET: ${{ secrets.PUSH_SECRET }}
        run: if [[ -n $PUSH_SECRET ]]; then printf '%s' "$PUSH_SECRET" > push-secret.json; fi
      - name: Scrape, build, publish, notify
        # Unquoted: the words are the arguments (the input is one of the choices above).
        run: bash ci/deploy.sh $WHAT
```

Check: `uv run -q --no-project --with pyyaml python -c "import yaml; w=yaml.safe_load(open('.github/workflows/sync.yml')); print(w[True]['schedule'])"`
→ the three crons.

## Step 4: docs

`README.md`, section "How it works": replace the first bullet's opening lines (from
"- `.github/workflows/sync.yml` updates the site on GitHub" up to "or the same `ci/deploy.sh` on a PC. A run:") with:

```
- `.github/workflows/sync.yml` updates the site on GitHub (`bash ci/deploy.sh auto noon|evening|night`). `ci/plan.py`
  reads the exam dates from the faculty's teaching calendar (the PDF `studije.py` archives): on a hot day
  (registration, an exam period and the 7 days after it) the board and the news are scraped at 12:23, 17:23 and
  21:23 Belgrade time (an hour later in summer), on other days at 21:23 only. The schedule pages also on the 1st of
  the month and on the first day of each registration and exam period; the teachers and the subjects on 1 October.
  A run that finds nothing new stops before saving and publishing. By hand, on GitHub:
  `gh workflow run sync.yml -f what=forum` (or `"forum studije"`, `sync`); on a PC: `bash ci/deploy.sh forum`
  (or `forum studije`, `sync`), which first gets the saved state. A run:
```

In the same list, step 3 ("checks the counts, then archives the schedules, the teachers and the subjects. ...")
becomes: "checks the counts, archives the news, and the schedules, the teachers and the subjects when they are due. A
failure in these does not stop the run;". Step 7 becomes: "exits 1 (a red run, GitHub's e-mail) when the count check,
a scraper, the push or the calendar check failed."

The "Files" bullet for `ci/deploy.sh` becomes: "- `ci/deploy.sh`: scrape, build and publish (`auto SLOT`, `sync`,
`forum [studije] [nastavnici] [predmeti]`, or nothing: only build and publish). `ci/plan.py`: what a scheduled run
does, from the calendar; the database fingerprint. `ci/state.sh`: get and save `nastava.db`."

`PLAN.md`, section "Daily refresh": add a first line "- Built as planned in `PLAN-sync.md` (scheduled sync)." Then in
this file change "Status:" to "built <date>, commit <hash>".

## Step 5: commit

`git status`; stage only `ci/plan.py`, `ci/deploy.sh`, `.github/workflows/sync.yml`, `README.md`, `PLAN.md`,
`PLAN-sync.md` (if README/PLAN.md have someone else's unstaged edits too, stage only your hunks: build the staged blob
with `git show HEAD:README.md`, apply your edit to that text, `git hash-object -w --stdin`, `git update-index
--cacheinfo 100644,<blob>,README.md`). Commit message: `Calendar-driven sync schedule`. Do not push.

## Step 6: tell the user what only they can do

1. Push (`save.bat`, or `git push`).
2. The web push keys for Actions, once: `gh secret set PUSH_SECRET < push-secret.json` (repo root). Offer to run it;
   do it only on their yes.
3. The first run, watched: `gh workflow run sync.yml -f what="auto night"`, then `gh run watch`. The unknown:
   whether nastava.mas.bg.ac.rs and www.mas.bg.ac.rs answer GitHub's servers (never tested: the only earlier run
   failed before scraping). If "nastava.py sync" times out or gets 403, the scrape has to stay on the PC: say so,
   and propose Windows Task Scheduler running `bash ci/deploy.sh auto night` etc. instead.
4. E-mail: GitHub mails failed scheduled runs to whoever last changed the cron lines (the user, by pushing). Check
   github.com/settings/notifications → Actions → "Notify me for failed workflows" is on.
5. Do not run `ci/deploy.sh forum|sync` on the PC at :23 past 11, 16 or 20 UTC: two runs at once both save the state;
   the later one wins (no posts lost, but the next run may notify some posts twice).

## Known limits (say them in the final report)

- A post edit that keeps its length is not seen by the fingerprint (the site still gets it with the next new post).
- A topic edit older than 14 days is not seen (nastava.py's existing shortcut).
- If the faculty's calendar PDF changes format so no line matches, `check` makes the night run red from 15 October;
  until then the runs use last year's dates moved by a year.
- GitHub can start scheduled runs 10–60 minutes late, and disables the schedule after 60 days without a commit.
