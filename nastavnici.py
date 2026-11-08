# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the teacher pages of www.mas.bg.ac.rs: the list, every profile and the emeritus page.

Usage: nastavnici.py sync

One row per teacher (the newest version of the profile) and one row per subject the teacher has.
A teacher who leaves the list stays, marked gone. The forum username is the part of the e-mail before @.
"""
import re
import sys
import time
from datetime import datetime, timezone

SITE = 'https://www.mas.bg.ac.rs/'
LIST = 'fakultet/nastavnici/start'
EMERITUS = 'fakultet/nastavnici/emeritus/start'

SCHEMA = '''
create table if not exists teachers (id text primary key, name text, full_name text, title text, katedra text, katedra_id integer,
	office text, email text, username text, phone text, hours text, research text, emeritus integer, html text,
	first_seen text, last_seen text, gone integer default 0);
create table if not exists teacher_subjects (teacher text, code text, name text, primary key (teacher, code));
'''


def split_title(text):
	"""'др Душан Љ. Ђукић, ванредни професор' -> ('др Душан Љ. Ђукић', 'ванредни професор')."""
	full, _, title = ' '.join(text.split()).partition(', ')
	return full, title


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
		a = p.select_one('a[href^="/fakultet/nastavnici/"]')
		m = a and re.fullmatch(r'/fakultet/nastavnici/(\d+)', a['href'])
		if not m:
			continue
		lines = [l.strip() for l in p.get_text('\n').split('\n') if l.strip()]
		mail = p.select_one('a[href^="mailto:"]')
		full, title = split_title(a.get_text())
		rows.append(dict(id=m.group(1), full_name=full, title=title,
			katedra=next((l for l in lines if l.startswith('Катедра')), None),
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


def main():
	from nastava import connect
	sys.stdout.reconfigure(encoding='utf-8')
	if (sys.argv[1] if len(sys.argv) > 1 else 'sync') != 'sync':
		sys.exit(__doc__)
	db = connect()
	db.executescript(SCHEMA)
	sync(db)


if __name__ == '__main__':
	assert split_title(' др Душан Љ. Ђукић,  ванредни професор ') == ('др Душан Љ. Ђукић', 'ванредни професор')
	assert field('Кабинет : 440\nТелефон: -', 'Кабинет') == '440'
	assert field('Кабинет\n:\nМејл адреса\n: x@y', 'Кабинет') is None
	assert plain_name('мастер маш. инж. Јована Р. Антић') == 'Јована Р. Антић' and plain_name('др Мирољуб Аџић') == 'Мирољуб Аџић'
	main()
