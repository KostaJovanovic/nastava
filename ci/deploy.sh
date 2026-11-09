#!/usr/bin/env bash
# Build the site and publish it, on this PC or in the scheduled run (sync.yml): the site goes up as an asset of the
# "site" release, and the deploy workflow puts it on GitHub Pages as it is.
# Usage: bash ci/deploy.sh [sync|forum]   (from the repo root)
#   sync   test the parsers, get the state (ci/state.sh pull), run the scrapers (posts, news, schedule pages, teachers,
#          subjects), save the state (ci/state.sh push), build, publish, then the web push of the new posts
#   forum  the same, but only the board and the news (the daily changing sources; the other scrapers ~8 min of
#          unchanged pages)
#   (none) build and publish this copy's nastava.db
# Missing posts or a failed side scraper do not stop the publish, but the script exits 1 at the end.
set -euo pipefail
repo=KostaJovanovic/nastava
export PYTHONIOENCODING=utf-8
failed=()

if [[ ${1:-} == sync || ${1:-} == forum ]]; then
	uv run test/parsers_test.py
	# The saved state, not this PC's copy: the scheduled run on Actions (sync.yml) may be newer, and an older copy
	# would scrape and notify its posts again.
	bash ci/state.sh pull
	# The newest post before the scrape: the posts after it get a web push once published (ci/push.py).
	before=$(uv run -q ci/push.py last) || before=
	uv run nastava.py sync
	# Right after the scrape, so a post made since then does not count as missing.
	uv run nastava.py stats || failed+=(stats)
	# The news change daily too, and all of them are ~46 requests.
	uv run vesti.py sync || failed+=(vesti)
	# The subjects' pages on cent.mas.bg.ac.rs: ~40 requests a run.
	uv run cent.py sync || failed+=(cent)
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
# It waits until the new posts are on the site. Without the keys (push-secret.json; on Actions the secret PUSH_SECRET)
# there is no push.
if [[ -n ${before:-} && -f push-secret.json ]]; then
	# Unquoted: three numbers (post, cent notice, cent page version).
	uv run -q ci/push.py send $before || failed+=(push)
fi
if ((${#failed[@]})); then
	echo "failed: ${failed[*]} (published anyway)" >&2
	exit 1
fi
