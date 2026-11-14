# Plan: refactor (untangle the code, cut the waste)

Status: agreed 2026-11-13, revised the same day (the waste list folded in), rechecked 2026-11-14 against the 92
commits since (the site's new pages: wiki, katedre, objave, stil; teachers' bios and summaries). Nothing built. One
commit per step, in order. Part A must not change the site's output; part B changes what the build or the browser
does, each step with its own check. Run it while no other session edits the repo (the moves touch most files).

## Before step A1

- **No work in progress.** On 2026-11-14 another session had 11 files changed and not committed (`build.py`,
  `site.js`, `style.css`, `studije.py`, templates; `mf.html` deleted). Start only on a clean tree, and take the
  reference build then, not before.
- **Fix the fingerprint first (a bug, its own commit).** `studije.py` now fills `wiki_pages` and `nastavnici.py`
  `departments`, but neither is in `ci/plan.py fingerprint` nor in `ci/runs.py TABLES`: a run where only they
  changed is not saved to the `state` release, and the run log misses them.
- **`mockup-gear.html`** (root, 116 lines, a design mockup): the user decides: delete, or move to `docs/`.

## The check

Before step A1, build `main` as it is into a reference folder: `uv run pages/build.py nastava.db %TEMP%/ref`, never
into `pages/.build`. After each step build the same `nastava.db` into `%TEMP%/new` and `diff -r` the two `site/`
folders: no difference outside `pagefind/`. Also: every no-network test in `test/`, `node --test
test/worker_test.mjs`, `pages/devcheck.py` (dev mode = build), and `uv run pages/serve.py <port>` serves a page.
Part B says per step where the output may differ and how that is checked instead.

## What is tangled (audit 2026-11-13)

- `pages/build.py`, 2,333 lines (2,710 on 2026-11-14 and growing): loads every source, cleans HTML, parses the
  schedules, the stats, feeds, sitemap, writing, the wiki, katedra and stil pages, hand-kept data (`OTHER_TEACHERS`,
  `FORUM_ACCOUNT`, `RENAMED`, `SITES`, `FORUMS`, `OWN_SITES`, `SHORT_SURNAME`, `LINKS`, `MF_GROUPS`) and 91 asserts.
- The scrapers borrow from each other: the DB path is defined five ways; `cent.py` owns `now`/`get`/`FILE`, used by
  `katedre.py` and `site_files.py`; five scrapers import `session` from `nastava.py` inside functions; `build.py`
  edits `sys.path` to import `studije`, `nastavnici`, `mail`.
- Two styles: tabs + `'` (nastava, documents, nastavnici, predmeti, studije, vesti, most tests), spaces + `"` (rest).
- The Cyrillic→Latin table four times: `build.py` (CYR, LAT), `nastavnici.py`, `teams.py`, `pismo.js`.
- The root: 11 scripts, 4 `.jsonl`, 2 browser-console `.js`, 7 plans, a mockup, 2 `.bat`.
- Page fetching written again per scraper: `studije.py` and `nastavnici.py` each have their own `page()` (sleep,
  get, None on 404), as `cent.get` and `nastava.get`.
- `nastavnici.py` does two jobs: the live sync and the history (Wayback, masinac → the `.jsonl` files).
- Asserts in `__main__` of 13 files (~170), run on each build or run.
- `site.js`: one IIFE on every page (1,039 lines, 1,192 on 2026-11-14); most of it serves three pages.

## Where the time goes (profiled 2026-11-13)

Shares of dev mode's start-up (`uv run pages/serve.py`, ~15 s; cProfile, which doubles the times); a build spends
the same on these:

| What | Share | Step |
|---|---|---|
| `archive_stats` (`post_words` over all 24k posts), for `/statistika/` only | ~26% | B1 |
| `lat()`: a Python call per Cyrillic letter, 4.5M calls | ~18% | A2 |
| `write()`, though dev mode only stores the page: not explained yet | ~18% | A5 |
| `clean_html` (nh3) of every post up front | ~14% | B2 |

## Part A: output stays the same

