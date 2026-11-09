# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the teacher pages of www.mas.bg.ac.rs: the list, every profile and the emeritus page.

Usage: nastavnici.py sync
       nastavnici.py history   (once: teachers who left before, from the Wayback Machine)

One row per teacher (the newest version of the profile) and one row per subject the teacher has.
A teacher who leaves the list stays, marked gone. The forum username is the part of the e-mail before @.
"""
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

SITE = 'https://www.mas.bg.ac.rs/'
LIST = 'fakultet/nastavnici/start'
EMERITUS = 'fakultet/nastavnici/emeritus/start'

SCHEMA = '''
create table if not exists teachers (id text primary key, name text, full_name text, title text, katedra text, katedra_id integer,
	office text, email text, username text, phone text, hours text, research text, emeritus integer, html text,
	first_seen text, last_seen text, gone integer default 0, photo text);
create table if not exists teacher_subjects (teacher text, code text, name text, primary key (teacher, code));
'''


def split_title(text):
	"""'др Душан Љ. Ђукић, ванредни професор' -> ('др Душан Љ. Ђукић', 'ванредни професор')."""
	full, _, title = ' '.join(text.split()).partition(', ')
	return full.strip(), title


def plain_name(full):
	"""'мастер маш. инж. Јована Р. Антић' -> 'Јована Р. Антић': the degree is in lower case, the name is not."""
	words = full.split()
	return ' '.join(words[next((i for i, w in enumerate(words) if w[0].isupper()), 0):])


def field(text, label):
	# The value is on the line of the colon; an empty one must not take the next line's label.
	m = re.search(rf'{label}\s*:[ \t]*(.*)', text)
	return (m and m.group(1).strip()) or None


def sections(main):
	"""{h3 heading: text under it} of a profile."""
	out = {}
	for h in main.select('h3'):
		parts = []
		for sib in h.find_next_siblings():
			if sib.name in ('h2', 'h3'):
				break
			parts.append(sib.get_text('\n'))
		out[h.get_text(strip=True)] = '\n'.join(' '.join(l.split()) for l in '\n'.join(parts).split('\n') if l.strip())
	return out


def parse_list(html):
	"""The rows of the teacher list: id, full name, title, katedra, phone, email."""
	from bs4 import BeautifulSoup
	rows = []
	for p in BeautifulSoup(html, 'html.parser').select('div.page p'):
		# Not .media: the 2014 list links the photo first, a link without the name.
		a = p.select_one('a[href^="/fakultet/nastavnici/"]:not(.media)')
		m = a and re.fullmatch(r'/fakultet/nastavnici/(\d+)', a['href'])
		if not m:
			continue
		lines = [l.strip() for l in p.get_text('\n').split('\n') if l.strip()]
		mail = p.select_one('a[href^="mailto:"]')
		full, title = split_title(a.get_text())
		rows.append(dict(id=m.group(1), full_name=full, title=title,
			katedra=next((l[0].upper() + l[1:] for l in lines if l.lower().startswith('катедра')), None),
			phone=field(p.get_text('\n'), 'Телефон'), email=mail and mail.get_text(strip=True)))
	return rows


def parse_profile(html):
	from bs4 import BeautifulSoup
	main = BeautifulSoup(html, 'html.parser').select_one('div.page')
	if main is None:
		raise RuntimeError('profile: no div.page, the site changed')
	head = main.select_one('div.wrap_box p')
	text = head.get_text('\n') if head else ''
	kat = head and head.select_one('a[href^="/organizacija/katedre/"]')
	sec = sections(main)
	subjects = {}
	for a in main.select('a[href^="/studije/predmeti/"]'):
		code = a['href'].rsplit('/', 1)[-1]
		subjects.setdefault(code, ' '.join(a.get_text().split()))
	return dict(name=main.select_one('h2').get_text(strip=True),
		katedra=kat and ' '.join(kat.get_text().split()), katedra_id=kat and int(kat['href'].rsplit('/', 1)[-1]),
		office=field(text, 'Кабинет'), hours=sec.get('Термини за пријем студената'),
		research=sec.get('Истраживачка област'), html=str(main)), subjects


def parse_emeritus(html):
	from bs4 import BeautifulSoup
	rows = []
	for box in BeautifulSoup(html, 'html.parser').select('div.page div.wrap_box'):
		mail = box.select_one('a[href^="mailto:"]')
		if not mail:
			continue
		email = mail.get_text(strip=True)
		line = next(l for l in box.get_text('\n').split('\n') if ',' in l)
		full, title = split_title(line)
		rows.append(dict(id=f'emeritus-{email.split("@")[0]}', full_name=full, title=title, email=email,
			name=plain_name(full), emeritus=1, html=f'<div class="page">{box}</div>'))
	return rows


def save(db, row, now):
	row = dict(row, username=row.get('email') and row['email'].split('@')[0].lower(), first_seen=now, last_seen=now, gone=0)
	cols = list(row)
	db.execute(f'insert into teachers ({", ".join(cols)}) values ({", ".join("?" * len(cols))}) on conflict(id) do update set '
		+ ', '.join(f'{c} = excluded.{c}' for c in cols if c != 'first_seen'), list(row.values()))


def sync(db):
	from nastava import DELAY, session
	now = datetime.now(timezone.utc).isoformat(timespec='seconds')

	def page(path):
		"""The page's HTML, or None for a 404."""
		time.sleep(DELAY)
		r = session().get(SITE + path, timeout=60)
		if r.status_code == 404:
			return None
		r.raise_for_status()
		return r.text

	listed = parse_list(page(LIST) or '')
	if len(listed) < 50:
		raise RuntimeError(f'only {len(listed)} teachers in the list, the site changed')
	for i, row in enumerate(listed, 1):
		html = page(f'fakultet/nastavnici/{row["id"]}')
		if html is None:
			# Listed before its profile exists: keep the list's data, try the profile again tomorrow.
			print(f'no profile for {row["id"]} {row["full_name"]}', flush=True)
			save(db, dict(row, name=plain_name(row['full_name']), emeritus=0), now)
			continue
		profile, subjects = parse_profile(html)
		save(db, dict(row, **{k: v for k, v in profile.items() if v or k not in row}, emeritus=0), now)
		db.execute('delete from teacher_subjects where teacher = ?', (row['id'],))
		db.executemany('insert into teacher_subjects values (?,?,?)', [(row['id'], c, n) for c, n in subjects.items()])
		if i % 25 == 0:
			db.commit()
			print(f'{i}/{len(listed)}', flush=True)
	emeriti = parse_emeritus(page(EMERITUS))
	for row in emeriti:
		save(db, row, now)
	gone = db.execute('update teachers set gone = 1 where last_seen != ?', (now,)).rowcount
	db.commit()
	n = db.execute('select count(*) from teacher_subjects').fetchone()[0]
	print(f'{len(listed)} teachers, {len(emeriti)} emeriti, {n} teacher subjects, {gone} gone', flush=True)


