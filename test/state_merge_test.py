"""The asserts of ci/state_merge.py (were its __main__ block), no network: uv run test/state_merge_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ci"))
import os  # noqa: E402
import sqlite3  # noqa: E402
import tempfile  # noqa: E402
from state_merge import merge  # noqa: E402


def _test():
    with tempfile.TemporaryDirectory() as tmp:
        s, l = os.path.join(tmp, "s.db"), os.path.join(tmp, "l.db")
        a = sqlite3.connect(s)
        a.executescript(
            "CREATE TABLE posts (id integer primary key, html text);"
            "INSERT INTO posts VALUES (1, 'state'), (3, 'new');"
            "CREATE TABLE log (x text); INSERT INTO log VALUES ('a');"
            "CREATE TABLE subject_places (subject text); INSERT INTO subject_places VALUES ('now');"
        )
        a.commit()
        b = sqlite3.connect(l)
        b.executescript(
            "CREATE TABLE posts (id integer primary key, html text, extra text);"
            "INSERT INTO posts VALUES (1, 'old here', NULL), (2, 'only here', 'e');"
            "CREATE TABLE log (x text); INSERT INTO log VALUES ('a'), ('b');"
            "CREATE TABLE subject_places (subject text); INSERT INTO subject_places VALUES ('dropped');"
            "CREATE TABLE wiki_pages (path text, sha text, primary key (path, sha)); CREATE INDEX w ON wiki_pages (sha);"
            "INSERT INTO wiki_pages VALUES ('upis/start', 'x');"
        )
        b.commit()
        b.close()
        a.close()
        assert merge(s, l) == 3  # post 2, log 'b', the wiki page
        m = sqlite3.connect(s)
        assert m.execute("SELECT id, html, extra FROM posts ORDER BY id").fetchall() == [
            (1, "state", None),
            (2, "only here", "e"),
            (3, "new", None),
        ]
        assert m.execute("SELECT x FROM log ORDER BY x").fetchall() == [("a",), ("b",)]
        assert m.execute("SELECT * FROM subject_places").fetchall() == [("now",)]
        assert m.execute("SELECT * FROM wiki_pages").fetchall() == [("upis/start", "x")]
        assert m.execute("SELECT 1 FROM sqlite_master WHERE name = 'w'").fetchone()
        m.close()


_test()
