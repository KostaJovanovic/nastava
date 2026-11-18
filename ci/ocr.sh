#!/usr/bin/env bash
# OCR the site's own attachments on this PC's graphics card and save the state (save.bat ocr). No scrape, no build:
# the text goes up with the state, and the next build uses it.
#   get the state (ci/state.sh pull), documents.py ocr, save the state (ci/state.sh push)
# Not beside a scheduled run: if one started or saved while this ran, nothing is saved (the state that run saved would
# be overwritten) and the files are read again next time.
# Usage: bash ci/ocr.sh   (from the repo root)
set -euo pipefail
repo=KostaJovanovic/nastava
export PYTHONIOENCODING=utf-8

running() {
	gh run list -R "$repo" -w sync.yml -L 20 --json status \
		-q '[.[] | select(.status | test("in_progress|queued|waiting|pending"))] | length'
}
newest() { gh release view state -R "$repo" --json assets -q '.assets[].name' | sort | tail -n 1; }
looked() {  # the attachments looked at so far
	uv run -q --no-project python -c "
import sqlite3; db = sqlite3.connect('nastava.db')
cols = {r[1] for r in db.execute('pragma table_info(documents)')}
print(db.execute('select count(ocr) from documents').fetchone()[0] if 'ocr' in cols else 0)" | tr -d '\r'
}

if (($(running))); then
	echo "a sync.yml run is going (gh run list -R $repo -w sync.yml): run this after it" >&2
	exit 1
fi
bash ci/state.sh pull
pulled=$(newest)
before=$(looked)
uv run scrapers/documents.py ocr
if [[ $(looked) == "$before" ]]; then
	echo "nothing new looked at: no save"
	exit 0
fi
if (($(running))) || [[ $(newest) != "$pulled" ]]; then
	echo "a scheduled run started or saved meanwhile: not saved. Run save.bat ocr again after it." >&2
	exit 1
fi
bash ci/state.sh push
