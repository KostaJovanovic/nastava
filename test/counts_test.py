"""The filter counts must not change when a value of the same group is picked: python counts_test.py <base url>."""
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip('/')
sys.stdout.reconfigure(encoding='utf-8')


def counts(page, name):
	return {page.locator(f'input[name="{name}"]').nth(i).get_attribute('value') or 'svi':
		page.locator(f'input[name="{name}"]').nth(i).locator('xpath=..').locator('.n').inner_text()
		for i in range(page.locator(f'input[name="{name}"]').count())}


with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page()
	seen = {}
	for url in ['/?q=ispit', '/?q=ispit&smer=катедре', '/?q=ispit&smer=мастер академске студије - МИ']:
		page.goto(base + url)
		page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('rezultat')")
		page.wait_for_load_state('networkidle')
		seen[url] = counts(page, 'smer')
		print(url, '->', page.inner_text('#res-h'), seen[url])
	assert len({tuple(c.items()) for c in seen.values()}) == 1, 'smer counts changed when a smer was picked'
	print('ok: smer counts stay the same')