WAYBACK = 'https://web.archive.org/'
MASINAC = 'https://www.masinac.org/'
LATIN = 'a b v g d đ e ž z i j k l lj m n nj o p r s t ć u f h c č dž š'.split()
CYRILLIC = 'абвгдђежзијклљмнњопрстћуфхцчџш'


def to_cyr(s):
	"""'Miloš Glavonjić' -> 'Милош Главоњић' (masinac.org writes in Latin, the faculty in Cyrillic)."""
	def one(m):
		c = CYRILLIC[LATIN.index(m[0].lower())]
		return c.upper() if m[0][0].isupper() else c
	return re.sub('dž|lj|nj|[a-zčćšžđ]', one, s, flags=re.I)


def name_key(name):
	"""A name to match across scripts and spellings: Latin, no diacritics, no middle initial, lower case.
	'Весна К. Спасојевић-Бркић' and 'Vesna Spasojevic Brkic' -> 'vesna spasojevic brkic'."""
	lat = ''.join(LATIN[CYRILLIC.index(c)] if c in CYRILLIC else c for c in name.lower())
	lat = lat.translate(str.maketrans('čćšžđ-', 'ccszd '))
	return ' '.join(w for w in lat.replace('.', '. ').split() if not w.endswith('.'))


def person_keys(row):
	"""What identifies a person across ids and sites: the name, the e-mail before @."""
	user = (row.get('email') or '').split('@')[0].lower()
	return {name_key(plain_name(row['full_name']))} | ({user} if user else set())


