"""Teacher list filter and profile pages: python nastavnici_test.py <base url>."""
import re
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
		page.fill('#q', q)  # the header search filters the list on this page
		print(f'{q!r}:', shown(), page.locator('[data-rows] > li:visible .pc__a').all_inner_texts()[:3])
	assert page.input_value('#qk') == 'nastavnici' and 'q=440' in page.url
	page.fill('#q', '')
	# A filter's value is the name's Latin slug: the URL has no Cyrillic.
	page.select_option('#t-k', 'katedra-za-matematiku')
	in_katedra = shown()
	print('katedra matematika:', in_katedra, '| url:', page.url.split('/', 3)[-1])
	assert page.url.endswith('?katedra=katedra-za-matematiku'), page.url
	page.select_option('#t-z', 'docent')
	print('+ docent:', shown())
	page.goto(base + '/nastavnici/?katedra=katedra-za-matematiku')
	print('from url:', shown())
	assert shown() == in_katedra
	# Grouped by katedra, each group folds; its heading counts its rows.
	page.goto(base + '/nastavnici/')
	page.select_option('#t-g', 'k')
	first = page.locator('details.sg').first
	print('groups:', page.locator('details.sg').count(), '| first:', first.locator('summary').inner_text().replace('\n', ' '))
	n = int(first.locator('.sg__n').inner_text())
	assert first.get_attribute('open') is not None and first.locator('.pc:visible').count() == n
	first.locator('summary').click()
	assert first.get_attribute('open') is None and first.locator('.pc:visible').count() == 0
	page.select_option('#t-g', '')
	page.goto(base + '/nastavnik/dusan-lj-djukic/')
	print('profile h1:', page.inner_text('h1'), '| archived subjects:', page.locator('.tp__subj a[href^="/predmet/"]').count(),
		'| posts:', page.locator('.tp__posts li').count())
	page.screenshot(path='test/nastavnik.png')
	page.click('#pismo')
	print('cyrillic h1:', page.inner_text('h1'), '| button:', page.get_attribute('#pismo', 'data-pismo'))
	page.click('#pismo')
	# On a teacher's page the header search lists teachers; arrow down and Enter opens the first.
	assert page.input_value('#qk') == 'nastavnici'
	page.fill('#q', 'mladenov')
	names = page.locator('.cmd__list a').all_inner_texts()
	print('teachers for "mladenov":', names)
	assert names
	page.press('#q', 'ArrowDown')
	page.keyboard.press('Enter')
	page.wait_for_url(lambda url: '/nastavnik/' in url and 'dusan-lj-djukic' not in url)
	assert page.inner_text('h1') == names[0], page.inner_text('h1')
	page.goto(base + '/nastavnik/dusan-lj-djukic/')
	page.goto(base + page.locator('.tp__subj a').first.get_attribute('href'))
	print('subject page teachers:', page.locator('.mh__sub a[href^="/nastavnik/"]').all_inner_texts())
	# The topic filter of a subject page, by author.
	before = shown()
	page.select_option('#f-a', index=1)
	print('subject topics:', before, '-> by', page.locator('#f-a option:checked').inner_text(), shown(), '| url:', page.url.split('?')[1])
	assert 0 < shown() <= before
	page.select_option('#f-a', index=0)
	# The header search filters the topics; Enter searches the text of this subject's posts.
	page.fill('#q', 'kolokvijum')
	print('topics with "kolokvijum":', shown())
	assert shown() < before
	page.press('#q', 'Enter')
	page.wait_for_url(re.compile(r'subject=.*q=kolokvijum|q=kolokvijum.*subject='))
	page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('rezultat')")
	print('Enter ->', page.url.split('?')[1], '|', page.inner_text('#res-h'))
	# Another scope leaves the page's: the list shows all again and Enter searches all the posts.
	page.go_back()
	page.wait_for_selector('#qk:visible')
	page.fill('#q', 'kolokvijum')
	page.select_option('#qk', '')
	assert shown() == before
	page.press('#q', 'Enter')
	page.wait_for_url(re.compile(r'/\?q=kolokvijum'))
	assert 'subject' not in page.url, page.url
	# A smer's page: the header search filters its subjects.
	page.goto(base + '/smer/oas-mi/')
	all_subjects = shown()
	page.fill('#q', 'mehanika')
	print('smer subjects:', all_subjects, '-> "mehanika":', page.locator('[data-rows] > li:visible .fr__a').all_inner_texts())
	assert 0 < shown() < all_subjects
	# The home page: a new visitor starts in the subjects. Sve lists the subjects by studije, the teachers and the
	# schedule under the bar.
	page.goto(base + '/')
	assert page.input_value('#qk') == 'predmeti'
	page.select_option('#qk', '')
	page.fill('#q', 'num')
	page.wait_for_selector('#q-list a')
	print('sve "num":', page.locator('.cmd__h').all_inner_texts(), '| studije:', page.locator('.cmd__s').all_inner_texts()[:3])
	# The home page lists the posts and news itself: none under the bar.
	assert not page.locator('.cmd__all').count()
	page.fill('#q', 'ispit')
	assert page.locator('.cmd__g[aria-label="Raspored"] a').count(), 'no exam entries'
	# Predmeti: every match, by studije; the choice is kept for the home page only.
	page.fill('#q', 'num')
	page.select_option('#qk', 'predmeti')
	n = page.locator('.cmd__list a').count()
	print('predmeti "num":', n, 'in', page.locator('.cmd__s').all_inner_texts())
	assert n > 5 and not page.locator('.cmd__h').count() and not page.locator('.cmd__all').count()
	page.goto(base + '/nastavnik/dusan-lj-djukic/')
	assert page.input_value('#qk') == 'nastavnici'
	page.goto(base + '/')
	assert page.input_value('#qk') == 'predmeti'
	# Vesti: the year's list filters by category; the scope searches only the news, Sve the news and the posts.
	page.goto(base + '/vesti/')
	assert page.input_value('#qk') == 'vest'
	in_year = shown()
	page.select_option('#v-k', 'izdvajamo')
	print('vesti:', in_year, '-> izdvajamo:', shown())
	assert 0 < shown() < in_year and 'kategorija=izdvajamo' in page.url
	page.goto(base + '/vest/32035/')
	assert page.locator('.snav a[aria-current]').inner_text() == 'Vesti'
	# Off the home page, the posts' and news' best hits show under the bar while typing.
	for kind in ['', 'vest', 'obavestenje']:
		page.select_option('#qk', kind)
		page.fill('#q', 'stipendija')
		page.wait_for_function("document.querySelector('.cmd__all')?.textContent.startsWith('Svi rezultati')")
		hits = page.locator('.cmd__g:has(+ .cmd__all) a').count()
		print(f'under the bar, {kind or "sve"}:', hits, '|', page.inner_text('.cmd__all'))
		assert 0 < hits <= 5
	counts = {}
	for kind in ['vest', 'obavestenje', '']:
		page.goto(f'{base}/?q=stipendija&kind={kind}')
		page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('rezultat')")
		counts[kind] = int(page.inner_text('#res-h b'))
		assert page.input_value('#qk') == kind
	print('"stipendija":', counts)
	assert counts['vest'] + counts['obavestenje'] == counts[''] and counts['vest'] > 0
	assert not errors
	print('page errors:', errors or 'none')
