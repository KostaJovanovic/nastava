"""Time page loads and filter clicks in Edge: python speed_test.py <base url> <site dir>."""
import os
import sys
import time

from playwright.sync_api import sync_playwright

base, site = sys.argv[1].rstrip('/'), sys.argv[2]
sys.stdout.reconfigure(encoding='utf-8')
for d in ('smer',):
	for name in sorted(os.listdir(os.path.join(site, d))):
		print(f'{d}/{name}: {os.path.getsize(os.path.join(site, d, name, "index.html")) // 1024} KB')
print('index.html:', os.path.getsize(os.path.join(site, 'index.html')) // 1024, 'KB')

done = "document.querySelector('#res-h')?.textContent.includes('rezultat')"
with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page()
	for path in ('/smer/oas-mi/', '/smer/mas-mi/'):
		t = time.time()
		page.goto(base + path, wait_until='load')
		print(f'{path} load: {time.time() - t:.2f}s')
	t = time.time()
	page.goto(base + '/', wait_until='load')
	page.wait_for_function('window.performance && document.readyState === "complete"')
	print(f'/ load: {time.time() - t:.2f}s')
	page.wait_for_load_state('networkidle')
	# A smer comes from a link now (the side panel picks subjects).
	for key in ('mas-mi', 'katedre'):
		t = time.time()
		page.goto(f'{base}/?smer={key}')
		page.wait_for_function(done)
		page.wait_for_load_state('networkidle')
		print(f'smer {key!r}: {time.time() - t:.2f}s -> {page.inner_text("#res-h")}')