def parse_masinac(html):
	"""A lecturer page of masinac.org (a student portal that copied the faculty's teacher data, 2008 on): its fields,
	the photo's URL and the table without the photo."""
	from bs4 import BeautifulSoup
	table = BeautifulSoup(html, 'html.parser').select_one('table#zaposleni')
	if table is None:
		return None
	row = {tr.select_one('td.left').get_text(strip=True): ' '.join(tr.select_one('td.right').get_text(' ', strip=True).split())
		for tr in table.select('tr') if tr.select_one('td.left')}
	img = table.select_one('td.slika img')
	photo = img and urljoin(MASINAC, img['src'])
	if img:
		img.find_parent('td').decompose()
	return dict(row, photo=photo, html=f'<div class="page">{table}</div>')


def wb_time(ts):
	"""'20140629012301' -> '2014-06-29T01:23:01+00:00', the form of first_seen and last_seen."""
	return f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}T{ts[8:10]}:{ts[10:12]}:{ts[12:14]}+00:00'


def history(db):
	"""Teachers who left before the archive began, from the Wayback Machine's copies of the list (2014 on) and from
	masinac.org (2008 on). Each one not listed today is stored gone, with their last archived profile and a photo that
	still loads; listed teachers are not touched."""
	from collections import Counter, defaultdict
	from nastava import DELAY, session

	def get(url, tries=4):
		"""The page's text; None after the tries (raises for the Wayback Machine, where every page asked for exists)."""
		for attempt in range(tries):
			time.sleep(1.5 * 2 ** attempt)
			try:
				# masinac.org sends a missing page to its home page: not followed.
				r = session().get(url, timeout=90, allow_redirects=url.startswith(WAYBACK))
			except Exception as e:
				print(f'retry {url}: {e}', flush=True)
				continue
			if r.status_code == 200 and r.text:
				return r.text
			print(f'retry {url}: {r.status_code}', flush=True)
		if url.startswith(WAYBACK):
			raise RuntimeError(f'wayback: no answer for {url}')

	def captures(url, prefix=False):
		"""[(timestamp, original url)] of each distinct 200 capture."""
		q = f'{WAYBACK}cdx/search/cdx?url={url}&filter=statuscode:200&fl=timestamp,original'
		q += '&matchType=prefix' if prefix else '&collapse=digest'
		return sorted(tuple(l.split(' ')) for l in get(q).splitlines() if l)

	def page(ts, url):
		return get(f'{WAYBACK}web/{ts}id_/{url}')

	live = {r[0] for r in db.execute('select id from teachers where not gone')}
	seen = {}  # id -> [first ts, last ts, row of the last list]
	for path, parse in ((LIST, parse_list), (EMERITUS, parse_emeritus)):
		for ts, url in captures('www.mas.bg.ac.rs/' + path):
			rows = parse(page(ts, url))
			print(f'{path} {ts}: {len(rows)}', flush=True)
			for row in rows:
				seen.setdefault(row['id'], [ts, ts, row])[1:] = [ts, row]
	profiles = {}
	for ts, url in captures('www.mas.bg.ac.rs/fakultet/nastavnici/', prefix=True):
		m = re.search(r'/fakultet/nastavnici/(\d+)$', url.split('?')[0])
		if m:
			profiles[m[1]] = (ts, url)
	# One person under several ids (the faculty renumbered its pages in 2015; a teacher who became emeritus), matched
	# by name or e-mail: the newest id is kept, with the earliest first day. None if they are listed today.
	taken = {k for n, u in db.execute('select name, username from teachers where not gone') for k in (name_key(n), u) if k}
	people = []  # [keys, ids newest first]
	for i in sorted(seen, key=lambda i: seen[i][1], reverse=True):
		keys = person_keys(seen[i][2])
		p = next((p for p in people if p[0] & keys), None)
		if p:
			p[0] |= keys
			p[1].append(i)
		else:
			people.append([keys, [i]])
	left = {ids[0]: [min(seen[i][0] for i in ids), *seen[ids[0]][1:]] for keys, ids in people
		if not keys & taken and not live.intersection(ids)}
	print(f'{len(seen)} ids in the archived lists, {len(people)} people, {len(left)} not listed today', flush=True)
	for n, (i, (first, last, row)) in enumerate(left.items(), 1):
		subjects = {}
		if i in profiles:
			try:
				profile, subjects = parse_profile(page(*profiles[i]))
				# The faculty reuses a page's number: a profile of someone else (153: Покрајац, later Бојовић) is not theirs.
				if name_key(profile['name']) == name_key(plain_name(row['full_name'])):
					row = dict(row, **{k: v for k, v in profile.items() if v or k not in row})
				else:
					print(f'{i} {row["full_name"]}: the profile is {profile["name"]}, not used', flush=True)
					subjects = {}
			except RuntimeError as e:
				print(f'{i} {row["full_name"]}: {e}', flush=True)
		if row.get('katedra'):
			row['katedra'] = row['katedra'][0].upper() + row['katedra'][1:]
		save(db, dict(row, name=row.get('name') or plain_name(row['full_name']), emeritus=int(i.startswith('emeritus-'))),
			wb_time(last))
		db.execute('update teachers set first_seen = ?, gone = 1 where id = ?', (wb_time(first), i))
		db.execute('delete from teacher_subjects where teacher = ?', (i,))
		db.executemany('insert into teacher_subjects values (?,?,?)', [(i, c, s) for c, s in subjects.items()])
		db.commit()
		print(f'{n}/{len(left)} {row["full_name"]} {first[:4]}-{last[:4]}', flush=True)

	# masinac.org: its lecturers in no list here are added, gone; its photos fill the ones the faculty lost.
	pages = {}  # path -> [first ts, last ts, last url]
	for ts, url in captures('masinac.org/fakultet/katedre/', prefix=True):
		m = re.search(r'/fakultet/(katedre/([a-z]+)/predavaci/[a-z0-9-]+)$', url.split('?')[0])
		if m:
			pages.setdefault(m[1], [ts, ts, url])[1:] = [ts, url]
	known = {}  # name key or username -> (id, katedra)
	for i, name, user, kat in db.execute('select id, name, username, katedra from teachers'):
		known.update({k: (i, kat) for k in (name_key(name), user) if k})
	lecturers = []
	for path, (first, last, url) in pages.items():
		html = get(MASINAC + 'fakultet/' + path, tries=1)
		try:
			html = html or page(last, url)
		except RuntimeError as e:
			print(e, flush=True)
		row = parse_masinac(html or '')
		if row is None:
			print(f'masinac.org {path}: no data table', flush=True)
			continue
		name, _, degree = row.get('Ime i prezime', '').partition(',')
		# 'Dragan Lj.Milanović' -> 'Драган Љ. Милановић'
		row.update(path=path, first=first, name=to_cyr(re.sub(r'\.(?=\S)', '. ', name.strip())), dr='dr' in degree)
		stem = row['photo'] and row['photo'].rsplit('/', 1)[1].split('.')[0].lower()
		# By e-mail or photo name; by name only without a middle initial ('Dragan Lj. Milanović' is not 'Драган Д.').
		row['keys'] = [k for k in ((row.get('Email') or '').split('@')[0].lower(), stem) if k]
		row['keys'] += [name_key(row['name'])] if '.' not in row['name'] else []
		row['match'] = next((known[k] for k in row['keys'] if k in known), None)
		lecturers.append(row)
	katedra = defaultdict(Counter)  # masinac.org katedra -> the faculty's names of it, from the teachers in both
	for row in lecturers:
		if row['match'] and row['match'][1]:
			katedra[row['path'].split('/')[1]][row['match'][1]] += 1
	new = [row for row in lecturers if not row['match']]
	for row in new:
		k, slug = row['path'].split('/')[1], row['path'].rsplit('/', 1)[1]
		title = row.get('Zvanje') or row.get('Naučno zvanje')
		i = f'masinac-{k}-{slug}'
		save(db, dict(id=i, full_name=('др ' if row['dr'] else '') + row['name'], name=row['name'],
			title=title and to_cyr(title.lower()), katedra=katedra[k] and katedra[k].most_common(1)[0][0],
			email=row.get('Email'), phone=row.get('Broj telefona'), html=row['html'], emeritus=0), wb_time(row['first']))
		db.execute('update teachers set gone = 1 where id = ?', (i,))
	db.commit()
	print(f'masinac.org: {len(lecturers)} lecturers, {len(new)} added: {", ".join(r["name"] for r in new)}', flush=True)

	# A departed teacher's photo: the faculty's while it still has it (stored none), else the Wayback Machine's copy,
	# else masinac.org's (live, then archived).
	# shortcut: checked when history runs; a teacher who leaves later keeps the faculty's link until it runs again.
	def image(url):
		time.sleep(DELAY)
		try:
			r = session().head(url, timeout=60)
		except Exception:
			return False
		return r.status_code == 200 and r.headers.get('content-type', '').startswith('image')

	archived = {}  # the faculty's photo name or masinac.org's photo path -> its Wayback copy
	for ts, url in captures('www.mas.bg.ac.rs/_media/fakultet/nastavnici/', prefix=True):
		archived[url.split('?')[0].rsplit('/', 1)[1].lower()] = f'{WAYBACK}web/{ts}im_/{url}'
	for ts, url in captures('masinac.org/images/predavaci/', prefix=True):
		archived[url.split('?')[0].split('masinac.org/', 1)[1].lower()] = f'{WAYBACK}web/{ts}im_/{url}'
	theirs = {k: row['photo'] for row in lecturers if row['photo'] for k in row['keys']}
	found = Counter()
	for i, name, user, html in db.execute('select id, name, username, html from teachers where gone').fetchall():
		m = re.search(r'_media/fakultet/nastavnici/([^"?]+)', html or '')
		if m and image(SITE + '_media/fakultet/nastavnici/' + m[1]):
			photo, how = None, 'faculty'
		elif m and m[1].lower() in archived:
			photo, how = archived[m[1].lower()], 'wayback'
		else:
			photo = next((theirs[k] for k in (user, name_key(name)) if k in theirs), None)
			if photo and not image(photo):
				photo = archived.get(photo.split('masinac.org/', 1)[1].lower())
			how = 'masinac.org' if photo else 'none'
		db.execute('update teachers set photo = ? where id = ?', (photo, i))
		found[how] += 1
	db.commit()
	print(f'photos of the departed: {dict(found)}', flush=True)


