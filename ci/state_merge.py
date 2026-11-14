"""Pull the saved state into this PC's nastava.db without losing what only this PC has (ci/state.sh pull).

Usage: state_merge.py <state .tar.zst> <nastava.db>

The state (the scheduled runs' copy) wins: its rows stay as they are. Added from this PC's copy: a table the state
lacks, a column it lacks, and every row it lacks (a page, a file, a post scraped here and never saved). Nothing of
either copy is deleted. Then the result goes into nastava.db through SQLite's backup, not over the file: a running
dev server (pages/serve.py) keeps it and its WAL open, and Windows neither deletes nor replaces an open file.
"""
import os
import sqlite3
import sys
import tarfile
import tempfile

# Tables a scraper rewrites as a whole set (predmeti.py, nastavnici.py), not versions: a union would bring back what the
# faculty dropped. The state's set stays; this PC's only fills one the state lacks or has empty.
WHOLE = {"subject_places", "teacher_subjects"}


def merge(state, local):
    """Add to the database at state what the one at local has and it lacks (see above). Returns how many rows."""
    db = sqlite3.connect(state)
    db.execute("ATTACH ? AS l", (local,))
    have = {n for n, in db.execute("SELECT name FROM main.sqlite_master WHERE type = 'table'")}
    tables = db.execute("SELECT name, sql FROM l.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
    for name, sql in tables:
        q = '"' + name.replace('"', '""') + '"'
        if name not in have:
            db.execute(sql)
            for (index,) in db.execute("SELECT sql FROM l.sqlite_master WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
                                       (name,)).fetchall():
                db.execute(index)
        elif name in WHOLE and db.execute(f"SELECT 1 FROM main.{q} LIMIT 1").fetchone():
            continue
        mine = {r[1]: r for r in db.execute(f"PRAGMA main.table_info({q})")}
        for _, col, kind, notnull, default, _ in db.execute(f"PRAGMA l.table_info({q})").fetchall():
            if col not in mine:  # a column a newer scraper added here
                db.execute(f'ALTER TABLE main.{q} ADD COLUMN "{col}" {kind}' + (f" DEFAULT {default}" if default is not None else ""))
        cols = ", ".join(f'"{r[1]}"' for r in db.execute(f"PRAGMA l.table_info({q})"))
        # OR IGNORE: a row whose key the state has with other values stays the state's.
        db.execute(f"INSERT OR IGNORE INTO main.{q} ({cols}) SELECT {cols} FROM l.{q} EXCEPT SELECT {cols} FROM main.{q}")
    db.commit()
    added = db.total_changes
    db.execute("DETACH l")
    db.close()
    return added


def pull(archive, local):
    """The state at archive into local, merged. Rows added from local: told, and marked in $RUN_DIR/merged so that
    ci/deploy.sh saves the state even when the scrape changed nothing (else they would wait for a run that does)."""
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(archive, "r:zst") as t:
            t.extractall(tmp, filter="data")
        state = os.path.join(tmp, "nastava.db")
        added = merge(state, local) if os.path.exists(local) else 0
        src, dst = sqlite3.connect(state), sqlite3.connect(local, timeout=60)
        src.backup(dst)
        dst.close()
        src.close()
    if added:
        print(f"kept {added} rows only this copy had")
        if os.getenv("RUN_DIR"):
            with open(os.path.join(os.environ["RUN_DIR"], "merged"), "w") as f:
                f.write(str(added))


def _test():
    with tempfile.TemporaryDirectory() as tmp:
        s, l = os.path.join(tmp, "s.db"), os.path.join(tmp, "l.db")
        a = sqlite3.connect(s)
        a.executescript("CREATE TABLE posts (id integer primary key, html text);"
                        "INSERT INTO posts VALUES (1, 'state'), (3, 'new');"
                        "CREATE TABLE log (x text); INSERT INTO log VALUES ('a');"
                        "CREATE TABLE subject_places (subject text); INSERT INTO subject_places VALUES ('now');")
        a.commit()
        b = sqlite3.connect(l)
        b.executescript("CREATE TABLE posts (id integer primary key, html text, extra text);"
                        "INSERT INTO posts VALUES (1, 'old here', NULL), (2, 'only here', 'e');"
                        "CREATE TABLE log (x text); INSERT INTO log VALUES ('a'), ('b');"
                        "CREATE TABLE subject_places (subject text); INSERT INTO subject_places VALUES ('dropped');"
                        "CREATE TABLE wiki_pages (path text, sha text, primary key (path, sha)); CREATE INDEX w ON wiki_pages (sha);"
                        "INSERT INTO wiki_pages VALUES ('upis/start', 'x');")
        b.commit()
        b.close()
        a.close()
        assert merge(s, l) == 3  # post 2, log 'b', the wiki page
        m = sqlite3.connect(s)
        assert m.execute("SELECT id, html, extra FROM posts ORDER BY id").fetchall() == [(1, "state", None), (2, "only here", "e"), (3, "new", None)]
        assert m.execute("SELECT x FROM log ORDER BY x").fetchall() == [("a",), ("b",)]
        assert m.execute("SELECT * FROM subject_places").fetchall() == [("now",)]
        assert m.execute("SELECT * FROM wiki_pages").fetchall() == [("upis/start", "x")]
        assert m.execute("SELECT 1 FROM sqlite_master WHERE name = 'w'").fetchone()
        m.close()


if __name__ == "__main__":
    _test()
    if len(sys.argv) == 3:
        pull(*sys.argv[1:])
    elif len(sys.argv) != 1:
        sys.exit(__doc__)
