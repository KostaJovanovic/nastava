"""Real searches and screenshots in Edge: python browser_test.py <base url> <out dir>."""
import sys

from playwright.sync_api import sync_playwright

base, out = sys.argv[1].rstrip('/'), sys.argv[2]
QUERIES = ['rezultati', 'резултати', 'diskretna', 'дискретна', 'ispitna pitanja', 'rasporedjen', 'kolokvijum', 'Ђукић', 'djukic']

sys.stdout.reconfigure(encoding='utf-8')
with sync_playwright() as p:
	browser = p.chromium.launch(channel='msedge')
	page = browser.new_page(viewport={'width': 1366, 'height': 900})
	errors = []
	page.on('pageerror', lambda e: errors.append(str(e)))
	for q in QUERIES:
		page.goto(f'{base}/?q={q}')
		page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('rezultat')", timeout=20000)
		page.wait_for_load_state('networkidle')  # the rows render after the heading, once their fragments load
		heading = page.inner_text('#res-h')
		first = page.locator('.row .t a').first
		print(f'{q!r:20} -> {heading!r:40} {first.inner_text() if first.count() else "-"}')
	done = "document.querySelector('#res-h')?.textContent.includes('rezultat')"
	page.goto(f'{base}/?q=rezultati')
	page.wait_for_function(done)
	page.screenshot(path=f'{out}/desktop-search.png')
	# Extra arguments: site paths to screenshot, for example item/p123 or smer/4.
	for path in sys.argv[3:]:
		page.goto(f'{base}/{path}/')
		page.screenshot(path=f'{out}/desktop-{path.replace("/", "-")}.png')
	phone = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True)
	phone.goto(f'{base}/?q=diskretna')
	phone.wait_for_function(done)
	phone.screenshot(path=f'{out}/phone-search.png')
	if sys.argv[3:]:
		phone.goto(f'{base}/{sys.argv[3]}/')
		phone.screenshot(path=f'{out}/phone-{sys.argv[3].replace("/", "-")}.png')
	# A smer filter from the URL, as the subject page links it.
	page.goto(f'{base}/?smer=катедре')
	page.wait_for_function(done)
	page.wait_for_load_state('networkidle')
	print('smer filter:', page.inner_text('#res-h'), '| first:', page.locator('.row .s').first.inner_text())
	print('page errors:', errors or 'none')
	browser.close()
