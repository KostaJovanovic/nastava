"""Download only the attachments the test posts link (no id sweep), then extract. Run with DB and FILES set."""

import sys

sys.path.insert(0, "scrapers")
import documents as d
import nastava as n

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    db = n.connect()
    for (i,) in db.execute("select id from documents where post is not null and fetched = 0").fetchall():
        print(i, d.save(db, i, d.fetch(i)))
    db.commit()
    d.run_extract(db, False)
    for row in db.execute("select id, mime, size, length(text), error, title from documents"):
        print(row)
