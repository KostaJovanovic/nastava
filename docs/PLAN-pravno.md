# Plan: legal cleanup (2026-11-18)

From the legal audit (ZZPL, copyright). Decided with the user, one question at a time. Not started; built in one go
once all parts are agreed.

## 1. Files: links only (agreed)

Public build (a real build) links to originals only; the local server (dev mode, `output.dev`) keeps every file we
have downloaded.

Public build:
1. [ ] Board attachments since Oct 2026: link to `nastava.mas.bg.ac.rs/download/file.php?id=…`, no thumbnails
   (`load_board.hosted_files`, `clean.attachments`). Drop `documents.py host` from `ci/deploy.sh`.
2. [ ] Mail, Teams, Moodle: attachment names as plain text, no link (`load_sources.mail_file`, `file_rows`).
3. [ ] Old-site files: gone from subject pages, `/stari-sajt/` and the teachers' election reports (not even names).
   Kept only on old news posts (the 47 file news, the file links in `load_stare`'s texts), linked to the Wayback
   copy (default; the user did not pick, may change).
4. [ ] Document pages: extracted text stays in the Pagefind index, not shown on the page.
5. [ ] Worker: drop the `/files/` route (`releaseFile`).

Local server:
6. [ ] Links as today. `serve.py` serves `/files/` from disk, not masinci.org: `files-<year>` by `files/index.sqlite`
   → `files/blobs/`, `mail` from `mail/`, `stari-<host>` from `work/wayback/`; thumbnails made on request
   (`common.thumbnail`); a missing file 404.

Then:
7. [ ] Tests: public build has no `/files/` link; dev build keeps them; `serve.py` resolves one file of each kind.
8. [ ] Preview outside `pages/.build`; the user reviews and rebuilds.
9. [ ] Delete the releases `files-2026-2027` and `mail` after the deploy (confirm right before).
10. [ ] README.

## 2. Student lists: link to the original only (agreed)

Exam results with names and index numbers in archived text: 67 cent pages, 38 board posts, 8 department pages, at
least. Public build: the list is replaced by a note and a link to the faculty's page (its own retention applies).
Local server: shown as today.

1. [ ] Find them: a pattern (index numbers like `2021/0123`, more than 5 in a text) plus a hand-kept list for those
   it misses (names only).
2. [ ] Public build: the post or page shows the note and the source link in place of its text; left out of Pagefind
   too.
3. [ ] Test: a text with a list is replaced in the public build, kept in dev.

## 3. Privacy and "O sajtu" pages (agreed: no name, as masinac.org)

masinac.org names no one (founders "Vlada i Ivan", a contact form). The user chose the same: no name, contact by
mail (valjdakosta@gmail.com, as the photo takedown), knowing it falls short of ZZPL čl. 23's identity.

1. [ ] `privatnost.html`, new sections (casual Serbian, verzije style; wording asked per change):
   - what the archive holds about people: teachers' public work data, names in the faculty's posts; students' lists
     are not shown (part 2);
   - why: one search over the faculty's public notices (legitimate interest);
   - how long: as long as the source has it, or until a removal request;
   - your rights: see, correct, remove, object (by mail), and a complaint to the Poverenik (poverenik.rs);
   - Cloudflare: processes the requests, also in the US.
2. [ ] `o_sajtu.html` from `docs/o-sajtu.md`, with the note that the site is unofficial and not the faculty's.
3. [ ] Footer: a short "Nezvaničan sajt" line, linking O sajtu.

## 4. Teacher pages (agreed)

1. [ ] Living teachers (not `died`): no birth date in "Život" in the public build; the local server keeps it.
   Deceased: dates stay.
2. [ ] Check the summaries (`data/nastavnici-sazetak.jsonl`) of living teachers for a birth date or place; list
   them for the user before any change (summary rules: [[summary-rewrite-rules]] memory).
3. [ ] Under the summary's source note: a mail link to report an error (as the photo's takedown link).

## 5. Removal and corrections (agreed)

1. [ ] Footer (`base.html:120`): the link "Piši mi :)" (valjdakosta.com/guestbook) becomes a mailto to
   valjdakosta@gmail.com for removal or correction; the subject names the page (site.js fills its URL; without JS a
   plain subject). Wording asked.
2. [ ] The privacy page's rights section: the same mailto.
3. [ ] Doing a removal: a hand-kept list the public build leaves out (posts, pages, names), shared with part 2's
   hand-kept list of student lists; the local server ignores it.

Note: mail result files were already redacted (`work/withhold.py`, commits 8dd1673, 3d84ccf; `common.lists_students`
finds lists). Part 2 reuses `lists_students`' index-number rule for texts.

## 6. Mail, Teams, Moodle posts (agreed: teachers' only)

1. [ ] Public build: only the teachers' posts; the students' replies ("Student #N") left out (`load_mail`). The
   local server keeps them.
2. [ ] Test: a thread with a student's reply has none in the public build.

## 7. Small

1. [ ] Fonts: the OFL licence text next to Geist, IBM Plex and Roboto Mono in `pages/static/fonts/`.
2. [ ] Cloudflare in the privacy page (part 3).
3. [ ] Visitor counter (`pages/src/index.js` visit): store SHA-256(IP + period + a Worker secret `COUNTER_SALT`), not
   the IP; the user sets the secret once (`npx wrangler secret put COUNTER_SALT` in `pages/`). The rows of the
   period running then hold raw IPs until they expire (3 days). Privacy page: "IP se ne čuva, samo njen otisak".
