"""The "Nazad" link under the crumbs, in Edge: python back_test.py <base url>.

The teachers' list -> a teacher -> the browser's back -> another teacher: each page's link is the page it was opened
from (no circle between the two teachers), with the browser's page cache and without, and after a reload."""

import sys

from playwright.sync_api import sync_playwright

base = sys.argv[1].rstrip("/")
sys.stdout.reconfigure(encoding="utf-8")


def back(page):
    """The link's (href, text), or None when it is hidden."""
    a = page.locator("[data-back]")
    return None if a.get_attribute("hidden") is not None else (a.get_attribute("href"), a.locator("b").inner_text())


def go(page, href):
    """As a click on a link: with a referrer."""
    with page.expect_navigation():
        page.evaluate("h => location.href = h", href)
    page.wait_for_load_state("load")


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    for cache in (True, False):
        page = browser.new_context().new_page()
        if not cache:  # an unload listener keeps a page out of the page cache: every page runs its script again
            page.add_init_script("addEventListener('unload', () => {})")
        page.goto(base + "/")
        go(page, "/nastavnici/")
        a, b = page.eval_on_selector_all("a[href^='/nastavnik/']", "as => [...new Set(as.map(a => a.getAttribute('href')))].slice(0, 2)")
        go(page, a)
        assert back(page)[0] == "/nastavnici/", back(page)
        page.go_back()
        page.wait_for_load_state("load")
        assert back(page)[0] == "/", f"the list after the browser's back: {back(page)}"
        go(page, b)
        assert back(page)[0] == "/nastavnici/", f"the second teacher: {back(page)}"
        page.click("[data-back]")
        page.wait_for_load_state("load")
        assert page.url == base + "/nastavnici/" and back(page)[0] == "/", (page.url, back(page))
        page.reload()
        assert back(page)[0] == "/", f"the list reloaded: {back(page)}"
        print("ok", "with" if cache else "without", "the page cache")
    browser.close()
