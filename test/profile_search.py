"""Time the parts of one filter click with Pagefind directly in the page: python profile_search.py <base url>."""
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
JS = """async () => {
  const pf = await import('/pagefind/pagefind.js');
  await pf.options({ excerptLength: 30 });
  await pf.filters();
  const t = () => performance.now();
  const out = {};
  const all = { vrsta: { any: ['obavestenje', 'dokument'] } };
  const smer = { ...all, smer: { any: ['катедре'] } };
  let a = t(); let r = await pf.search(null, { filters: smer, sort: { datum: 'desc' } }); out.search_sorted = t() - a;
  a = t(); await pf.search(null, { filters: smer }); out.search_unsorted = t() - a;
  a = t(); await pf.search(null, { filters: all }); out.counts_search = t() - a;
  a = t(); await Promise.all(r.results.slice(0, 20).map((x) => x.data())); out.fragments_20 = t() - a;
  a = t(); r = await pf.search(null, { filters: all, sort: { datum: 'desc' } }); out.search_all_sorted = t() - a;
  return out;
}"""
with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page()
	page.goto(sys.argv[1].rstrip('/') + '/')
	page.wait_for_load_state('networkidle')
	for run in (1, 2):
		print(run, {k: round(v) for k, v in page.evaluate(JS).items()}, 'ms')
