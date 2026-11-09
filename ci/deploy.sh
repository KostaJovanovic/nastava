#!/usr/bin/env bash
# Build the site on this PC and publish it. The scraping and building happen here; GitHub only hosts the result:
# the site goes up as an asset of the "site" release, and the deploy workflow puts it on GitHub Pages as it is.
# Usage: bash ci/deploy.sh [sync|forum]   (from the repo root)
#   sync   test the parsers, run the scrapers (posts, schedule pages, teachers, subjects), save the state
#          (ci/state.sh push), then build and publish
#   forum  the same, but only the board (the one daily changing source; the other scrapers ~8 min of unchanged pages)
# As in sync.yml: missing posts or a failed side scraper do not stop the publish, but the script exits 1 at the end.
# shortcut: everything runs on a PC for now; when the daily run moves to Actions, put the cron back in sync.yml.
set -euo pipefail
repo=KostaJovanovic/nastava
export PYTHONIOENCODING=utf-8
failed=()

if [[ ${1:-} == sync || ${1:-} == forum ]]; then
	uv run test/parsers_test.py
	uv run nastava.py sync
	# Right after the scrape, so a post made since then does not count as missing.
	uv run nastava.py stats || failed+=(stats)
	if [[ $1 == sync ]]; then
		uv run studije.py sync || failed+=(studije)
		uv run nastavnici.py sync || failed+=(nastavnici)
		uv run predmeti.py sync || failed+=(predmeti)
	fi
	bash ci/state.sh push
fi

uv run pages/build.py nastava.db pages/.build

name=site-$(date -u +%Y%m%d-%H%M%S).tar.gz
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
tar -czf "$tmp/$name" -C pages/.build/site .
gh release view site -R "$repo" >/dev/null 2>&1 ||
	gh release create site -R "$repo" --latest=false --title site --notes "The built site, published by the deploy workflow."
gh release upload site -R "$repo" "$tmp/$name"
# Keep the two newest, so a bad build can be published back over.
gh release view site -R "$repo" --json assets -q '.assets[].name' | sort | head -n -2 |
	xargs -r -I{} gh release delete-asset site {} -R "$repo" -y
gh workflow run deploy.yml -R "$repo"
echo "uploaded $name ($(du -h "$tmp/$name" | cut -f1)); deploy started: gh run list -R $repo -w deploy"
if ((${#failed[@]})); then
	echo "failed: ${failed[*]} (published anyway)" >&2
	exit 1
fi
