"""The profile Page Object: finding the right Connect control."""
import unittest
from unittest import mock

from tests.connecting.fakes import (FakeBrowser, FakeProfile, FakeResults, profile_module,
                                    profile_page)


class ProfileConnectTests(unittest.TestCase):
    """Finding the right Connect control on a profile page."""

    def setUp(self):
        patched = mock.patch.object(profile_module.time, "sleep", lambda *_: None)
        patched.start()
        self.addCleanup(patched.stop)

    def browser_on(self, profile):
        url = "https://www.linkedin.com/in/renata/"
        browser = FakeBrowser(FakeResults([]), {url: profile})
        browser.get(url)
        return browser

    def test_never_invites_someone_from_the_profiles_rail(self):
        """A profile page shows Connect buttons for other people too; the one
        that gets clicked is matched by name."""
        profile = FakeProfile("Renata Santos", connect_in_top_card=True,
                              rail=("Someone Else", "Another Person"))
        bot = profile_page(self.browser_on(profile))
        control = bot.find_profile_connect("Renata Santos", timeout=0)
        self.assertEqual(control.get_attribute("aria-label"),
                         "Invite Renata Santos to connect")

    def test_a_page_with_only_other_peoples_connects_yields_nothing(self):
        profile = FakeProfile("Renata Santos", menu_connect=None)
        bot = profile_page(self.browser_on(profile))
        self.assertIsNone(bot.find_profile_connect("Renata Santos", timeout=0))

    def test_the_menus_connect_is_labelled_on_a_div_inside_its_link(self):
        """The regression this class exists for. LinkedIn does not put the
        label on the menu item's <a> — it puts it on a div inside it, so a
        search for a labelled <a> or <button> found nothing and every
        Follow-only person was skipped."""
        profile = FakeProfile("Renata Santos")
        browser = self.browser_on(profile)
        bot = profile_page(browser)

        control = bot.connect_from_more_menu("Renata Santos")

        self.assertEqual(profile.more_clicks, 1)
        self.assertIsNotNone(control, "the Connect in the More menu was missed")
        self.assertEqual(control.tag, "a", "the link is what carries the action")
        self.assertIn("/preload/custom-invite/", control.get_attribute("href"))
        self.assertIsNone(control.get_attribute("aria-label"),
                          "the label is on the div inside it, not on the link")

    def test_the_named_search_reaches_into_the_open_menu(self):
        """The search that keeps the rail safe has to see the menu item too,
        and the label it carries is on a div, not on the link."""
        profile = FakeProfile("Renata Santos")
        bot = profile_page(self.browser_on(profile))
        profile.click_more()

        control = bot.find_profile_connect("Renata Santos", timeout=0)

        self.assertIsNotNone(
            control, "the menu's Connect is labelled on an inner div")
        self.assertIn("/preload/custom-invite/", control.get_attribute("href"))

    def test_an_unlabelled_menu_item_is_found_by_what_it_reads(self):
        """If LinkedIn drops the aria-label entirely, the item in the person's
        own menu that reads Connect is still unambiguous."""
        profile = FakeProfile("Renata Santos", menu_connect="unlabelled")
        bot = profile_page(self.browser_on(profile))
        control = bot.connect_from_more_menu("Renata Santos")
        self.assertIsNotNone(control)
        self.assertIn("/preload/custom-invite/", control.get_attribute("href"))

    def test_a_menu_item_that_is_not_connect_is_never_taken(self):
        profile = FakeProfile("Renata Santos", menu_connect=None)
        bot = profile_page(self.browser_on(profile))
        self.assertIsNone(bot.connect_in_open_menu() if profile.menu
                          else bot.connect_from_more_menu("Renata Santos"))

    def test_a_name_in_a_different_unicode_form_still_matches(self):
        """'Nájera' can arrive composed from the card and decomposed from the
        profile; they spell the same name."""
        profile = FakeProfile("Alex Nájera Arcia", connect_in_top_card=True)
        bot = profile_page(self.browser_on(profile))
        decomposed = "Alex Nájera Arcia"
        self.assertNotEqual(decomposed, "Alex Nájera Arcia")
        self.assertIsNotNone(bot.find_profile_connect(decomposed, timeout=0))

    def test_gives_up_after_a_few_more_buttons(self):
        """The sticky header renders its own More button, and posts further
        down the page render others; only the first few are worth trying."""
        profile = FakeProfile("Renata Santos", menu_connect=None, more_buttons=9)
        bot = profile_page(self.browser_on(profile))
        self.assertIsNone(bot.connect_from_more_menu("Renata Santos"))
        self.assertEqual(profile.more_clicks, profile_module.MORE_BUTTON_ATTEMPTS)


def test_open_connect_clicks_the_named_control_and_reports_it():
    url = "https://www.linkedin.com/in/renata/"
    profile = FakeProfile("Renata Santos")
    browser = FakeBrowser(FakeResults([]), {url: profile})
    browser.get(url)
    with mock.patch.object(profile_module.time, "sleep", lambda *_: None):
        assert profile_page(browser).open_connect("Renata Santos") is True
    assert profile.more_clicks == 1


def test_open_connect_without_any_connect_is_false():
    url = "https://www.linkedin.com/in/renata/"
    browser = FakeBrowser(FakeResults([]), {url: FakeProfile("Renata Santos", menu_connect=None)})
    browser.get(url)
    with mock.patch.object(profile_module.time, "sleep", lambda *_: None):
        assert profile_page(browser).open_connect("Renata Santos") is False
