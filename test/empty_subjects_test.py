"""Subjects with 0 results are hidden: python empty_subjects_test.py <base url>."""
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip('/')
sys.stdout.reconfigure(encoding='utf-8')
with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page()
	errors = []
	page.on('pageerror', lambda e: errors.append(str(e)))
	visible = lambda: page.locator('[data-subject-list] label:visible')
	page.goto(base + '/')
	page.wait_for_load_state('networkidle')
	print('home, subjects shown:', visible().count())
	page.locator('input[name="smer"][value="катедре"]').check()
	page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('rezultat')")
	page.wait_for_load_state('networkidle')
	counts = [visible().nth(i).locator('.n').inner_text() for i in range(visible().count())]
	print('smer katedre, subjects shown:', len(counts), '| any 0:', '0' in counts)
	assert counts and '0' not in counts
	page.fill('#subj-q', 'meh')
	print('subject search hint:', page.inner_text('[data-subject-hint]'))
	page.locator('input[name="smer"][value=""]').check()
	page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('Najnovije')")
	page.fill('#subj-q', '')
	print('cleared, subjects shown again:', visible().count())
	print('page errors:', errors or 'none')
