# Plan: refactor (untangle the code, cut the waste)

Status: agreed 2026-11-13, made full 2026-11-14 (checked against the code that day). Nothing built.

Part A must not change the site: every page byte for byte the same (the check below), except where a step says what
may differ. Part B changes what the build or the browser does, each step with its own check. The open question at
the end is in no step until the user answers it.

## Rules for whoever builds it

- All of it on the local branch `refactor`, made from `main` at the start; `main` is not touched. The user merges it
  (and pushes) when they want. Other sessions may go on committing to `main`: before each step, `git merge main`
  into `refactor` (a merge, not a rebase: the moves keep their history), fix the conflicts by redoing the move on
  the new code, and take a new reference build from `main` as merged. If a merge cannot be made clean, stop and ask.
- Steps in order; each step one commit (A5: one commit per module moved), message 3–5 words. Commit, never push.
- Start a step only on a clean tree with no other session editing the repo: the moves touch most files.
- Never build into `pages/.build` (the user rebuilds); the check builds into `%TEMP%`.
- Never delete a plan file without asking the user at that moment, even one this plan names.
- A step that cannot pass its check stops: say what differs, do not commit around it.

## The check

Once, before A1:

    cp nastava.db "$TEMP/refactor.db"                       # frozen: a state pull must not change the data mid-way
    uv run pages/build.py "$TEMP/refactor.db" "$TEMP/ref"   # the reference (after the step-0 fixes)

After each step:

    uv run pages/build.py "$TEMP/refactor.db" "$TEMP/new"
    diff -r --exclude=pagefind "$TEMP/ref/site" "$TEMP/new/site"     # no output
    uv run pages/devcheck.py "$TEMP/refactor.db"                     # dev mode = build
    uv run test/parsers_test.py                                      # (from A6: every test/*_test.py)
    node --test test/worker_test.mjs

and once per part, `uv run pages/serve.py <port>` opens a page (kill only that server, by its exact command line).
`verzije.md` and the `.jsonl` files are inputs too: if another session changes them, take a new reference.

## What is tangled (audit 2026-11-13, numbers of 2026-11-14)

- `pages/build.py`, 2,729 lines: loads every source, cleans HTML, parses the schedules, the stats, the feeds, the
  sitemap, the writing, the wiki, katedra, objave and stil pages, hand-kept data and 104 asserts; mutable module
  state (`dev`, `pages`, `shell`, `site_dir`, `snav`, `urls`, `asset_v`, `katedra_pages`) that `serve.py` and
  `devcheck.py` reach into.
- The scrapers borrow from each other: the DB path is built five ways from `__file__`; `cent.py` owns `now`, `get`
  and `FILE`, used by `katedre.py` and `site_files.py`; five scrapers import `session` from `nastava.py` inside
  functions; page fetching is written again in `studije.page`, `nastavnici.page`, `cent.get`, `nastava.get`, and
  `nastavnici.history` has its own `get`; `build.py` edits `sys.path` to import `studije`, `nastavnici`, `mail`.
- Two styles: tabs + `'` (nastava, documents, nastavnici, predmeti, studije, vesti, most tests), spaces + `"` (rest).
- The Cyrillic→Latin tables: `build.py` (`CYR` for `fold`, `LAT` for `lat`), `nastavnici.py` (`LATIN`, `CYRILLIC`
  for `to_cyr`), `teams.py` (`LAT`), `pismo.js`.
- The root: 11 scripts, 4 `.jsonl` (written by hand and by sessions, read only by `build.py`), 2 browser-console
  `.js`, 7 plans, 2 `.bat`.
- `nastavnici.py`: the live sync plus `history`, a one-time job (~200 lines) with its own fetching.
- Asserts in the `__main__` of 14 files (~185), run on each build or each run.
- `site.js`: one 1,192-line IIFE on every page; the `/mojipredmeti/` picker (~270 lines) serves one page.

## Step 0: before the refactor (bugs, not refactor)

1. **The fingerprint misses `departments`.** `nastavnici.py` fills it, `ci/plan.py fingerprint` does not count it
   (`wiki_pages` was added 2026-11-14): a run where only a department page changed is not saved. Add
   `select count(*), total(length(html)) from departments`. Commit "Fingerprint: departments".
