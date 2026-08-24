"""The sent-invitation page adapter, with the browser primitives stubbed out."""
import pytest
from selenium.common.exceptions import StaleElementReferenceException

from linkedin_bots.withdrawing.adapters.selenium.sent_invitations_page import (
    SeleniumSentInvitationsPage)
from linkedin_bots.withdrawing.application.ports import LoadResult, StaleListError
from linkedin_bots.withdrawing.domain.invitation import SentInvitation

PAGE = 50


def _growing_page(loaded=50, total=500):
    """A page whose in-page loop adds one page of cards per page load."""
    page = SeleniumSentInvitationsPage(driver=None)
    page.chunks = []
    state = {"count": loaded}

    def expand_in_page(max_pages=None, max_cards=None, **kwargs):
        page.chunks.append({"max_pages": max_pages, "max_cards": max_cards})
        pages = 0
        for _ in range(max_pages):
            # The real in-page loop checks the cap before each page load.
            if max_cards and state["count"] >= max_cards:
                return {"cards": state["count"], "pages": pages, "reason": "cap"}
            if state["count"] >= total:
                return {"cards": state["count"], "pages": pages, "reason": "end"}
            state["count"] += PAGE
            pages += 1
        return {"cards": state["count"], "pages": pages, "reason": "chunk-done"}

    page.open = lambda: None
    page.card_count = lambda: state["count"]
    page.sent_labels = lambda: []
    page.expand_in_page = expand_in_page
    return page


def _scroll_only_page(loaded=50, total=1000, step=10):
    """A build with no "Load more": scrolling to the bottom mounts a page."""
    page = SeleniumSentInvitationsPage(driver=None)
    state = {"count": loaded}

    def wait_for_growth(previous, timeout=None):
        state["count"] = min(state["count"] + step, total)
        return state["count"]

    page.open = lambda: None
    page.card_count = lambda: state["count"]
    page.sent_labels = lambda: []
    page._scroll_list_bottom = lambda: None
    page._find_load_more = lambda: None
    page._page_pause = lambda: None
    page._wait_for_growth = wait_for_growth
    return page


class TestLoadCap:
    """--max caps the loading phase, in invitation cards."""

    def test_stops_at_the_cap_instead_of_the_end_of_the_list(self):
        assert _growing_page().load(max_cards=200) == LoadResult(200, exhausted=False)

    def test_the_cap_reaches_the_in_page_loop(self):
        page = _growing_page()
        page.load(max_cards=200)
        assert page.chunks and all(c["max_cards"] == 200 for c in page.chunks)

    def test_a_cap_already_covered_loads_nothing(self):
        page = _growing_page(loaded=300)
        assert page.load(max_cards=200).count == 300
        assert page.chunks == []

    def test_no_cap_loads_to_the_end(self):
        assert _growing_page().load() == LoadResult(500, exhausted=True)


class TestScrollOnlyBudget:
    """A page budget has to bound a list that loads without a button."""

    def test_scroll_loaded_pages_count_against_the_budget(self):
        assert _scroll_only_page().load(max_pages=2, use_js=False).count == 70

    def test_the_card_cap_still_holds_without_a_button(self):
        assert _scroll_only_page().load(max_cards=80, use_js=False).count <= 90


class _RowsDriver:
    def __init__(self, rows):
        self.rows = rows

    def execute_script(self, script, *args):
        return self.rows if "componentkey" in script else [1]


def test_loaded_invitations_become_value_objects():
    page = SeleniumSentInvitationsPage(_RowsDriver([
        {"link": "L0", "name": "Ana", "age": "Sent 2 months ago", "key": "k0"},
        {"link": "L1", "name": "", "age": "", "key": "k1"},
    ]))
    assert page.loaded_invitations() == [
        SentInvitation("Ana", "Sent 2 months ago", "k0"),
        SentInvitation("", "", "k1"),
    ]


def test_an_invitation_never_read_is_not_withdrawn():
    page = SeleniumSentInvitationsPage(driver=None)
    assert page.withdraw(SentInvitation("Ana", "Sent 2 months ago", "k0")) is False


def test_a_list_that_re_rendered_is_reported_as_stale():
    page = SeleniumSentInvitationsPage(_RowsDriver([
        {"link": "L0", "name": "Ana", "age": "Sent 2 months ago", "key": "k0"}]))
    invitation = page.loaded_invitations()[0]

    def stale_click(element, description="element"):
        raise StaleElementReferenceException("re-rendered")

    page._robust_click = stale_click
    with pytest.raises(StaleListError):
        page.withdraw(invitation)
