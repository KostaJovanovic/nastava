# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The asserts of scrapers/predmeti.py (were its __main__ block), no network: uv run test/predmeti_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from predmeti import subject_id  # noqa: E402

assert subject_id("/studije/predmeti/0642") == "0642" and subject_id("/studije/oas/start") is None
