"""Teacher list filter and profile pages: python nastavnici_test.py <base url>."""
import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip('/')
sys.stdout.reconfigure(encoding='utf-8')
with sync_playwright() as p:
	page = p.chromium.launch(channel='msedge').new_page(viewport={'width': 1400, 'height': 900})
	errors = []
	page.on('pageerror', lambda e: errors.append(str(e)))
	shown = lambda: page.locator('[data-rows] > li:visible').count()
	page.goto(base + '/nastavnici/')
	print('all:', shown(), '| heading:', page.inner_text('#title'))
	page.screenshot(path='test/nastavnici.png')
	for q in ['djukic', 'Ђукић', 'matematika 1', 'termotehnik', '440']:
		page.fill('#t-q', q)
		print(f'{q!r}:', shown(), page.locator('[data-rows] > li:visible .pc__a').all_inner_texts()[:3])
	page.fill('#t-q', '')
	# A filter's value is the name's Latin slug: the URL has no Cyrillic.
	page.select_option('#t-k', 'katedra-za-matematiku')
	print('katedra matematika:', shown(), '| url:', page.url.split('/', 3)[-1])
	assert page.url.endswith('?katedra=katedra-za-matematiku'), page.url
	page.select_option('#t-z', 'docent')
	print('+ docent:', shown())
	page.goto(base + '/nastavnici/?katedra=katedra-za-matematiku')
	print('from url:', shown())
	assert shown() == 8
	page.goto(base + '/nastavnik/dusan-lj-djukic/')
	print('profile h1:', page.inner_text('h1'), '| archived subjects:', page.locator('.tp__subj a[href^="/predmet/"]').count(),
		'| posts:', page.locator('.tp__posts li').count())
	page.screenshot(path='test/nastavnik.png')
	page.click('#pismo')
	page.click('#pismo')
	print('original script h1:', page.inner_text('h1'), '| button:', page.get_attribute('#pismo', 'data-pismo'))
	page.click('#pismo')
	page.goto(base + page.locator('.tp__subj a').first.get_attribute('href'))
	print('subject page teachers:', page.locator('.mh__sub a[href^="/nastavnik/"]').all_inner_texts())
	# The topic filter of a subject page, by author.
	before = shown()
	page.select_option('#f-a', index=1)
	print('subject topics:', before, '-> by', page.locator('#f-a option:checked').inner_text(), shown(), '| url:', page.url.split('?')[1])
	assert 0 < shown() <= before
	assert not errors
	print('page errors:', errors or 'none')
