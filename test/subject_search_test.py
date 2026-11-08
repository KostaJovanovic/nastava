"""Subject search in the side panel keeps the original names and marks the right letters:
python subject_search_test.py <base url>."""
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip('/')
sys.stdout.reconfigure(encoding='utf-8')
with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page()
	errors = []
	page.on('pageerror', lambda e: errors.append(str(e)))
	marks = lambda: page.locator('[data-subject-list] label:visible mark').all_inner_texts()
	for url in ['/', '/nastavnici/']:  # inline list, and the list loaded from /predmeti.html
		page.goto(base + url)
		page.wait_for_load_state('networkidle')
		page.click('[data-pismo="lat"]')
		page.fill('#subj-q', 'lj')
		lat = marks()
		page.click('[data-pismo="orig"]')
		page.fill('#subj-q', 'meh')
		names = page.locator('[data-subject-list] label:visible .opt__name').all_inner_texts()
		print(url, '| lat marks for "lj":', sorted(set(lat))[:4], '| orig names for "meh":', names[:3])
		assert lat and all(m.lower() == 'lj' for m in lat), lat
		assert names and all(any('Ѐ' <= c <= 'ӿ' for c in n) for n in names[:3]), names
	page.click('[data-pismo="lat"]')
	print('page errors:', errors or 'none')
	assert not errors
