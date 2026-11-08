# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A public, static archive of nastava.mas.bg.ac.rs (the phpBB notice board of Mašinski fakultet, Belgrade), plus the
schedule pages and the teachers of www.mas.bg.ac.rs. Live at https://nastava.valjdakosta.com. The UI is in Serbian.
Forked in design from Omar Žunić's dlwms (local copy in `ref/dlwms`, git-ignored). `README.md` describes the pipeline;
`PLAN.md` holds the wider plan (other faculty sites not scraped yet).

## Commands

Every script is a uv script with inline dependencies (`# /// script` header), so `uv run <file>` is enough.

    uv run nastava.py sync          # walk the forum tree, fetch changed topics into nastava.db
    uv run nastava.py stats         # board counts vs stored rows; exit 1 when posts are missing
    uv run studije.py sync          # schedule pages + their files (versioned by sha256)
    uv run nastavnici.py sync       # teacher list, profiles, emeritus page
    uv run documents.py sync        # attachments into files/ + text extraction (not run by CI)
    uv run pages/build.py nastava.db pages/.build      # render the site to pages/.build/site
    npx -y pagefind@1.6.0 --site pages/.build/site     # search index; must run after build.py
    uv run pages/build.py --strip pages/.build/site    # then drop the hidden text Pagefind read (~50 MB)
    server.bat [build]              # (re)build and serve on http://localhost:3000 (asks for admin: firewall rule)    python pages/serve.py [port]    # serve the last build; /static/ live from pages/static (no build for CSS/JS)
    bash ci/state.sh pull|push      # get/save nastava.db as an asset of the `state` GitHub release
    cd pages && wrangler deploy     # the Cloudflare Worker
    save.bat quick "message"        # git add + commit + push

Env vars read by `nastava.py`: `DB` (path to the database, default `./nastava.db`), `DELAY` (0.5 s), `WORKERS` (2).
Keep the scraping polite: no more parallelism or less delay than that.

### Tests

There is no test runner; each test is a plain script.

- `uv run --with beautifulsoup4 --with requests python test/parsers_test.py` — the parsers against saved pages in
  `test/fixtures/`, no network. This is the CI gate. When the board or www.mas.bg.ac.rs changes markup, save the new
  page over the fixture and fix the parser until it passes.
- `uv run pages/build.py ...` runs self-check asserts (`fold`, `plural`, `dmy`, ...) in `__main__` before building.
- Browser tests use Playwright with Edge (`channel='msedge'`) against a running site, e.g.
  `python test/browser_test.py http://localhost:3000 test`. Others: `nastavnici_test.py <base>`,
  `pismo_test.py <base> <item path> <out dir>`, `counts_test.py <base>`, `speed_test.py <base> <site dir>`,
  `profile_search.py <base>`. They print results and write screenshots (git-ignored `test/*.png`).

## Architecture

**Data flow:** scrapers → one SQLite file `nastava.db` → `pages/build.py` → static HTML → Pagefind → GitHub Pages →
Cloudflare Worker (`pages/src/index.js`) on the custom domain. The daily GitHub Action (`.github/workflows/sync.yml`)
runs that whole chain. There is no server and no backend; the database is never committed (it lives as a zstd tarball
on the `state` release; the two newest are kept).

**Pages are stored as fragments.** `build.py write()` stores each page (all but home and 404) as `<html lang="sr">` +
its `<title>` + the inside of `<main>`; the rest, the same on every page, is `site/shell.html`. The Worker `join()`s
them per request (the raw GitHub Pages URL shows bare fragments); `pages/serve.py join()` does the same locally. Keep
the two in step. A template that changes anything outside `<title>`/`<main>` per page fails `write()`'s assert.

**Scrapers share one database.** `nastava.py` owns the schema for `forums`, `topics`, `posts`, `documents` and the
`connect()`/`get()`/`session()` helpers; `documents.py` imports `nastava`. `studije.py` (`study_pages`, `study_files`)
and `nastavnici.py` (`teachers`, `teacher_subjects`) each declare their own tables with `create table if not exists`.
`build.py` imports `PAGES`, `SITE`, `media_path` from `studije.py`.

**Incremental sync = completeness check.** Each phpBB forum listing shows subforum topic/post counts and the last post
id. A forum is re-walked only when those differ from the stored walk; a topic is re-fetched only when its last post id
changed, plus topics with a post in the last 14 days (edits don't change counts). First run and daily run are the same
code. `stats` compares the same counts with stored rows.

**Nothing is deleted.** A post or teacher that disappears from the source stays in the archive (marked gone); a changed
schedule page or file adds a new version. Keep that invariant in any schema or scraper change.

**CI failure policy:** the count check and the side scrapers (`studije`, `nastavnici`) run with `continue-on-error` so
the state is still saved and the site deployed; a final step turns the run red if any of them failed.

**Site build (`pages/build.py` + `pages/templates/` + `pages/static/`):** Jinja2 templates, post HTML sanitized with
nh3 (`clean_html`). Pages: home (smerovi), `/smer/<id>/`, subject pages, `/tema/<id>/` (topics with several posts),
`/item/<id>/` (one post; this is what Pagefind indexes), `/nastavnici/` and a page per teacher, schedule pages. A forum
author is linked to a teacher when the username equals the teacher's e-mail before `@`.

**Cyrillic/Latin search:** the board mixes both scripts. `fold()` in `build.py` turns text into Latin, no diacritics,
lower case for the Pagefind index; the browser folds the query the same way (`pismoFold` in `pages/static/pismo.js`,
used by `search.js` and `site.js`). The two must stay in sync. `pismo.js` also switches the whole page between Latin,
Cyrillic and the original text.

**Frontend:** plain JS, no bundler. `search.js` keeps all search state in the URL (`/?q=`, `smer`, year, `autor`, ...)
and queries Pagefind client-side. `site.js` is optional enhancement: every page must work without it.

**Attachments** are not hosted: links point straight at nastava.mas.bg.ac.rs. `documents.py` keeps a local copy in
`files/` (git-ignored) for later hosting via dlwms's release-files route.

## Conventions

- Python scrapers and tests are indented with tabs; `pages/build.py` uses 4 spaces. JS in `pages/static/` uses tabs
  (`site.js` uses 2 spaces). Match the file you edit.
- Docstrings and comments are short plain English, explaining why. A known limit is marked `# shortcut: <limit>, <when
  to upgrade>`.
- Git-ignored, local only: `recon/` (phase 1 probes against the faculty sites), `ref/` (dlwms), `*.db`, `files/`,
  `pages/.build/`.