1. **Format.** `ruff format` every Python file: spaces, double quotes, line length 140 (`ruff.toml`). Its hash into
   `.git-blame-ignore-revs`. No other change in this commit.
2. **`common.py`.** DB path and `connect(ro=False)`, `session()` (retries) and `plain_session()` (none: katedre's
   crawl), `instrument`, `now`, `get` (with a `None` on 404 option, for `studije.page`, `nastavnici.page` and
   `nastava.get`), `FILE`, and the one Cyrillic→Latin table; `fold`, `lat`, `to_cyr` and
   teams' name regexes build on it. No scraper imports another scraper. `pismo.js` keeps its own copy (browser),
   with a comment naming `common.py`.
   `lat` becomes a `str.translate` table instead of a call per letter, with the Љ/Њ/Џ capital rule kept (an all-caps
   word: "LJ", else "Lj"; a pass for those three after the table). Same output: the check's diff proves it.
3. **Layout.**
   ```
   scrapers/     nastava vesti cent katedre studije nastavnici predmeti mail teams documents site_files common
   tools/teams/  teams-export.js teams-files.js
   data/         nastavnici-istorija.jsonl nastavnici-foto.jsonl nastavnici-biografije.jsonl nastavnici-sazetak.jsonl
   docs/         PLAN.md PLAN-app.md PLAN-refactor.md PLAN-stil.md PLAN-aesthetics.md
   ```
   Root keeps: `README.md`, `LICENSE`, `verzije.md`, `save.bat`, `server.bat`, `nastava.db`, `mail/`, `ci/`,
   `pages/`, `test/`. Update every path: `ci/deploy.sh`, `ci/plan.py`, `ci/runs.py` (scraper name from argv: the
   basename, so unchanged; `TABLES`), `ci/push.py`, `sync.yml` (`cache-dependency-glob`), `serve.py` `WATCH` (the
   scrapers and the four `.jsonl` now), `build.py`'s `HISTORY`/`FOTOS`/`BIOS`/`SUMMARIES`,
   `server.bat`, `save.bat`, the tests, the README (every `uv run X.py`), the memory notes that name paths.
   `mail.asset_name` hashes paths relative to `mail/`, which stays: the release assets keep their names.
4. **`scrapers/nastavnici_istorija.py`.** The history part of `nastavnici.py` (~220 lines: `to_cyr`, `name_key`,
   `parse_masinac`, `history`, …) with its own entry; README and `deploy.sh` if they call it.
5. **`pages/site/` package.** `pages/build.py` stays the entry (`uv run pages/build.py`, its script deps), with
   `main` only:
   - `text.py`: fold, lat, slug, plural, desc, katedra, acronyms, short_smer, smer_label
   - `html.py`: clean_html, cent_tidy, attachments, downloads, linkify, file_rows, drop_empty_tables, book_page
   - `load/`: board (places, items, topics), vesti, cent, katedre, mail, teachers (+ history, bio and summary
     files, bibliography), book, verzije
   - `links.py`: service, mark_elsewhere
   - `schedule.py`: parse_lectures, schedule_entries, render_study_pages
   - `wiki.py`: the faculty pages (wiki_pages): render_wiki_pages, wiki_href, wiki_title, wiki_link, link_groups
   - `stats.py`: archive_stats, post_words, same_words, bars, ranking
   - `stil.py`: stil_data, css_colors, png_size
   - `output.py`: env, write, write_page, split_page, versioned, breadcrumbs, feeds, sitemap, pagefind; the dev-mode
     state (`dev`, `shell`, `snav`, `pages`, `asset_v`) lives here only
   - `render.py`: render_places, render_teachers, render_katedre (+ department_intro), render_objave, render_book,
     render_vesti, render_home, picker
   - `known.py`: the hand-kept data
   Take the function list from `build.py` as it is on the day: it changes daily; each function goes to the module
   of its job, a new one too.
   `serve.py` (dev mode) and `devcheck.py` import from the package; check both.
   While moving `write()` into `output.py`, find its ~18% (profile once more: `path.parent.relative_to` 33k times?
   arguments built eagerly?) and fix it if the output stays the same; else note it for part B.
