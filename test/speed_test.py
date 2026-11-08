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
	for label in ('мастер академске студије - МИ', 'катедре', ''):
		before = page.inner_text('#res-h')
		t = time.time()
		page.locator(f'input[name="smer"][value="{label}"]').check()
		page.wait_for_function('b => document.querySelector("#res-h")?.textContent !== b', arg=before)
		page.wait_for_load_state('networkidle')
		print(f'click smer {label or "Svi"!r}: {time.time() - t:.2f}s -> {page.inner_text("#res-h")}')
