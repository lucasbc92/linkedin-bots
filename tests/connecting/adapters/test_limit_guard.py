"""The weekly-limit guard: its dialogs and HTTP 429."""
import json
from unittest import mock

from linkedin_bots.connecting.adapters.selenium import limit_guard as guard_module
from linkedin_bots.connecting.adapters.selenium.limit_guard import SeleniumLimitGuard


class FakeDriver:
    """Shows the hard-limit dialog, the close-to-limit warning, or neither."""

    def __init__(self, dialog=None, perf=()):
        self.dialog = dialog
        self.perf = list(perf)
        self.clicked = 0

    def find_elements(self, by, xpath):
        if self.dialog == "reached" and "reached the weekly" in xpath:
            return ["h2"]
        if self.dialog == "close" and "close to the weekly" in xpath:
            return ["h2"]
        return []

    def find_element(self, by, xpath):
        return "got-it"

    def execute_script(self, script, *args):
        self.clicked += 1

    def get_log(self, kind):
        entries, self.perf = self.perf, []
        return entries


def _guard(driver, confirm=lambda question: False, auto_continue=False, perf_logging=False):
    return SeleniumLimitGuard(driver, perf_logging, confirm, auto_continue=auto_continue)


def _check(guard):
    with mock.patch.object(guard_module.time, "sleep", lambda s: None):
        return guard.check()


def test_no_dialog_lets_the_run_go_on():
    assert _check(_guard(FakeDriver())) is True


def test_the_weekly_limit_reached_stops_the_run():
    driver = FakeDriver("reached")
    assert _check(_guard(driver, confirm=lambda q: True, auto_continue=True)) is False
    assert driver.clicked == 1


def test_close_to_the_limit_asks_and_honours_the_answer():
    assert _check(_guard(FakeDriver("close"), confirm=lambda q: True)) is True
    assert _check(_guard(FakeDriver("close"), confirm=lambda q: False)) is False


def test_auto_continue_goes_on_past_the_warning_without_asking():
    def never_asked(question):
        raise AssertionError("must not prompt")

    driver = FakeDriver("close")
    assert _check(_guard(driver, confirm=never_asked, auto_continue=True)) is True
    assert driver.clicked == 1


def _response(status, url="https://www.linkedin.com/voyager/api/verifyQuotaAndCreate"):
    return {"message": json.dumps({"message": {
        "method": "Network.responseReceived",
        "params": {"response": {"url": url, "status": status, "headers": {}}}}})}


def test_a_429_from_the_invite_endpoint_is_a_rate_limit():
    guard = _guard(FakeDriver(perf=[_response(429)]), perf_logging=True)
    assert guard.detect_rate_limit_429(wait=0) is True


def test_a_successful_invite_response_is_not():
    guard = _guard(FakeDriver(perf=[_response(200)]), perf_logging=True)
    assert guard.detect_rate_limit_429(wait=0) is False


def test_without_performance_logging_nothing_is_detected():
    assert _guard(FakeDriver(perf=[_response(429)])).rate_limited() is False