def main():
	from nastava import connect
	sys.stdout.reconfigure(encoding='utf-8')
	cmd = sys.argv[1] if len(sys.argv) > 1 else 'sync'
	if cmd not in ('sync', 'history'):
		sys.exit(__doc__)
	db = connect()
	db.executescript(SCHEMA)
	# photo: added after the table (history); null but for a departed teacher whose photo the faculty lost.
	if 'photo' not in {c[1] for c in db.execute('pragma table_info(teachers)')}:
		db.execute('alter table teachers add column photo text')
	(sync if cmd == 'sync' else history)(db)


if __name__ == '__main__':
	assert split_title(' др Душан Љ. Ђукић,  ванредни професор ') == ('др Душан Љ. Ђукић', 'ванредни професор')
	assert split_title('др Зоран В. Стаменић , доцент')[0] == 'др Зоран В. Стаменић'
	assert wb_time('20140629012301') == '2014-06-29T01:23:01+00:00'
	assert to_cyr('Miloš Lj. Glavonjić, Džajić') == 'Милош Љ. Главоњић, Џајић'
	assert name_key('Весна К. Спасојевић-Бркић') == name_key('Vesna Spasojević Brkić') == 'vesna spasojevic brkic'
	assert name_key('Dragan Lj.Milanović') == 'dragan milanovic'
	assert person_keys(dict(full_name='др Зоран В. Стаменић', email='ZStamenic@mas.bg.ac.rs')) == {'zoran stamenic', 'zstamenic'}
	assert field('Кабинет : 440\nТелефон: -', 'Кабинет') == '440'
	assert field('Кабинет\n:\nМејл адреса\n: x@y', 'Кабинет') is None
	assert plain_name('мастер маш. инж. Јована Р. Антић') == 'Јована Р. Антић' and plain_name('др Мирољуб Аџић') == 'Мирољуб Аџић'
	main()
