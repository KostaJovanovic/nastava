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
	gh release download state -R "$repo" -p "$name" -O - | zstd -dq | tar -x
	echo "pulled $name"
	;;
push)
	name=state-$(date -u +%Y%m%d-%H%M%S).tar.zst
	tmp=$(mktemp -d)
	trap 'rm -rf "$tmp"' EXIT
	# Fold the WAL into the file: tar takes only nastava.db.
	python3 -c "import sqlite3; sqlite3.connect('nastava.db').execute('pragma wal_checkpoint(truncate)')"
	tar -c nastava.db | zstd -q -T0 -10 -o "$tmp/$name"
	gh release view state -R "$repo" >/dev/null 2>&1 ||
		gh release create state -R "$repo" --latest=false --title state --notes "Scraper state for the daily sync."
	gh release upload state -R "$repo" "$tmp/$name"
	# Keep the two newest, so a bad run does not remove the last good state.
	gh release view state -R "$repo" --json assets -q '.assets[].name' | sort | head -n -2 |
		xargs -r -I{} gh release delete-asset state {} -R "$repo" -y
	echo "pushed $name ($(du -h "$tmp/$name" | cut -f1))"
	;;
*)
	echo "usage: $0 pull | push" >&2
	exit 2
	;;
esac
