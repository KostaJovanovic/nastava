#!/usr/bin/env bash
# Get or save nastava.db as an asset of the "state" release.
# Usage: ci/state.sh pull | push   (in the directory that holds nastava.db)
# Not encrypted: the database holds only what the public board shows.
set -euo pipefail
repo=${GITHUB_REPOSITORY:-KostaJovanovic/nastava}

case ${1:-} in
pull)
	# The asset names have a UTC time stamp, so the last name in sort order is the newest.
	name=$(gh release view state -R "$repo" --json assets -q '.assets[].name' | sort | tail -n 1)
	[[ -n $name ]] || { echo "no state asset" >&2; exit 1; }
	# Into the database through SQLite's backup, not over the file: a running dev server (pages/serve.py) keeps
	# nastava.db and its WAL open, and Windows neither deletes nor replaces an open file. The server sees the change
	# and restarts.
	gh release download state -R "$repo" -p "$name" -O - | uv run --no-project --python 3.14 python -c "
import sqlite3, sys, tarfile, tempfile
with tempfile.TemporaryDirectory() as tmp:
    tarfile.open(fileobj=sys.stdin.buffer, mode='r|zst').extractall(tmp, filter='data')
    src, dst = sqlite3.connect(tmp + '/nastava.db'), sqlite3.connect('nastava.db', timeout=60)
    src.backup(dst)
    dst.close(); src.close()"
	echo "pulled $name"
	;;
push)
	name=state-$(date -u +%Y%m%d-%H%M%S).tar.zst
	tmp=$(mktemp -d)
	trap 'rm -rf "$tmp"' EXIT
	# Fold the WAL into the file: the archive takes only nastava.db. Through uv: on Windows python3 is the Store
	# stub. Python 3.14's tarfile writes zstd itself, so no zstd binary is needed.
	uv run --no-project --python 3.14 python -c "
import sqlite3, sys, tarfile
sqlite3.connect('nastava.db').execute('pragma wal_checkpoint(truncate)')
with tarfile.open(sys.argv[1], 'w:zst', level=10) as t: t.add('nastava.db')" "$tmp/$name"
	gh release view state -R "$repo" >/dev/null 2>&1 ||
		gh release create state -R "$repo" --latest=false --title state --notes "Scraper state for the daily sync."
	gh release upload state -R "$repo" "$tmp/$name"
	# Keep the two newest, so a bad run does not remove the last good state.
	gh release view state -R "$repo" --json assets -q '.assets[].name' | sort | head -n -2 |
		xargs -r -I{} gh release delete-asset state {} -R "$repo" -y
	echo "pushed $name ($(du -h "$tmp/$name" | cut -f1))"
	# Its size for the run log (ci/deploy.sh, ci/runs.py).
	if [[ -n ${RUN_DIR:-} ]]; then wc -c < "$tmp/$name" > "$RUN_DIR/state"; fi
	;;
*)
	echo "usage: $0 pull | push" >&2
	exit 2
	;;
esac