2. **The run log misses both.** `ci/runs.py TABLES` lacks `wiki_pages` and `departments`. Add them. Commit "Run log:
   wiki, departments".

Then take the reference build.

## Part A: the same site

### A1. Format

- `ruff.toml` at the root: `line-length = 140`, `target-version = "py311"`, `[format] quote-style = "double"`,
  `indent-style = "space"`.
- `uvx ruff format .` (it skips `ref/`, `recon/` as git-ignored). No other change in this commit.
- Commit "Format: ruff, spaces". Then a second commit adding `.git-blame-ignore-revs` with that hash, and
  `git config blame.ignoreRevsFile .git-blame-ignore-revs` told to the user (a local setting).
- Check: the site check, and `python -m compileall -q .` (no syntax broken in the scripts the build does not import).

### A2. Shared scraper code

New, still in the root (A3 moves them):

- `translit.py`, no dependencies (`build.py`, `teams.py`, `mail.py` import it; they have no `requests`):
  - `LAT`: Cyrillic → Latin with diacritics, as a `str.maketrans` table, with `lat(s)` keeping today's rule for
    Љ/Њ/Џ (all-caps word: "LJ", else "Lj") and `Markup` in → `Markup` out.
  - `fold(s)`: lower ASCII without diacritics (today's `build.fold`, its `lru_cache` kept).
  - `to_cyr(s)` and its tables from `nastavnici.py`.
  - `teams.LAT` merges into these only where a table is equal letter for letter: compare them first (an assert);
    one that differs stays in `teams.py` with a comment why.
- `common.py`:
  - `ROOT` (the repo root, from `__file__`, so it stays right after A3), `DB = os.getenv("DB", ROOT / "nastava.db")`,
    `connect(ro=False)` (timeout 60; `ro` opens `file:…?mode=ro`).
  - `session()` (per thread, retries, the User-Agent, `instrument`), `plain_session()` (no retries: katedre's
    crawl), `instrument`, `now()`, `FILE`.
  - `get(s, url, delay, missing=False)`: sleep, get, timeout 60; a 404 with `missing=True` → `None`, else raise.
    Each scraper keeps its own `DELAY` (nastava 0.5, cent 1.0, katedre 0.3: their defaults differ on purpose) and
    a one-line wrapper where its callers want soup or text (`nastava.get`, `studije.page`, `nastavnici.page`).
  - `requests` is imported inside `session`/`plain_session`/`instrument`: `build.py` imports `studije` and
    `nastavnici` (for `media_path`, `photo_urls`) and has no `requests` in its dependencies.
- Every scraper imports from these two at the top; none imports another scraper. `site_files.py` and `katedre.py`
  stop importing `cent`.
- `build.py`: `fold`, `lat`, `CYR`, `LAT` come from `translit`; `pismo.js` gets a comment naming `translit.py`.
- Check: the site check (it proves `lat` and `fold` unchanged), `parsers_test.py`, each scraper's `--help`/usage runs
  (an import error shows), and one real `uv run cent.py sync` against a copy of the DB (`DB=$TEMP/scrape.db`) to see
  the network path work. Commit "Shared scraper code".

### A3. Layout

    scrapers/     nastava vesti cent katedre studije nastavnici predmeti mail teams documents site_files common translit
    tools/teams/  teams-export.js teams-files.js
    data/         nastavnici-istorija.jsonl nastavnici-foto.jsonl nastavnici-biografije.jsonl nastavnici-sazetak.jsonl
    docs/         PLAN.md PLAN-app.md PLAN-refactor.md PLAN-stil.md PLAN-aesthetics.md PLAN-sync.md PLAN-cent.md

Root keeps `README.md`, `LICENSE`, `ruff.toml`, `verzije.md`, `save.bat`, `server.bat`, `nastava.db`, `mail/`, `ci/`,
`pages/`, `test/`. All with `git mv`. What must follow:

- Paths from `__file__` that meant the root: `mail.MAIL`, `teams.MAIL`, `documents.FILES`, `site_files.HERE` →
  `common.ROOT` (the DB is already `common.DB` from A2).
- `ci/deploy.sh`: `uv run nastava.py` … and `uv run "$p.py"` → `scrapers/…`. `ci/runs.py` names a scraper by its
  file's basename: unchanged.
- `pages/build.py`: `sys.path` → `ROOT/"scrapers"`; `HISTORY`, `FOTOS`, `BIOS`, `SUMMARIES` → `data/`.
- `pages/serve.py` `WATCH`: the scrapers and the four `.jsonl` at their new paths.
- `test/parsers_test.py` (`sys.path`), `test/docs_test.py`, `server.bat` (its "uv run nastava.py sync" hint),
  `save.bat` if it names a script, `teams-files.js`'s comment naming `teams.py`.
- `README.md`: every `uv run X.py`, the file list. The old plans moved to `docs/` keep their text (history).
- Comments naming a script (`pages/src/index.js`, `rows.html`, `ci/push.py`, `ci/state_merge.py`): paths fixed.
- The memory notes: grep them for a moved file and fix (the user's `~/.claude/projects/J--Projekti-nastava/memory`).
- `sync.yml`'s `cache-dependency-glob: "**/*.py"` still matches.
- Check: the site check, every scraper's usage, `bash ci/deploy.sh` is not run (it publishes); read its diff
  instead, and `bash -n ci/deploy.sh`. Commit "Scrapers, data, docs folders".

### A4. `scrapers/nastavnici_istorija.py`

- From `nastavnici.py`: `history` and what only it uses (`WAYBACK`, `MASINAC`, `name_key`, `person_keys`,
  `image_key`, `parse_masinac`, `wb_time`, its `get`, which becomes `common.get` with its retries kept as they are:
  1.5 s × 2ⁿ, 4 tries). `to_cyr` is in `translit` since A2.
- `nastavnici.py`: `history` leaves its `commands` and docstring; `store_photos` stays (sync uses it) and the new
  file imports it.
- README: "nastavnici.py history" → "nastavnici_istorija.py".
- Check: site check, `parsers_test.py`, both files' usage. Commit "Teacher history apart".

### A5. `build.py` into `pages/sitegen/`

The package is `sitegen`, not `site` (a standard module Python imports at start-up: `import site` would get that one,
silently). Modules, by job:

| Module | What goes in |
|---|---|
| `text.py` | plural, FORMS, katedra, KATEDRA_NOM, acronyms, slug, desc, set_hrefs, parse_date, short_smer, smer_label, smer_abbr, slot_label, azbuka, strip_tags |
| `clean.py` | clean_html, cent_tidy, CENT_CLASSES, preuzeto, downloads, attachments, ATTACHMENT, FILE_KINDS, linkify, file_rows, drop_empty_tables, book_page |
| `known.py` | hand-kept data: RENAMED, SITES, SITE_NAMES, FORUMS, FORUM_ACCOUNT, OTHER_TEACHERS, OWN_SITES, SHORT_SURNAME, LINKS, HOME_ORDER, PROGRAMS, PROGRAM_NAMES, RANKS |
| `output.py` | env and its filters, all mutable state, versioned, version_static, Lazy, LazyTemplate, write, write_page, write_bytes, split_page, snav_href, breadcrumbs, write_sitemap, pagefind_tags, mark_for_pagefind, strip_pagefind, run_pagefind (from `main`) |
| `load/board.py` | subject_name, load_places, load_items, load_topics, board_subject, book_subject, row_katedra |
| `load/sources.py` | load_vesti, load_cent, load_katedre, load_mail, mail_href, VIA |
| `load/teachers.py` | load_history, load_teachers, _mentioned, bibliography, BIB_KINDS, department_intro, photo_path, write_photos |
| `load/book.py` | load_book, plan_groups |
| `links.py` | ELSEWHERE, FILE_HOSTS, FOLDER, service, mark_elsewhere |
| `schedule.py` | first_link, schedule_card, parse_lectures, schedule_entries, render_study_pages |
| `wiki.py` | link_groups, archived_wiki, wiki_href, wiki_link, render_wiki_pages, wiki_title |
| `stats.py` | bars, ranking, post_words, same_words, archive_stats, CLOUD_STOP, MONTHS, WEEKDAYS |
| `stil.py` | STIL_FONTS, STIL_LOGOS, css_colors, png_size, stil_data |
| `feeds.py` | post_href, atom, write_feeds |
| `render.py` | render_item, newest, render_places, render_cent, render_teachers, gone_span, render_katedre, render_book, picker, side_panel, attachment_files, render_vesti, render_objave, render_home, load_verzije |

`pages/build.py` keeps its dependency header, docstring, `main()` (the order of the build, as now) and `__main__`.

- **State lives in `output` only**, and every other module reads it as `output.dev`, `output.pages`, calls
  `output.write(...)`: never `from .output import dev, write` (a copy, which `devcheck.py`'s patching of
  `write`/`write_page`/`write_sitemap`/`run_pagefind` would miss). `katedra_pages` (filled by render_katedre, read
  by the `katedra_href` filter) is state too.
- `serve.py`: `build.pages`, `build.snav`, `build.snav_href` → `output.…`; `WATCH` gets `pages/sitegen/`.
  `devcheck.py`: patches `output`'s functions. `test/pismo_test.py`: `fold` from `translit`.
- Constants used by one module go with it; used by several (BASE, SITE_URL, KIND, MAIN, HEAD_END) go in `text.py`
  or `output.py`, wherever their users already import.
- The list above is of 2026-11-14: take the function list from `build.py` on the day; a newer function goes to the
  module of its job.
- Order (each a commit that passes the check): text, clean, known, output, links, load/*, schedule, wiki, stats,
  stil, feeds, render. A move only moves: no renames, no rewrites in the same commit.
- `write()` is ~18% of dev mode's start-up though it only stores the page there: when it reaches `output.py`,
  profile once (`python -m cProfile -s cumtime pages/devcheck.py`) and fix it if the site check stays empty; else
  note it under part B.
- The 104 asserts of `__main__` move with A6; until then they stay in `build.py`'s `__main__`, importing what they
  test.

### A6. Tests

- First the browser tests (`browser_test.py`, `nastavnici_test.py`, `pismo_test.py`, `speed_test.py`: they need
  Playwright and a running site) move to `test/browser/` (their screenshots stay git-ignored there: `.gitignore`
  updated), so `test/` holds only tests that need no network and no site.
- Every unit assert of a `__main__` goes to a test file, as plain asserts at module level (no framework), each test
  file a `uv` script with its module's dependencies:
  `test/build_test.py` (by sitegen module, in sections), `test/katedre_test.py`, `test/mail_test.py`,
  `test/teams_test.py`, `test/nastavnici_test.py`, `test/predmeti_test.py`, `test/site_files_test.py`,
  `test/plan_test.py`, `test/push_test.py`, `test/runs_test.py`, `test/state_merge_test.py`.
- Asserts that guard a real run stay where they are (`build.main`'s check that every `.snav` link is after the nav,
  `serve.py`, `icons.py`, `devcheck.py`'s comparison).
- `ci/deploy.sh`: the `tests` step runs every `test/*_test.py` except `build_test.py` and stops the run on a failure,
  as now (a broken parser must not scrape); a `build-tests` step before `build` runs `build_test.py`, so a build bug
  does not stop the scrape and the save, as today.
- Check: each new test passes; break one assert on purpose and see it fail; site check. Commit "Asserts into test/".

### A7. Front end

- `pages/static/moji.js`: the `/mojipredmeti/` picker (today `site.js` from `var mp = d.querySelector('[data-mp]')`
  to the end of its `izbor.then`, and the OPML button). Loaded only by `mojipredmeti.html`, inside its main part
  (the Worker joins the fragment, as `search.html` does with `search.js`), with `defer`: it runs after `site.js`,
  which is a plain script at the shell's end.
- What both need, `site.js` hands over once: `window.masinci = {el, izbor, mine, keepMine}` (`fold` is already
  `window.pismoFold`).
- The list filter (`[data-filter]`) stays in `site.js`: seven templates use it.
- `moji.js` into `VERSIONED` (`output.py`).
- `style.css`: one file, reordered into commented sections (variables, base, header, side panel, lists, subject,
  teacher, picker, stats, stil, footer). The colour variables stay first and in their order: `/stil/` lists them as
  `css_colors` finds them. Rules move, none changes; within a section the order of rules that match the same
  element stays (the cascade).
- May differ in the site check: `site.js`, `style.css`, the new `moji.js`, the `?v=` hashes on every page,
  `mojipredmeti/`'s script tag. Nothing else.
- Check in a browser (`serve.py`): `/mojipredmeti/` both steps, follow and unfollow, a teacher pick, the OPML
  download; the star on a subject page; the side panel's count and switch; light and dark; a phone width.
- Do this step when the UI work pauses: `site.js` and `style.css` change most days. Commit "Picker into moji.js",
  then "CSS in sections".

### A8. Plans

Ask the user, one file at a time, about deleting: `docs/PLAN-sync.md` and `docs/PLAN-cent.md` (built),
`docs/PLAN-stil.md` (built but its `verzije.md` entry), `docs/PLAN-aesthetics.md` (items open on 2026-11-14), and
this plan once part B is done. Fix the links to a deleted one (README, `PLAN.md`).

## Part B: less work, same pages

Where the time goes (dev mode's start-up, ~15 s, profiled 2026-11-13; a build spends the same on these):
`archive_stats` ~26% (B1), `lat` ~18% (A2), `write` ~18% (A5), `clean_html` ~14% (B2).

### B1. The word cloud at most weekly

- `nastava.db`'s `meta` table: `words` (the counts, JSON) and `words_at` (the date).
- `uv run pages/build.py words <db>`: computes and stores them when `words_at` is missing or 7+ days old, else
  nothing. `ci/deploy.sh` runs it after the scrapers, before the fingerprint check, so `ci/state.sh push` saves it.
- The build stays read-only: it uses `meta.words` when there, else computes in memory.
- `meta` is not in the fingerprint: a run that changed nothing else does not save a new cloud; the next run makes it
  again (a few seconds, rarely). `state_merge.py` keeps the state's `meta` rows: the saved cloud wins, right.
- Check: on the day it is made `/statistika/` equals the reference; a second run that day does not compute it.

### B2. `clean_html` per page in dev mode

The build cleans every post as now. Dev mode cleans a post when its page is rendered (the lists need no html). One
function both ways; `devcheck.py` must still find dev mode = build.

### B3. `pismo.js` converts each page once

Now it converts as the parser adds nodes, then `set(mode)` walks the whole body again at DOMContentLoaded, only for
text the parser grew after its first pass (split across network chunks). That walk skips a node whose text is still
what was shown (`shown`). The switch (a click) still converts everything. Check: `test/browser/pismo_test.py` on a
long page, both scripts.

### B4. The Worker caches `shell.html`

`pages/src/index.js` fetches the shell from GitHub Pages for every page not in its cache. Keep it in the edge cache,
keyed by the deploy (the shell's `?v=` asset versions), so a deploy brings the new shell. `test/worker_test.mjs`
gets a case; then `wrangler deploy` (the user's).

## Open question (asked, not answered)

Build every page in Latin and keep only the Cyrillic button? Gain: a Latin reader's page needs no conversion
(`pismo.js` acts only on a click), and `lat` at build time mostly goes. Loss: the Cyrillic view becomes
Latin→Cyrillic of the Latin, which `toCyr` cannot always undo ("injekcija" → инјекција, not ињекција; "nadživeti" →
надживети, not наџивети), so a post written in Cyrillic no longer shows exactly as written. Text written in Latin is
converted this way today.

## Not changed

The database schema (only new `meta` keys in B1), what any scraper fetches and when, the templates' output (but A7's
script tag), the Worker but B4, `mail/` and its release assets (`mail.asset_name` hashes paths relative to `mail/`,
which stays). The Teams `CLASSES` list stays in both `teams.py` and `teams-files.js` (a console script cannot read
the repo), each with a comment naming the other. `ci/*.py` keep their own `ROOT`: they run with other dependencies
(`state_merge.py` with none) and import no scraper.
