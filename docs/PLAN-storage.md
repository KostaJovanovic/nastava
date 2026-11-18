# Plan: one copy per file in files/ (2026-11-18)

Decided with the user ("carefully"). Not started.

## Why

`files/` holds 14,309 attachments in a folder each (`files/<id>/<name>`, 7.32 GiB), but only 11,438 distinct
files (5.22 GiB): 2.1 GiB are copies (one file is there 18 times). And nothing notices a damaged file (20784).

## What stays as it is

- `nastava.db`: not touched. `documents.path` (`<id>/<name>`) stays the file's name: the hosted files' URLs are
  built from it (`asset_name(path)`, `pages/sitegen/load_board.py`), so a new path would break every shared link.
  And the database is merged with the GitHub runs' copy (`ci/state_merge.py`: its rows win), so a change to
  existing rows here could be lost or overwrite newer scrapes.
- The releases, the Worker, the site, `files/sites/` (`site_files.py`), `files/ocr.jsonl` (keyed by `path`, which
  stays), `files/no-text.txt`.

## The new layout

- `files/blobs/<first 2 hex>/<sha256><.ext>`: each distinct file once (256 folders of ~45).
- `files/index.sqlite`, table `files (path primary key, sha256, size)`: `<id>/<name>` → its copy. Local only, like
  `files/` (git-ignored); a GitHub run starts with none.
- `scrapers/documents.py`: one function finds a file (`index.sqlite`, else the old place `files/<path>`, so a run
  mid-move and the GitHub runs keep working) and one stores it (blob + index row). The five places that join
  `FILES` with a path use them. `stats` gains a check: every blob's hash still matches its name.

## Steps, each checked before the next

1. A dry run of the move script (`work/storage/move.py`): counts only (files, distinct, bytes), changes nothing.
2. The move: copy, never move, each file into `blobs/` (J: has the room); read every copy back and compare its
   SHA-256; write `index.sqlite`. The old folders stay. Check: as many index rows as files, every blob hashes to its
   name, and the bytes of every path through the index equal the old file's.
3. `documents.py` switched to the two functions; its tests and `build_test.py` pass; `documents.py extract` on a
   few files gives the same text as before.
4. Only with the user's yes, asked right before: delete the old numbered folders (`files/<id>/`). Until then they
   are the backup.
5. README: the new layout.

## Open

- Whether the GitHub releases should drop their copies too (a file posted again is a new asset now). Not part of
  this plan.
