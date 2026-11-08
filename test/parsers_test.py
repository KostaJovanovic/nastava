"""The scrapers' parsers on saved pages (test/fixtures), no network:
uv run --with beautifulsoup4 --with requests python test/parsers_test.py
A change on the board or on www.mas.bg.ac.rs: save the new page over the fixture and fix the parser until this passes."""
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import nastava  # noqa: E402
import nastavnici  # noqa: E402

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
print('parsers ok')