6. **Tests.** Every inline assert to `test/<module>_test.py` (plain asserts, no framework), the build's ones split
   by module. `deploy.sh`'s `tests` step runs every no-network test; the browser ones stay manual.
7. **Front end.** `site.js` keeps what every page needs (header search, menus, side panel); the picker and
   `/mojipredmeti/` steps, and the list grouping and filters (predmeti, nastavnici, the archive) become their own
   files, loaded only by their templates, added to `VERSIONED` in `output.py`. `style.css` stays one file,
   reordered into commented sections (base, header, side panel, lists, subject, teacher, stats, …), but its colour
   variables stay first and in their order: `/stil/` lists them as `css_colors` finds them.
   Check also in a browser: the pages that lost code still filter, group and pick.
   Do this step when the UI work pauses: `site.js` and `style.css` change most days (the picker was rebuilt
   2026-11-13), and a split during that work means conflicts.
8. **Done plans.** Delete `PLAN-sync.md` and `PLAN-cent.md`, only after asking the user at this step; fix the
   README and `PLAN.md` links to them. Ask the same then about `PLAN-stil.md` (built but its verzije.md entry) and
   `PLAN-aesthetics.md` (items open on 2026-11-14): never delete one without asking.

## Part B: less work, same pages

1. **The word cloud at most weekly** (the user's call; keep it simple). `nastava.db`'s `meta` table keeps it:
   `words` (the counts as JSON) and `words_at` (the date). A small writer (`uv run pages/build.py words nastava.db`)
   computes them when `words_at` is missing or 7+ days old, else does nothing. `ci/deploy.sh` runs it after the
   scrapers and before the fingerprint check, so `ci/state.sh push` saves it to the `state` release with the rest.
   The build stays read-only: it uses `meta.words` when there, else computes in memory (an old database, dev mode
   on a copy never written). `meta` is not in `ci/plan.py fingerprint`, so a run that changed nothing else does not
   save a new cloud; the next run makes it again (a few seconds, rarely). Check: `/statistika/` the same as the reference
   on the day the cloud is made; later it lags the posts by up to 7 days, by design.
2. **`clean_html` per page in dev mode.** The build cleans every post as now (the pages and the search need it);
   dev mode cleans a post only when its page is rendered (the post list needs no html). Same function both ways:
   `devcheck.py` must still find dev mode = build.
3. **`pismo.js` converts each page once.** Now it converts as the parser adds nodes, then `set(mode)` walks the
   whole body again at DOMContentLoaded, only to catch text the parser grew after its first conversion (split
   across network chunks). Let that walk skip a node whose text is still what was shown (`shown`). The switch (a
   click) still converts everything. Check: `test/pismo_test.py` on a long page.
4. **The Worker caches `shell.html`** (`pages/src/index.js`). It now fetches the shell from GitHub Pages for every
   page not in its edge cache: one extra request each. Keep it in the edge cache, keyed by the deploy (the shell's
   own asset versions, `?v=`), so a deploy brings the new shell. Minor; `test/worker_test.mjs` gets a case, then
   `wrangler deploy`.

## Open question (for the user, asked, not answered)

Build every page in Latin and keep only the Cyrillic button? Gain: a Latin reader's page needs no conversion at all
(`pismo.js` would act only on a click), and `lat` at build time mostly goes. Loss: the Cyrillic view becomes
Latin→Cyrillic of the Latin, which `toCyr` cannot always undo: "nj"/"lj"/"dž" across a word's parts ("injekcija" →
инјекција, not ињекција; "nadživeti" → надживети, not наџивети), so a post first written in Cyrillic no longer
shows exactly as written. Text first written in Latin is already converted this way today. Not in any step until
answered.

## Not changed

The Teams `CLASSES` list stays in both `teams.py` and `teams-files.js` (a console script cannot read the repo), each
with a comment naming the other. The database schema (only new `meta` keys), what any scraper fetches, and the
Worker beyond step B4.
