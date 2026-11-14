# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf", "numpy", "tzdata"]
# ///
"""The asserts of ci/runs.py (were its __main__ block), no network: uv run test/runs_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ci"))
import datetime as dt  # noqa: E402
import json  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402
from runs import hhmm, replay, scrapers  # noqa: E402

# A post at 10:00 waits for 10:52; one after the day's last run for the next day's first.
_r = [
    (dt.datetime(2026, 1, 5, 10, 52, tzinfo=dt.timezone.utc), "noon", "quiet"),
    (dt.datetime(2026, 1, 6, 10, 52, tzinfo=dt.timezone.utc), "noon", "quiet"),
]
_w, _t, _u = replay(
    [
        (dt.datetime(2026, 1, 5, 10, 0, tzinfo=dt.timezone.utc), "quiet"),
        (dt.datetime(2026, 1, 5, 11, 0, tzinfo=dt.timezone.utc), "quiet"),
    ],
    _r,
)
assert [w for w, _ in _w] == [52, 23 * 60 + 52] and _u["noon", "quiet"] == 1, (_w, _u)
assert hhmm(5 * 60 + 52) == "05:52 UTC (6:52/7:52)" and hhmm(23 * 60 + 52) == "23:52 UTC (0:52/1:52)"
# The parse of requests.jsonl: an answer and a failed request.
_d = Path(tempfile.mkdtemp())
(_d / "r.jsonl").write_text(
    json.dumps(dict(scraper="katedre", url="https://a/x", host="a", status=200, s=1.5, bytes=10, etag=True))
    + "\n"
    + json.dumps(dict(scraper="katedre", url="https://b/y", host="b", status="ConnectTimeout", s=60.0))
    + "\n"
)
_s = scrapers(_d / "r.jsonl")["katedre"]
assert (_s["requests"], _s["errors"], _s["hosts"]["a"]["etag"], _s["hosts"]["b"]["errors"], _s["slowest"][0][1]) == (
    2,
    {"ConnectTimeout": 1},
    1,
    1,
    "https://b/y",
), _s
