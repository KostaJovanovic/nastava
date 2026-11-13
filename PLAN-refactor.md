# Plan: refactor (untangle the code)

Status: agreed 2026-11-13, nothing built. One commit per step, in order. The site's output must not change: every
step ends with the check below. Run it while no other session edits the repo (the moves touch most files).

## The check (after every step)

Before step 1, build `main` as it is into a reference folder: `uv run pages/build.py nastava.db %TEMP%/ref`, never
into `pages/.build`. After each step build the same `nastava.db` into `%TEMP%/new` and `diff -r` the two `site/`
folders: no difference outside `pagefind/`. Also: every test in `test/` (no network ones), `node --test
test/worker_test.mjs`, `pages/devcheck.py` (dev mode = build), and `uv run pages/serve.py <port>` serves a page.

## What is tangled (audit 2026-11-13)

- `pages/build.py`, 2,333 lines: loads every source, cleans HTML, parses the schedules, the stats, feeds, sitemap,
  writing, hand-kept data (`OTHER_TEACHERS`, `FORUM_ACCOUNT`, `RENAMED`, `SITES`, `FORUMS`) and 91 asserts.
- The scrapers borrow from each other: the DB path is defined five ways; `cent.py` owns `now`/`get`/`FILE`, used by
  `katedre.py` and `site_files.py`; five scrapers import `session` from `nastava.py` inside functions; `build.py`
  edits `sys.path` to import `studije`, `nastavnici`, `mail`.
- Two styles: tabs + `'` (nastava, documents, nastavnici, predmeti, studije, vesti, most tests), spaces + `"` (rest).
- The Cyrillic→Latin table four times: `build.py` (CYR, LAT), `nastavnici.py`, `teams.py`, `pismo.js`.
- The root: 11 scripts, 3 `.jsonl`, 2 browser-console `.js`, 4 plans, 2 `.bat`.
- `nastavnici.py` does two jobs: the live sync and the history (Wayback, masinac → the `.jsonl` files).
- Asserts in `__main__` of 13 files (~170), run on each build or run.
- `site.js`: one 1,039-line IIFE on every page; most of it serves three pages.

## Steps

1. **Format.** `ruff format` every Python file: spaces, double quotes, line length 140 (`ruff.toml`). Its hash into
   `.git-blame-ignore-revs`. No other change in this commit.
2. **`common.py`.** DB path and `connect(ro=False)`, `session()` (retries) and `plain_session()` (none: katedre's
   crawl), `instrument`, `now`, `get`, `FILE`, and the one Cyrillic→Latin table; `fold`, `lat`, `to_cyr` and
   teams' name regexes build on it. No scraper imports another scraper. `pismo.js` keeps its own copy (browser),
   with a comment naming `common.py`.
3. **Layout.**
   ```
   scrapers/     nastava vesti cent katedre studije nastavnici predmeti mail teams documents site_files common
   tools/teams/  teams-export.js teams-files.js
   data/         nastavnici-istorija.jsonl nastavnici-foto.jsonl nastavnici-biografije.jsonl
   docs/         PLAN.md PLAN-app.md PLAN-refactor.md
   ```
   Root keeps: `README.md`, `LICENSE`, `verzije.md`, `save.bat`, `server.bat`, `nastava.db`, `mail/`, `ci/`,
   `pages/`, `test/`. Update every path: `ci/deploy.sh`, `ci/plan.py`, `ci/runs.py` (scraper name from argv: the
   basename, so unchanged; `TABLES`), `ci/push.py`, `sync.yml` (`cache-dependency-glob`), `serve.py` `WATCH`,
   `server.bat`, `save.bat`, the tests, the README (every `uv run X.py`), the memory notes that name paths.
   `mail.asset_name` hashes paths relative to `mail/`, which stays: the release assets keep their names.
4. **`scrapers/nastavnici_istorija.py`.** The history part of `nastavnici.py` (~220 lines: `to_cyr`, `name_key`,
   `parse_masinac`, `history`, …) with its own entry; README and `deploy.sh` if they call it.
5. **`pages/site/` package.** `pages/build.py` stays the entry (`uv run pages/build.py`, its script deps), with
   `main` only:
   - `text.py`: fold, lat, slug, plural, desc, katedra, acronyms, short_smer, smer_label
   - `html.py`: clean_html, cent_tidy, attachments, downloads, linkify, file_rows, drop_empty_tables, book_page
   - `load/`: board (places, items, topics), vesti, cent, katedre, mail, teachers (+ history files), book, verzije
   - `links.py`: service, mark_elsewhere
   - `schedule.py`: parse_lectures, schedule_entries, render_study_pages
   - `stats.py`: archive_stats, post_words, same_words, bars, ranking
   - `output.py`: env, write, write_page, split_page, versioned, breadcrumbs, feeds, sitemap, pagefind; the dev-mode
     state (`dev`, `shell`, `snav`, `pages`, `asset_v`) lives here only
   - `render.py`: render_places, render_teachers, render_book, render_vesti, render_home, picker
   - `known.py`: the hand-kept data
   `serve.py` (dev mode) and `devcheck.py` import from the package; check both.
6. **Tests.** Every inline assert to `test/<module>_test.py` (plain asserts, no framework), the build's ones split
   by module. `deploy.sh`'s `tests` step runs every no-network test; the browser ones stay manual.
7. **Front end.** `site.js` keeps what every page needs (header search, menus, side panel); the picker and
   `/mojipredmeti/` steps, and the list grouping and filters (predmeti, nastavnici, the archive) become their own
   files, loaded only by their templates, added to `VERSIONED` in `output.py`. `style.css` stays one file,
   reordered into commented sections (base, header, side panel, lists, subject, teacher, stats, …).
8. **Done plans.** Delete `PLAN-sync.md` and `PLAN-cent.md`, only after asking the user at this step; fix the
   README and `PLAN.md` links to them.

## Not changed

The Teams `CLASSES` list stays in both `teams.py` and `teams-files.js` (a console script cannot read the repo), each
with a comment naming the other. The database schema, the Worker, the templates' output, and what any scraper
fetches.
