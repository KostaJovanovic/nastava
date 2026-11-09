# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The scrapers' parsers on saved pages (test/fixtures), no network: uv run test/parsers_test.py
A change on the board or on www.mas.bg.ac.rs: save the new page over the fixture and fix the parser until this passes."""
import sqlite3
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import nastava  # noqa: E402
import cent  # noqa: E402
import nastavnici  # noqa: E402
import predmeti  # noqa: E402
import studije  # noqa: E402

FIX = ROOT / 'test' / 'fixtures'
read = lambda name: (FIX / name).read_text(encoding='utf-8')
soup = lambda name: BeautifulSoup(read(name), 'html.parser')

# A forum page: its subforums with counts and last post, its topics, the next page.
rows = list(nastava.read_rows(soup('viewforum.html')))
forums = [r for r in rows if r[0] == 'forum']
assert len(forums) == 21 and len(rows) - len(forums) == 25, (len(forums), len(rows))
assert ('forum', 1272, 'Алгебра и линеарна алгебра (7002)', 253, 288, 29335) in forums
assert nastava.next_page(soup('viewforum.html')) == 'viewforum.php?f=1062&start=25'

# A topic page: its forum from the breadcrumb, each post with author, dates, text and attachment.
nastava.get = lambda path: soup('viewtopic.html')
forum, name, posts = nastava.read_topic(21088)
assert (forum, name, len(posts)) == (51, 'Математика 1 (0669)', 2)
first = posts[0]
assert (first['id'], first['author'], first['date'], first['posted']) == (29307, 'apejcev', '30.10.2026. 20:26', '2026-10-30T19:26:27+00:00')
assert first['title'].startswith('Analiticka geometrija') and first['content'] and 'attachbox' in first['html']
assert first['files'] == [(23874, 'Pravairavan.pdf')] and posts[1]['files'] == []
# A topic page where no post parses (the board changed its markup) is an error, not a topic with no posts.
empty = soup('viewtopic.html')
for p in empty.select('div.post'):
	p.decompose()
nastava.get = lambda path: empty
try:
	nastava.read_topic(21088)
	raise AssertionError('no error for a topic page without posts')
except ValueError:
	pass

# Nothing is deleted: a post that leaves the board stays, marked gone; a topic that 404s is marked gone.
db = sqlite3.connect(':memory:')
db.executescript(nastava.SCHEMA)
db.execute('insert into topics (id, forum, last_post) values (1, 5, 11)')
post = lambda i: dict(id=i, title='t', author='a', date='', posted='', content='c', html='h', files=[], images=set())
assert nastava.store_topic(db, 1, 11, (5, 'F', [post(10), post(11)])) == 2
nastava.store_topic(db, 1, 11, (5, 'F', [post(11)]))
assert db.execute('select id, gone from posts order by id').fetchall() == [(10, 1), (11, 0)]
nastava.store_topic(db, 1, 11, (5, 'F', [post(10), post(11)]))
assert db.execute('select sum(gone) from posts').fetchone() == (0,)
nastava.store_topic(db, 1, 11, None)
assert db.execute('select gone from topics').fetchone() == (1,) and db.execute('select count(*), sum(gone) from posts').fetchone() == (2, 2)

# The teacher list, a profile and the emeritus page.
listed = nastavnici.parse_list(read('nastavnici.html'))
assert len(listed) == 201 and all(t['katedra'] for t in listed) and sum(not t['email'] for t in listed) == 4
assert listed[0] == dict(id='1', full_name='др Драган С. Алексендрић', title='редовни професор', katedra='Катедра за моторна возила',
                         phone='локал 390; директан 3370-346', email='daleksendric@mas.bg.ac.rs')
profile, subjects = nastavnici.parse_profile(read('nastavnik.html'))
assert (profile['name'], profile['katedra_id'], profile['office'], profile['research']) == ('Душан Љ. Ђукић', 12, '440', 'нумеричка анализа')
assert len(subjects) == 8 and subjects['1623'] == 'Математика 1'
emeriti = nastavnici.parse_emeritus(read('emeritus.html'))
assert len(emeriti) == 6 and emeriti[0]['id'] == 'emeritus-madzic' and emeriti[0]['name'] == 'Мирољуб Аџић'
# The name of a listed teacher whose profile is missing: the same as the profile's.
assert nastavnici.plain_name(next(t['full_name'] for t in listed if t['id'] == '52')) == profile['name']
assert nastavnici.plain_name('мастер маш. инж. Јована Р. Антић') == 'Јована Р. Антић'

# The subject book, the plans (a grid of rowspans; an elective slot is a link to its list) and a subject page.
book = predmeti.parse_book(read('predmeti.html'))
assert len(book) == 784 and book['1623'] == ('Математика 1', 'Основне академске студије — МИ')
electives = predmeti.parse_electives(read('oas-izborni.html'))
assert len(electives['section54']) == 19
rows = predmeti.places(predmeti.parse_plan(read('oas.html'), 0), lambda href: electives.get(href.split('#')[1], []))
assert (1, 1, None, None, '1623') in rows and (1, 3, None, None, '0203') in rows and (1, 3, None, None, '1415') in rows
assert len([r for r in rows if r[2] == '5.4']) == 19
# The final subject's cell has no link; its list is linked elsewhere on the page. The list links the one final
# subject once per teacher: it is one place.
assert [r[4] for r in rows if r[2] == '6.5'] == ['0361']
assert [s for s, p, td in predmeti.parse_plan(read('oas.html'), 1)].count(1) == 6
modules = predmeti.parse_modules(read('mas.html'))
assert len(modules) == 21 and modules[0] == ('Аутоматско управљање', 'studije/mas/modul-18')
modul = read('modul.html')
rows = predmeti.places(predmeti.parse_plan(modul), lambda href: predmeti.parse_electives(modul).get(href.split('#')[1], []))
assert (1, 1, None, None, '1554') in rows and len([r for r in rows if r[2] == '1.5']) == 4
subject = predmeti.parse_subject(read('predmet.html'))
assert {k: subject[k] for k in ('name', 'ects', 'katedra', 'holder')} == dict(name='Математика 1', ects=6, katedra='Катедра за математику', holder='494')
assert '<p>' in subject['html'], 'the page text keeps its paragraphs'

# A schedule file's link and its path under the built site: no way out of it, no type that runs script there.
assert studije.media_path('/_media/studije/i_godina.pdf?cache=1') == 'studije/i_godina.pdf'
assert studije.media_path('/lib/exe/fetch.php?media=studije:itm1.pdf') == 'studije/itm1.pdf'
assert studije.media_path('https://example.com/_media/x.pdf') is None
assert not studije.safe(studije.media_path('/lib/exe/fetch.php?media=:x.pdf'))
assert not studije.safe('a/../../x.pdf') and not studije.safe('x.svg') and studije.safe('studije/i_godina.pdf')

# cent.mas.bg.ac.rs (cent.py): a subject's notices page (a notice; Divi's script links made <a>), a results page (file
# icons named by the file), a labs page (video links), and a subject's own page (only the header: no content).
T = 'https://cent.mas.bg.ac.rs/tehnologija-masinske-obrade/'
code, html, notices = cent.parse(read('cent-obavestenja.html'), T + 'obavestenja/')
assert code == '1617' and len(notices) == 1, (code, notices)
assert (notices[0]['title'], notices[0]['date']) == ('ВАЖНО ОБАВЕШТЕЊЕ – друга лабораторијска вежба!', '2026-11-06')
assert [f.rsplit('/', 1)[1] for f in notices[0]['files']] == ['Detaljan_raspored_lab2.pdf', 'Spisak_studenata_po_grupama_lab_2.pdf']
assert 'vesti_predmeta_title' not in notices[0]['html'] and 'Detaljan_raspored_lab2.pdf</a>' in notices[0]['html']
links = [(a['href'].rsplit('/', 1)[1], a.get_text(' ', strip=True)) for a in BeautifulSoup(html, 'html.parser').find_all('a')]
assert len(links) == 12 and ('Spisak_studenata_2026-2027_smjena1_v3.pdf', 'Смена 1') in links, links
assert 'vesti_predmeta_title' in html, 'the page keeps its notices as they were shown'
code, html, notices = cent.parse(read('cent-rezultati.html'), T + 'rezultati-tmo/')
assert code == '1617' and notices == [] and html.count('<a ') == 35 and '>fin11.pdf</a>' in html
assert 'href=""' not in html, 'an icon that links nowhere goes'
assert 'et_link_options_data' not in html and '<script' not in html
code, html, notices = cent.parse(read('cent-lab.html'), T + 'laboratorijske-vezbe-tmo/')
texts = [a.get_text(strip=True) for a in BeautifulSoup(html, 'html.parser').find_all('a')]
assert len(texts) == 15 and texts.count('video') == 3 and 'lab1.pdf' in texts and '' not in texts, texts
assert cent.parse(read('cent-predmet.html'), T) == ('1617', '', [])
# A notice no longer on its page stays, marked gone; a page's content that changes is a new version, and a page back
# to an older content makes that version the newest again.
db = sqlite3.connect(':memory:')
db.executescript(cent.SCHEMA)
notice = lambda t: dict(title=t, date='2026-11-06', html='x', files=[])
cent.store_notices(db, 1, [notice('a'), notice('b')], 's1')
cent.store_notices(db, 1, [notice('b')], 's2')
cent.store_notices(db, 2, [], 's2')
assert db.execute('select title, gone, first_seen, last_seen from cent_notices order by nid').fetchall() == [('a', 1, 's1', 's1'), ('b', 0, 's1', 's2')]
# An edited notice keeps its text before.
cent.store_notices(db, 1, [dict(notice('b'), html='y')], 's3')
assert db.execute('select html, last_seen from cent_notices where title = "b"').fetchone() == ('y', 's3')
assert db.execute('select nid, html, last_seen from cent_notice_old').fetchall() == [(2, 'x', 's2')]
page = dict(id=5, parent=0, menu_order=0, slug='x', title=dict(rendered='X &amp; Y'), link='L', modified='m')
assert [cent.store_page(db, page, '1617', h, w) for h, w in (('a', 's1'), ('a', 's2'), ('b', 's3'), ('a', 's4'))] == [True, False, True, True]
assert db.execute('select title, html, first_seen, last_seen from cent_pages order by last_seen desc').fetchall() == [
    ('X & Y', 'a', 's1', 's4'), ('X & Y', 'b', 's3', 's3')]
print('parsers ok')
