# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The asserts of scrapers/nastavnici_istorija.py (were its __main__ block), no network: uv run test/nastavnici_istorija_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from nastavnici_istorija import image_key, person_keys, wb_time  # noqa: E402

assert wb_time("20140629012301") == "2014-06-29T01:23:01+00:00"
assert image_key("http://cent.mas.bg.ac.rs/ljudi/slike/velike/dmilutinovic.jpg") == "dmilutinovic"
assert image_key("http://ie.mas.bg.ac.rs/data_store/images/zaposleni/photo_sonja_josipovic.jpg?x=1") == "sonja josipovic"
assert person_keys(dict(full_name="др Зоран В. Стаменић", email="ZStamenic@mas.bg.ac.rs")) == {"zoran stamenic", "zstamenic"}
