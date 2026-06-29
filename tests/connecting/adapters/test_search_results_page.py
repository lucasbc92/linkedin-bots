"""The search-results Page Object: one walk over a page, the profile link,
whether the page may be left — against a hand-built DOM."""
import inspect
import unittest

from linkedin_bots.connecting.adapters.selenium.search_results_page import SeleniumSearchResults
from tests.connecting.fakes import (FakeBrowser, FakeResults, Node, result_card,
                                    results_page)


class ScanTests(unittest.TestCase):
    """One walk over the page, whichever way each person has to be invited."""

    def page(self, *actions, **kwargs):
        return FakeResults([result_card(f"Person {i}", action)
                            for i, action in enumerate(actions)], **kwargs)

    def walk(self, bot, **kwargs):
        """Every (label, kind) the scan hands back for a page, in order."""
        processed, seen = set(), []
        while True:
            control, label, kind = bot.next_target(processed, **kwargs)
            if control is None:
                return seen
            processed.add(label)
            seen.append((label, kind))

    def test_people_come_back_in_the_order_the_page_shows_them(self):
        """Not Connect controls first and detours afterwards — one list, in
        card order, each person with the route their own card allows."""
        bot = results_page(FakeBrowser(self.page("follow", "connect", "follow")))
        self.assertEqual(self.walk(bot), [
            ("Follow Person 0", "follow"),
            ("Invite Person 1 to connect", "connect"),
            ("Follow Person 2", "follow"),
        ])

    def test_a_page_of_follow_only_cards_is_no_longer_a_dead_end(self):
        bot = results_page(FakeBrowser(self.page("follow", "follow")))
        self.assertEqual([kind for _label, kind in self.walk(bot)],
                         ["follow", "follow"])

    def test_rows_that_mount_late_are_still_reached(self):
        page = self.page("follow", "connect", "follow", "connect", mounted=1)
        bot = results_page(FakeBrowser(page))
        self.assertEqual(len(self.walk(bot)), 4)
        self.assertEqual(page.mounted, 4, "the scan must reach the list's end")

    def test_a_card_offering_both_is_taken_the_cheap_way(self):
        """Some cards carry Follow *and* Connect; opening a profile for one of
        those would spend a page load on someone already reachable."""
        row, control, url = result_card("Dual Card", "connect")
        row._select(".//div")[-1].append(Node("button", aria_label="Follow Dual Card"))
        bot = results_page(FakeBrowser(FakeResults([(row, control, url)])))
        self.assertEqual(self.walk(bot),
                         [("Invite Dual Card to connect", "connect")])

    def test_follow_cards_are_left_alone_where_the_page_must_not_be_left(self):
        """The one case that still skips them: a results URL that would not
        survive the round trip (see RestorableResultsTests)."""
        bot = results_page(FakeBrowser(self.page("follow", "connect", "follow")))
        self.assertEqual(self.walk(bot, include_follow=False),
                         [("Invite Person 1 to connect", "connect")])

    def test_the_walk_takes_the_detour_without_being_asked(self):
        default = inspect.signature(
            SeleniumSearchResults.next_target).parameters["include_follow"].default
        self.assertTrue(default)


class ProfileUrlTests(unittest.TestCase):
    def test_reads_the_persons_own_link_not_a_shared_connections(self):
        row, control, url = result_card(
            "Silvana Ferreira Alcides", "follow",
            mutuals=("flavioceci", "jefersonalberto"))
        bot = results_page(FakeBrowser(FakeResults([(row, control, url)])))
        self.assertEqual(bot.profile_url_for(control), url)

    def test_drops_the_query_string(self):
        row, control, url = result_card("Someone", "follow")
        link = row._select(".//a")[1]
        link.attrs["href"] = url + "?miniProfileUrn=urn%3Ali%3A123"
        bot = results_page(FakeBrowser(FakeResults([(row, control, url)])))
        self.assertEqual(bot.profile_url_for(control), url)


class RestorableResultsTests(unittest.TestCase):
    """Whether the results page may be left at all."""

    def bot_on(self, url, page_number):
        browser = FakeBrowser(FakeResults([]), url=url, page_number=page_number)
        return results_page(browser)

    def test_a_page_that_carries_its_number_may_be_left(self):
        bot = self.bot_on("https://www.linkedin.com/search/results/people/"
                          "?keywords=recruiter&page=7", 7)
        self.assertTrue(bot.detours_allowed())

    def test_page_one_may_be_left_without_the_parameter(self):
        bot = self.bot_on("https://www.linkedin.com/search/results/people/"
                          "?keywords=recruiter", 1)
        self.assertTrue(bot.detours_allowed())

    def test_a_page_that_would_be_lost_is_not_left(self):
        bot = self.bot_on("https://www.linkedin.com/search/results/people/"
                          "?keywords=recruiter", 7)
        self.assertFalse(bot.detours_allowed())


def test_a_profile_that_never_opened_does_not_step_off_the_results():
    """Going back from a page the detour never left would land on the
    previous page of results and rescan the wrong people."""
    row, control, url = result_card("Renata Santos", "follow")
    browser = FakeBrowser(FakeResults([(row, control, url)]))
    page = results_page(browser)
    assert page.return_to_results(browser.results_url) is True
    assert browser.backs == 0
