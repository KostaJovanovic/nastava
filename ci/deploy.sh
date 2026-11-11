#!/usr/bin/env bash
# Scrape, build and publish: the scheduled run (sync.yml) and this PC (by hand, as an override) run the same steps.
# The site goes up as an asset of the "site" release, and the deploy workflow puts it on GitHub Pages as it is.
# Usage: bash ci/deploy.sh [auto SLOT | sync | forum [studije] [nastavnici] [predmeti] [katedre]]   (from the repo root)
#   auto SLOT  the scheduled run: SLOT is morning, noon, afternoon, evening or night; ci/plan.py picks the scrapers from the faculty's
#              teaching calendar, or "skip" (stop at once)
#   sync       every scraper: the board, the news, the schedule pages, the teachers, the subjects, the departments'
#              sites
#   forum ...  the board and the news, and the scrapers named after it
#   (none)     build and publish this copy's nastava.db, nothing scraped
# A scrape first gets the saved state (ci/state.sh pull), so this PC goes on from the last scheduled run. When the
# scrapers changed nothing (ci/plan.py fingerprint), the state is not saved. Then: build, publish (the footer shows
# when the board was read), then the web push of the new posts. Missing posts, a failed scraper, a failed push or an unreadable
# calendar do not stop the rest, but the script exits 1 at the end (a red run: GitHub's e-mail).
set -euo pipefail
repo=KostaJovanovic/nastava
export PYTHONIOENCODING=utf-8
failed=()
finish() {
	if ((${#failed[@]})); then
		echo "failed: ${failed[*]}" >&2
		exit 1
	fi
	exit 0
}

if [[ ${1:-} == auto || ${1:-} == sync || ${1:-} == forum ]]; then
	# The saved state, not this PC's copy: the scheduled run may be newer, and an older copy would scrape and notify
	# its posts again.
	bash ci/state.sh pull
	parts=("$@")
	if [[ $1 == auto ]]; then
		# tr: on Windows, Python ends its lines with \r\n.
		plan=$(uv run -q ci/plan.py "${2:?usage: deploy.sh auto morning|noon|afternoon|evening|night}" | tr -d '\r')
		echo "plan for the $2 run: $plan"
		read -ra parts <<< "$plan"
		[[ ${parts[0]} == skip ]] && exit 0
		# Once a day: a calendar the next days' runs can read.
		if [[ $2 == evening ]]; then  # the last run every day has (night is on hot days only)
			uv run -q ci/plan.py check || failed+=(kalendar)
		fi
	elif [[ $1 == sync ]]; then
		# katedre: the departments' own sites, a crawl of every page, ~600 requests.
		parts=(forum studije nastavnici predmeti katedre)
	fi
	for p in "${parts[@]:1}"; do
		[[ $p == studije || $p == nastavnici || $p == predmeti || $p == katedre ]] || { echo "unknown scraper: $p" >&2; exit 2; }
	done
	uv run test/parsers_test.py
	# The newest post before the scrape: the posts after it get a web push once published (ci/push.py).
	before=$(uv run -q ci/push.py last | tr -d '\r') || before=
	print=$(uv run -q ci/plan.py fingerprint | tr -d '\r')
	uv run nastava.py sync
	# Right after the scrape, so a post made since then does not count as missing.
	uv run nastava.py stats || failed+=(stats)
	# The news change daily too, and all of them are ~46 requests.
	uv run vesti.py sync || failed+=(vesti)
	# The subjects' pages on cent.mas.bg.ac.rs: ~40 requests a run.
	uv run cent.py sync || failed+=(cent)
	for p in "${parts[@]:1}"; do
		uv run "$p.py" sync || failed+=("$p")
	done
	# Nothing changed: no save, but still a build and publish, so the footer's "Provereno" shows this run's time.
	if [[ $(uv run -q ci/plan.py fingerprint | tr -d '\r') == "$print" ]]; then
		echo "nothing changed: no save; build and publish for the time checked"
	else
		bash ci/state.sh push
	fi
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
finish
