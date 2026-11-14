# MF Beograd archive: plan

Status (2026-11-09): nastava is built on dlwms and tested (README.md). vesti is scraped (text only, media linked).
The main site and the department sites below are not scraped yet. Phase 1 probes and scripts are in `recon/`.

## Sources

| # | Source | Tech | Size | How to get it all | Completeness check |
|---|---|---|---|---|---|
| 1 | nastava.mas.bg.ac.rs/nastava | phpBB 3, public | ~17k topics, ~23.7k posts, 2014– ; ~16k attachments, ~6–7 GB | Walk every viewforum page (all ~1,250 subforums), then each topic page; sweep attachment ids 1..max | Per-subforum topic/post counts from the listing = stored; board totals (16,991 / 23,690); id sweep |
| 2 | vesti.mas.bg.ac.rs | WordPress, REST API open | 4,524 posts, 12,740 media, 2014– | `/wp/v2/posts?per_page=100` (46 req), media metadata (128 req) | `X-WP-Total` = stored |
| 3 | www.mas.bg.ac.rs | DokuWiki (no RSS/RPC) | course book `/studije/predmeti/NNNN`, schedules, documents | Crawl `?do=index` page tree | pages in index = stored |
| 4 | Department sites (WordPress) | cent (241 pages, 1,152 media): scraped (cent.py); meh (=tkl, 24 pages), motori (18 pages) | small | REST API | `X-WP-Total` |
| 5 | Department sites (hand-made) | ie, pt, hidro, fluidi, vaz, bmi, ppm, ciah (ASP.NET) | tiny, mostly static | Same-host crawl, depth-limited, all linked files | crawl frontier empty |
| – | Not reachable from outside | au, omk, tmm (DNS ok, connection times out) | ? | retry later / from faculty network | – |
| – | Login only, out of scope | studenti, zaposleni, konta, pretprijava (personal services); Moodle on fsel and on vaz (147.91.26.211, course keys) | – | skip | – |

The 15 departments without a link have no own site; their notices are in nastava's "катедре" forum.

## Base: Omar's dlwms (cloned in `ref/dlwms`, commit 3850b60)

Same architecture, new scrapers. dlwms: public repo → daily Actions cron → SQLite state as an encrypted
release asset → files as GitHub release assets (max 1000 per release) → static site on GitHub Pages →
Cloudflare Worker proxy on a custom domain with edge cache. This avoids the R2 10 GB and the
Workers 20k-file limits, and a public repo gets free Actions minutes.

| dlwms file | For MF |
|---|---|
| `fit_archive.py` (ASP.NET, login, postbacks) | **rewrite** as `nastava.py`: phpBB listing walk, no login |
| `documents.py` list/download (postbacks) | **rewrite**: attachments by `download/file.php?id=N` |
| `documents.py` extract (pdf/docx/pptx/xlsx/zip/rar, soffice) | reuse as-is |
| `index.py --text-only` | reuse; new `read_*` per source, base URLs |
| `pages/build.py`, templates, static, `search.js` | reuse; texts in Serbian, filters: izvor, predmet, godina |
| `pages/src/index.js` (Worker), `assets.py`, `release_files.py` | reuse; release per school year, split at 1000 assets |
| `ci/state.sh`, `ci/placeholders.py`, `sync.yml` | reuse; no login secrets needed |
| `app.py`, `common.py`, vectors, Docker | drop |

## nastava attachments: size and storage (counted 2026-11-09)

The `documents.size` column stays empty until the download, so these are the sizes phpBB shows next to each link
("(45.16 KiB) Downloaded 642 times"), summed from `posts.html` (rounded, so within a few MiB).

- **7.3 GiB** for 14,255 of the 14,265 ids in `documents` (10 show no size); 0.5 MiB on average.
- Largest 66, 61, 61 MiB; none over 100 MiB, so GitHub's 2 GiB per asset is no issue.
- Growth about 1.2 GiB a year lately.

| School year | Files | MiB |
|---|---|---|
| 2013/14 | 117 | 41 |
| 2014/15 | 640 | 257 |
| 2015/16 | 663 | 258 |
| 2016/17 | 717 | 192 |
| 2017/18 | 742 | 227 |
| 2018/19 | 758 | 254 |
| 2019/20 | 1,220 | 817 |
| 2020/21 | 1,740 | 902 |
| 2021/22 | 1,463 | 492 |
| 2022/23 | 1,236 | 431 |
| 2023/24 | 1,368 | 886 |
| 2024/25 | 1,311 | 1,362 |
| 2025/26 | 1,955 | 1,166 |
| 2026/27 (to Nov) | 329 | 194 |

Where they go:

- Local: `files/` in the repo (`documents.py`, override with `FILES`; gitignored). J: had 371 GB free.
- Public: GitHub release assets, one release per school year, split at 1000 assets: every year from 2019/20 has
  more than 1000, so about 21 releases. Served by the Worker's `/files/` route (dlwms `release_files.py`).
- Not R2: 7.3 GiB fits the 10 GB free tier now but would pass it in 2–3 years.
- The extracted text goes into `nastava.db`, which grows the `state` release asset on every sync.

## Phase 2: scrapers

- nastava: walk every subforum listing (with pages) → topic ids; fetch each topic page; attachments by id. Check: per-subforum counts and board totals = stored; attachment ids 1..max.
- Never delete: a post gone from the site stays, marked `gone`.
- Polite: 2 parallel requests, 0.5 s gap, backoff on errors. No logins.
- Files: magic-byte type, cut trailing HTML, detect HTML error pages, list no-text files for OCR.

## Daily refresh

- Built: the scheduled sync (README.md, "How it works").
- nastava: `search.php?search_id=active_topics` (last 7 days, public) + Atom feed + attachment ids above the last known. Weekly full listing reconcile (~1,500 requests).
- vesti / WordPress: REST `modified_after`. Static sites: weekly re-crawl.
- First full run (~4–6 h) runs locally, then the state goes to the release; Actions does the daily runs.

## Privacy

The sources are already public. The archive stays public. Optional: `noindex` so search engines don't index student lists through the archive.

## Later

- **Limit `POST /push`** (audit 2026-11-10). The Worker stores any well-formed subscription with no limit, so a
  script can fill KV with fake endpoints: KV's 1,000 writes a day run out (real visitors can't turn notifications on)
  and `ci/push.py send` makes a request per fake entry each run. Cloudflare's free rate-limiting rule (on the zone:
  domain → Security → Security rules) counts over 10 seconds only, too short to protect a daily quota. Better: the
  Workers rate-limit binding (`[[ratelimits]]` in `pages/wrangler.toml`, a 60 s period, keyed by `CF-Connecting-IP`
  in `push()` in `pages/src/index.js`); it covers both domains. A per-IP limit slows a flood, it does not cap the
  daily total.
- **Check the 60-day keepalive** (`sync.yml`, step "Keep the schedule on"): after a run, the sync workflow should
  still show as active with no "disabled soon" warning from GitHub. If `gh workflow enable` does not restart the 60
  days, the schedule stops after 60 days without a commit.
