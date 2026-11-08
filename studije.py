# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the schedule pages of www.mas.bg.ac.rs and every file they link.

Usage: studije.py sync

Each page and file is stored with its sha256; a changed page or file adds a version and the old one stays.
The site shows the newest version (pages/build.py).
"""
import hashlib
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse

SITE = 'https://www.mas.bg.ac.rs/'
PAGES = {'kalendar-nastave': 'Kalendar nastave', 'raspored-predavanja': 'Raspored predavanja', 'raspored-ispita': 'Raspored ispita'}
# Served from the archive's own origin, so only types that cannot run script there.
SAFE = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'txt', 'csv'}

SCHEMA = '''
create table if not exists study_pages (slug text, sha text, title text, html text, first_seen text, last_seen text, primary key (slug, sha));
create table if not exists study_files (path text, sha text, data blob, first_seen text, last_seen text, primary key (path, sha));
'''


def media_path(url):
	"""'studije/i_godina.pdf' for a DokuWiki media link (/_media/... or fetch.php?media=ns:name), else None."""
	u = urlparse(urljoin(SITE, url))
	if u.netloc not in ('www.mas.bg.ac.rs', 'mas.bg.ac.rs'):
		return None
	if u.path.startswith('/_media/'):
		return unquote(u.path[len('/_media/'):])
	match = re.search(r'(?:^|&)media=([^&]+)', u.query) if u.path.endswith('fetch.php') else None
	return unquote(match.group(1)).replace(':', '/') if match else None


def safe(path):
	# The path becomes a file path under the built site: no way out of it.
	inside = '..' not in path and not path.startswith(('/', '\\')) and ':' not in path and '\\' not in path
	return inside and '.' in path and path.rsplit('.', 1)[-1].lower() in SAFE


def store(db, table, key_col, key, sha, now, **cols):
	db.execute(f'insert into {table} ({key_col}, sha, first_seen, last_seen, {", ".join(cols)}) values (?,?,?,?{",?" * len(cols)}) '
		f'on conflict({key_col}, sha) do update set last_seen = excluded.last_seen', (key, sha, now, now, *cols.values()))


def sync(db):
	# Imported here: pages/build.py imports this module for media_path and has none of these installed.
	from bs4 import BeautifulSoup
	from documents import is_html_page
	from nastava import DELAY, session
	now = datetime.now(timezone.utc).isoformat(timespec='seconds')
	files = set()
	for slug, title in PAGES.items():
		r = session().get(f'{SITE}studije/{slug}', timeout=60)
		r.raise_for_status()
		main = BeautifulSoup(r.text, 'html.parser').select_one('div.page')
		if main is None:
			raise RuntimeError(f'{slug}: no div.page, the site changed')
		html = str(main)
		store(db, 'study_pages', 'slug', slug, hashlib.sha256(html.encode()).hexdigest(), now, title=title, html=html)
		files |= {p for tag in main.select('a[href], img[src]') for p in [media_path(tag.get('href') or tag.get('src'))] if p and safe(p)}
	ok = skipped = 0
	for path in sorted(files):
		time.sleep(DELAY)
		r = session().get(SITE + '_media/' + path, timeout=300)
		if r.status_code == 404 or is_html_page(r.content):
			print(f'skip {path}: {r.status_code}, html page' if r.ok else f'skip {path}: {r.status_code}', flush=True)
			skipped += 1
			continue
		r.raise_for_status()
		store(db, 'study_files', 'path', path, hashlib.sha256(r.content).hexdigest(), now, data=r.content)
		ok += 1
	db.commit()
	print(f'{len(PAGES)} pages, {ok} files, {skipped} skipped', flush=True)


def main():
	from nastava import connect
	sys.stdout.reconfigure(encoding='utf-8')
	db = connect()
	db.executescript(SCHEMA)
	if (sys.argv[1] if len(sys.argv) > 1 else 'sync') != 'sync':
		sys.exit(__doc__)
	sync(db)


if __name__ == '__main__':
	# media_path and safe are checked in test/parsers_test.py.
	main()
