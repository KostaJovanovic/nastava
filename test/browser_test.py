"""Real searches and screenshots in Edge: python browser_test.py <base url> <out dir>."""
import re
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
		first = page.locator('#res .fr__a').first
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
	# A smer filter from the URL: the smer's Latin slug (a URL never has Cyrillic).
	page.goto(f'{base}/?smer=katedre')
	page.wait_for_function(done)
	page.wait_for_load_state('networkidle')
	print('smer filter:', page.inner_text('#res-h'), '| first:', page.locator('#res .fr__s .s1').first.inner_text())
	assert page.locator('.chip').first.inner_text() == 'katedre'
	# A Cyrillic query: the URL has it folded to Latin.
	page.fill('#q', 'распоред')
	page.wait_for_function("location.search.includes('q=raspored')")
	assert not re.search(r'[Ѐ-ӿ]|%D[01]', page.url, re.I), page.url
	# An author filter from the URL, as a teacher page links it.
	page.goto(f'{base}/?autor=ddjukic')
	page.wait_for_function(done)
	page.wait_for_load_state('networkidle')
	chip = page.locator('.chip').first.inner_text()
	print('autor filter:', page.inner_text('#res-h'), '| first author:', page.locator('#res .fr__s .s2').first.inner_text(), '| chip:', chip)
	assert 'Đukić' in chip, chip  # the teacher's name, not the username
	page.click('.chip')  # removing the chip clears the filter: the board index again
	page.wait_for_function("document.querySelector('#res-h')?.textContent.includes('Arhiva')")
	assert 'autor' not in page.url, page.url
	# The subject picker: open it, follow the first subject of the first program's year; a search then covers only
	# that subject, until "all subjects" is picked.
	page.click('[data-moji-open]')
	# Nothing is picked at first and every subject shows; a pick narrows them, and on a phone hides the rest of its row.
	assert page.locator('.mp__tab[aria-pressed="true"]').count() == 0
	n_all = page.locator('.mp__card').count()
	page.locator('.mp__tabs .mp__tab').first.click()
	page.locator('.mp__chips .mp__tab').first.click()
	assert page.locator('.mp__tabs .mp__tab:visible').count() > 1
	assert 0 < page.locator('.mp__card').count() < n_all, n_all
	page.set_viewport_size({'width': 400, 'height': 800})
	assert page.locator('.mp__tabs .mp__tab:visible').count() == 1 and page.locator('.mp__chips .mp__tab:visible').count() == 1
	page.set_viewport_size({'width': 1366, 'height': 900})
	card = page.locator('.mp__card').first
	name = card.inner_text()
	card.click()
	assert card.get_attribute('aria-pressed') == 'true' and page.inner_text('.mp__tabs .mp__tab .mp__badge') == '1'
	assert page.evaluate("JSON.parse(localStorage.moji).length") == 1
	# A year chip switches the cards; the search box finds a teacher, whose card follows their subjects.
	page.locator('.mp__chips .mp__tab').nth(1).click()
	print('picker, 2nd year:', page.locator('.mp__group h3').all_inner_texts())
	page.fill('[data-mp-q]', 'mladenovic')
	print('picker search:', page.locator('.mp__card .mp__name').all_inner_texts()[:4])
	page.fill('[data-mp-q]', '')
	page.click('.mp__foot [data-mp-close]')
	assert page.locator('[data-moji-list] .chip').count() == 1
	page.goto(f'{base}/?from=2014')  # the year field's min: an invalid form is not submitted
	page.wait_for_function(done)
	page.wait_for_load_state('networkidle')
	seen = set(page.locator('#res .fr__s .s1').all_inner_texts())
	print('picker:', name, '->', page.inner_text('#res-h'), '| subjects:', seen)
	assert seen == {name} and 'Moji predmeti (1)' in page.inner_text('.chips'), (seen, page.inner_text('.chips'))
	page.locator('label', has_text='Pretraga u svim predmetima').click()
	page.wait_for_function("location.search.includes('sve=1') && !document.querySelector('.chips')?.textContent.includes('Moji')")
	page.wait_for_load_state('networkidle')
	assert len(set(page.locator('#res .fr__s .s1').all_inner_texts())) > 1
	page.evaluate("localStorage.removeItem('moji')")
	# A link off the site asks first; a PDF of this site opens in a new tab.
	page.goto(f'{base}/item/p100/')
	page.locator('main a[href^="https://nastava.mas.bg.ac.rs"]').first.click()
	print('leaving:', page.inner_text('.leave .leave__url'))
	assert page.locator('.leave[open]').count() == 1
	page.click('[data-leave-stay]')
	assert page.locator('.leave[open]').count() == 0 and '/item/p100/' in page.url
	page.goto(f'{base}/raspored/')
	with page.context.expect_page() as tab:
		page.locator('.rs-card').first.click()
	print('pdf in a new tab:', tab.value.url.split('/')[-1], '| this page:', page.url.split('/', 3)[-1])
	assert tab.value.url.endswith('.pdf') and '/raspored/' in page.url
	tab.value.close()
	print('page errors:', errors or 'none')
	browser.close()
