"""Script switch and side panel checks in Edge: python pismo_test.py <base url> <item path> <out dir>."""
import re
import sys

from playwright.sync_api import sync_playwright

base, item, out = sys.argv[1].rstrip('/'), sys.argv[2], sys.argv[3]
sys.stdout.reconfigure(encoding='utf-8')
CYR = re.compile(r'[Ѐ-ӿ]')
LAT_WORD = re.compile(r'\b[a-zčćšžđ]{4,}\b')


def main_text(page):
	return page.inner_text('main')


def pismo(page, mode):
	"""Click the script button (it cycles lat → cyr → orig) until it is on mode."""
	for _ in range(3):
		if page.get_attribute('#pismo', 'data-pismo') == mode:
			return
		page.click('#pismo')
	assert page.get_attribute('#pismo', 'data-pismo') == mode, mode


with sync_playwright() as p:
	browser = p.chromium.launch(channel='msedge')
	page = browser.new_page(viewport={'width': 1366, 'height': 900})
	errors = []
	page.on('pageerror', lambda e: errors.append(str(e)))

	page.goto(f'{base}/{item}/')
	page.wait_for_load_state('networkidle')
	original = page.evaluate("() => fetch(location.href).then(r => r.text())")
	lat = main_text(page)
	print('default latin, cyrillic letters left in main:', len(CYR.findall(lat)), '| button:', page.get_attribute('#pismo', 'data-pismo'))
	assert not CYR.findall(lat), lat[:300]
	page.screenshot(path=f'{out}/pismo-lat.png')

	pismo(page, 'cyr')
	cyr = main_text(page)
	print('cyrillic: latin words left:', LAT_WORD.findall(cyr.lower())[:8], '| title:', page.title())
	page.screenshot(path=f'{out}/pismo-cyr.png')

	pismo(page, 'orig')
	orig = main_text(page)
	first_line = re.search(r'<h1 class="post__title" id="title">(.*?)</h1>', original, re.S).group(1).strip()
	print('original restored, title matches the built page:', page.inner_text('h1#title') == first_line)
	assert page.inner_text('h1#title') == first_line

	pismo(page, 'lat')
	assert main_text(page) == lat, 'switching back to latin gave a different text'
	print('back to latin: identical')

	# A side panel choice on an item page opens the search with that filter.
	page.locator('input[name="smer"]').nth(1).check()
	page.wait_for_url(re.compile(r'smer='))
	page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('rezultat')")
	page.wait_for_load_state('networkidle')
	print('smer from an item page ->', page.url.split('?')[1][:80], '|', page.inner_text('#res-h'))
	page.screenshot(path=f'{out}/pismo-search.png')

	# The choice is remembered on the next page.
	pismo(page, 'cyr')
	page.goto(f'{base}/')
	print('remembered on the next page:', page.get_attribute('#pismo', 'data-pismo') == 'cyr', '| heading:', page.inner_text('#res-h'))
	pismo(page, 'lat')

	# The theme button: from the system's scheme (light here) to dark, then light; remembered on the next page.
	scheme = lambda: page.evaluate("getComputedStyle(document.documentElement).colorScheme")
	themes = []
	for _ in range(2):
		page.click('#tema')
		themes.append((page.get_attribute('html', 'data-tema'), scheme(), page.get_attribute('#tema', 'aria-label')))
	print('theme clicks:', themes)
	assert themes == [('dark', 'dark', 'Tema: tamna'), ('light', 'light', 'Tema: svetla')], themes
	page.click('#tema')
	page.goto(f'{base}/')
	assert page.get_attribute('html', 'data-tema') == 'dark'
	page.click('#tema')

	phone = browser.new_page(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True)
	phone.goto(f'{base}/{item}/')
	phone.wait_for_load_state('networkidle')
	phone.screenshot(path=f'{out}/pismo-phone.png')
	print('page errors:', errors or 'none')
	browser.close()
