"""Teacher list filter and profile pages: python nastavnici_test.py <base url>."""
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip('/')
sys.stdout.reconfigure(encoding='utf-8')
with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page(viewport={'width': 1400, 'height': 900})
	errors = []
	page.on('pageerror', lambda e: errors.append(str(e)))
	shown = lambda: page.locator('[data-teachers] .row:visible').count()
	page.goto(base + '/nastavnici/')
	print('all:', shown(), '| heading:', page.inner_text('#title'))
	page.screenshot(path='test/nastavnici.png')
	for q in ['djukic', 'Ђукић', 'matematika 1', 'termotehnik', '440']:
		page.fill('#t-q', q)
		print(f'{q!r}:', shown(), page.locator('[data-teachers] .row:visible .t').all_inner_texts()[:3])
	page.fill('#t-q', '')
	page.select_option('#t-k', 'Катедра за математику')
	print('katedra matematika:', shown(), '| url:', page.url.split('/', 3)[-1])
	page.select_option('#t-z', 'доцент')
	print('+ docent:', shown())
	page.goto(base + '/nastavnici/?katedra=' + 'Катедра за математику')
	print('from url:', shown())
	page.goto(base + '/nastavnik/52/')
	print('profile h1:', page.inner_text('h1'), '| archived subjects:', page.locator('.dside .lnk[href^="/predmet/"]').count(),
		'| posts:', page.locator('.rows .row').count())
	page.screenshot(path='test/nastavnik.png')
	page.click('[data-pismo="orig"]')
	print('original script h1:', page.inner_text('h1'))
	page.click('[data-pismo="lat"]')
	page.goto(base + '/predmet/' + page.locator('.dside .lnk[href^="/predmet/"]').first.get_attribute('href').split('/')[2] + '/')
	print('subject page teachers:', page.locator('.sugg a[href^="/nastavnik/"]').all_inner_texts())
	print('page errors:', errors or 'none')
