# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The asserts of scrapers/nastavnici.py (were its __main__ block), no network: uv run test/nastavnici_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from nastavnici import field, name_key, photo_urls, plain_name, split_title  # noqa: E402
from translit import to_cyr  # noqa: E402

assert split_title(" др Душан Љ. Ђукић,  ванредни професор ") == ("др Душан Љ. Ђукић", "ванредни професор")
assert split_title("др Зоран В. Стаменић , доцент")[0] == "др Зоран В. Стаменић"
assert photo_urls('<img src="/_media/fakultet/nastavnici/7.jpg?w=130&amp;tok=a">', None) == (
    "https://www.mas.bg.ac.rs/_media/fakultet/nastavnici/7.jpg?w=130&tok=a",
    "https://www.mas.bg.ac.rs/_media/fakultet/nastavnici/7.jpg",
)
assert photo_urls("", "https://x/y.jpg") == ("https://x/y.jpg", "https://x/y.jpg")
assert to_cyr("Miloš Lj. Glavonjić, Džajić") == "Милош Љ. Главоњић, Џајић"
assert name_key("Весна К. Спасојевић-Бркић") == name_key("Vesna Spasojević Brkić") == "vesna spasojevic brkic"
assert name_key("Dragan Lj.Milanović") == "dragan milanovic"
assert field("Кабинет : 440\nТелефон: -", "Кабинет") == "440"
assert field("Кабинет\n:\nМејл адреса\n: x@y", "Кабинет") is None
assert plain_name("мастер маш. инж. Јована Р. Антић") == "Јована Р. Антић" and plain_name("др Мирољуб Аџић") == "Мирољуб Аџић"
