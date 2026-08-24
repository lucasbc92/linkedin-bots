"""Tests for the shared trusted-click ladder.

Every bot clicks through this one ladder, so its fallback order is worth
pinning down.

Run with:  python -m pytest
"""

import logging
import unittest
from unittest import mock


from linkedin_bots.shared.infrastructure.clicking import ClickMixin


class _Element:
    """Selenium element stand-in whose native click can be made to fail."""

    location = {'x': 10, 'y': 20}
    size = {'width': 100, 'height': 40}

    def __init__(self, native_ok=True):
        self.native_ok = native_ok
        self.clicked = False

    def click(self):
        if not self.native_ok:
            raise RuntimeError("element not interactable")
        self.clicked = True


class _Driver:
    """Records what the ladder tried, and can fail chosen strategies."""

    def __init__(self, cdp_ok=True, script_ok=True):
        self.cdp_ok = cdp_ok
        self.script_ok = script_ok
        self.tried = []

    def execute_cdp_cmd(self, cmd, params):
        self.tried.append(('cdp', params.get('type')))
        if not self.cdp_ok:
            raise RuntimeError("cdp unavailable")

    def execute_script(self, script, *args):
        kind = 'js_click' if '.click()' in script else 'scroll'
        self.tried.append((kind, None))
        if kind == 'js_click' and not self.script_ok:
            raise RuntimeError("script blocked")


class _Clicker(ClickMixin):
    def __init__(self, driver):
        self.driver = driver


def _clicker(cdp_ok=True, script_ok=True):
    return _Clicker(_Driver(cdp_ok=cdp_ok, script_ok=script_ok))


class ClickLadderTest(unittest.TestCase):
    def test_native_click_short_circuits_the_ladder(self):
        c = _clicker()
        el = _Element(native_ok=True)
        self.assertTrue(c._robust_click(el))
        self.assertTrue(el.clicked)
        self.assertEqual(c.driver.tried, [])   # nothing else was attempted

    def test_falls_through_to_cdp_when_native_and_actionchains_fail(self):
        c = _clicker()
        # ActionChains talks to a real driver; make it raise so CDP is next.
        with mock.patch("linkedin_bots.shared.infrastructure.clicking.ActionChains", side_effect=RuntimeError("no chains")):
            self.assertTrue(c._robust_click(_Element(native_ok=False)))
        self.assertIn(('cdp', 'mousePressed'), c.driver.tried)
        self.assertIn(('cdp', 'mouseReleased'), c.driver.tried)

    def test_falls_through_to_js_when_cdp_fails(self):
        c = _clicker(cdp_ok=False)
        with mock.patch("linkedin_bots.shared.infrastructure.clicking.ActionChains", side_effect=RuntimeError("no chains")):
            self.assertTrue(c._robust_click(_Element(native_ok=False)))
        self.assertEqual(c.driver.tried[-1], ('js_click', None))

    def test_returns_false_only_when_every_strategy_fails(self):
        c = _clicker(cdp_ok=False, script_ok=False)
        with self.assertLogs("linkedin_bot", logging.WARNING):
            with mock.patch("linkedin_bots.shared.infrastructure.clicking.ActionChains", side_effect=RuntimeError("no chains")):
                self.assertFalse(c._robust_click(_Element(native_ok=False)))

    def test_cdp_click_presses_and_releases_at_the_element_centre(self):
        c = _clicker()
        self.assertTrue(c._cdp_click(_Element()))
        self.assertEqual(c.driver.tried,
                         [('cdp', 'mousePressed'), ('cdp', 'mouseReleased')])

    def test_cdp_click_reports_failure_instead_of_raising(self):
        c = _clicker(cdp_ok=False)
        self.assertFalse(c._cdp_click(_Element()))


class EveryClickerSharesTheLadderTest(unittest.TestCase):
    """One implementation of the ladder, not one per bot."""

    def test_clickers_inherit_rather_than_redefine(self):
        from linkedin_bots.connecting.adapters.selenium.invite_modal import SeleniumInviteModal
        from linkedin_bots.connecting.adapters.selenium.profile_page import SeleniumProfilePage
        from linkedin_bots.connecting.adapters.selenium.search_results_page import (
            SeleniumSearchResults)
        from linkedin_bots.messaging.adapters.selenium.conversation_list import (
            SeleniumConversationList)
        from linkedin_bots.messaging.adapters.selenium.thread_page import SeleniumThreadPage
        from linkedin_bots.withdrawing.adapters.selenium.sent_invitations_page import (
            SeleniumSentInvitationsPage)

        for bot in (SeleniumSearchResults, SeleniumProfilePage, SeleniumInviteModal,
                    SeleniumConversationList, SeleniumThreadPage,
                    SeleniumSentInvitationsPage):
            self.assertTrue(issubclass(bot, ClickMixin), bot.__name__)
            for method in ("_robust_click", "_cdp_click"):
                self.assertNotIn(method, vars(bot),
                                 f"{bot.__name__} still defines its own {method}")


if __name__ == "__main__":
    unittest.main()
