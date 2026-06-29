"""Tests for moving between results pages through the URL.

The pagination button sometimes takes the click and does nothing — seen on a
reverse run that stopped at page 90 after reloading it. LinkedIn's search URL
carries ``page=N``, so the bot can load the neighbouring page directly.

Run with:  python -m pytest
"""
import unittest

from linkedin_bots.connecting.adapters.selenium.search_results_page import (
    SeleniumSearchResults, page_url)
from tests.connecting.fakes import PassGuard

BASE = ("https://www.linkedin.com/search/results/people/?origin=FACETED_SEARCH"
        "&title=%22tech%20recruiter%22")


class PageUrlTests(unittest.TestCase):
    def test_replaces_the_page_parameter(self):
        self.assertEqual(page_url(f"{BASE}&page=90&spellCorrectionEnabled=true", 89),
                         f"{BASE}&page=89&spellCorrectionEnabled=true")

    def test_adds_the_parameter_when_absent(self):
        self.assertEqual(page_url(BASE, 2), f"{BASE}&page=2")

    def test_leaves_lookalike_parameters_alone(self):
        url = "https://www.linkedin.com/search/results/people/?homepage=3&page=4"
        self.assertEqual(page_url(url, 5),
                         "https://www.linkedin.com/search/results/people/?homepage=3&page=5")


class FakeButton:
    def __init__(self, number):
        self.text = str(number)


class FakeDriver:
    def __init__(self, url, page_number, lands_on=None):
        self.current_url = url
        self.page_number = page_number
        self.lands_on = lands_on
        self.loaded = []

    def get(self, url):
        self.loaded.append(url)
        self.current_url = url
        self.page_number = self.lands_on

    def find_element(self, by, selector):
        return FakeButton(self.page_number)


def make_bot(driver):
    bot = SeleniumSearchResults(driver, guard=PassGuard(), pause=lambda *_: None)
    return bot


class GoToPageByUrlTests(unittest.TestCase):
    def test_loads_the_target_page(self):
        driver = FakeDriver(f"{BASE}&page=90", 90, lands_on=89)
        self.assertTrue(make_bot(driver).go_to_page_by_url(89, timeout=0))
        self.assertEqual(driver.loaded, [f"{BASE}&page=89"])

    def test_reports_a_load_that_lands_elsewhere(self):
        driver = FakeDriver(f"{BASE}&page=90", 90, lands_on=1)
        self.assertFalse(make_bot(driver).go_to_page_by_url(89, timeout=0))


class FakeNavButton:
    def get_attribute(self, name):
        return "pagination-controls-prev-button" if name == "data-testid" else None


class ReloadedPageNavigationTests(unittest.TestCase):
    """On every page the bot had reloaded, the Previous button ignored the
    click and 15s went by before the URL fallback; pages that were never
    reloaded paged fine by clicking."""

    def make(self, reloaded_page):
        driver = FakeDriver(f"{BASE}&page=89", 89, lands_on=88)
        bot = make_bot(driver)
        bot.reverse = True
        bot.reloaded_page = reloaded_page
        bot.short_wait = type("W", (), {"until": lambda self, c: FakeNavButton()})()
        bot.driver.execute_script = lambda *a: None
        bot.clicks = 0

        def click(element):
            bot.clicks += 1
            driver.page_number = 88
        bot._robust_click = click
        return bot

    def test_a_reloaded_page_is_left_through_the_url(self):
        bot = self.make(reloaded_page=89)
        self.assertTrue(bot.go_to_next_page())
        self.assertEqual(bot.clicks, 0)
        self.assertEqual(bot.driver.loaded, [f"{BASE}&page=88"])

    def test_a_page_that_was_not_reloaded_is_left_by_clicking(self):
        bot = self.make(reloaded_page=None)
        self.assertTrue(bot.go_to_next_page())
        self.assertEqual(bot.clicks, 1)
        self.assertEqual(bot.driver.loaded, [])


if __name__ == "__main__":
    unittest.main()
