#!/usr/bin/env bash
# Build the site on this PC and publish it. The scraping and building happen here; GitHub only hosts the result:
# the site goes up as an asset of the "site" release, and the deploy workflow puts it on GitHub Pages as it is.
# Usage: bash ci/deploy.sh [sync]   (from the repo root)
#   sync   run the scrapers first (posts, schedule pages, teachers, subjects), then build and publish
# shortcut: everything runs on a PC for now; when the daily run moves to Actions, put the cron back in sync.yml.
set -euo pipefail
repo=KostaJovanovic/nastava
export PYTHONIOENCODING=utf-8

if [[ ${1:-} == sync ]]; then
	uv run nastava.py sync
	uv run studije.py sync
	uv run nastavnici.py sync
	uv run predmeti.py sync
	# Missing posts are reported, not fatal: the site is still published, as the daily run did.
	uv run nastava.py stats || echo "stats: posts missing, publishing anyway" >&2
fi

uv run pages/build.py nastava.db pages/.build
npx -y pagefind@1.6.0 --site pages/.build/site
uv run pages/build.py --strip pages/.build/site

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
