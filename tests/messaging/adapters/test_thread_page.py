"""Opening a conversation and sending, with the browser stubbed out."""
import types

from linkedin_bots.messaging.adapters.selenium.thread_page import (CARD_HEADLINE_XPATH,
                                                                  CARD_NAME_XPATH,
                                                                  HEADLINE_SCROLLS,
                                                                  HEADLINE_TITLE_XPATH,
                                                                  SeleniumThreadPage)
from linkedin_bots.messaging.application.ports import SendResult, SendStatus


def _page(url="https://www.linkedin.com/messaging/thread/2-ana/", sent=True, opens=True):
    driver = types.SimpleNamespace(current_url=url, execute_script=lambda *a: None)
    page = SeleniumThreadPage(driver, pause=lambda low, high: None)
    page._robust_click = lambda *a: True
    page._wait_thread_open = lambda *a, **k: opens
    page._get_compose_box = lambda: object()
    page.typed = []

    def send_message(compose, message, name):
        page.typed.append(message)
        return sent

    page._send_message = send_message
    return page


def test_a_send_reports_its_thread():
    assert _page().send(object(), "Ana Silva", "Olá") == SendResult(SendStatus.SENT, "2-ana")


def test_a_recorded_thread_is_skipped_once_opened():
    page = _page()
    result = page.send(object(), "Ana Silva", "Olá", ruled_out=frozenset({"2-ana"}))
    assert result.status is SendStatus.SKIPPED and page.typed == []


def test_a_thread_that_never_opens_is_skipped():
    assert _page(opens=False).send(object(), "Ana Silva", "Olá").status is SendStatus.SKIPPED


def test_a_message_that_does_not_register_is_reported():
    assert _page(sent=False).send(object(), "Ana Silva", "Olá").status is SendStatus.NOT_REGISTERED


def test_an_unexpected_error_is_contained():
    page = _page()

    def boom(*args):
        raise RuntimeError("driver died")

    page._robust_click = boom
    assert page.send(object(), "Ana Silva", "Olá").status is SendStatus.ERROR


def test_open_then_send_open_sends_once_and_reports_the_thread():
    page = _page()
    assert page.open(object(), "Ana Silva") is None
    assert page.send_open("Ana Silva", "Olá") == SendResult(SendStatus.SENT, "2-ana")
    assert page.typed == ["Olá"]


def test_open_skips_a_ruled_out_thread():
    page = _page()
    assert page.open(object(), "Ana Silva", ruled_out=frozenset({"2-ana"})).status is SendStatus.SKIPPED


def test_send_open_skips_when_the_panel_switched_contact():
    page = _page()
    answers = iter([True, False])
    page._wait_thread_open = lambda *a, **k: next(answers)
    assert page.open(object(), "Ana Silva") is None
    assert page.send_open("Ana Silva", "Olá").status is SendStatus.SKIPPED
    assert page.typed == []


class _El:
    """A stand-in WebElement: its text, its title attribute and its children by XPath."""

    def __init__(self, text="", title=None, children=None):
        self.text = text
        self._title = title
        self._children = children or {}

    def get_attribute(self, name):
        return self._title if name == "title" else None

    def find_elements(self, by, xpath):
        return self._children.get(xpath, [])


def _card(name, text, title=None):
    inner = [_El(text, title)] if title else []
    subtitle = _El(text, children={HEADLINE_TITLE_XPATH: inner})
    return _El(children={CARD_NAME_XPATH: [_El(name)], CARD_HEADLINE_XPATH: [subtitle]})


def _headline_page(*card_lists):
    """A page whose profile cards are each list in turn, one per look."""
    page = _page()
    looks = iter(card_lists)
    page._profile_cards = lambda: next(looks, card_lists[-1])
    page.scrolls = 0

    def scroll():
        page.scrolls += 1

    page._scroll_history_to_top = scroll
    return page


def test_the_headline_prefers_the_full_title_attribute():
    card = _card("Ana Silva", "Senior Software Engineer | Ja…",
                 title="Senior Software Engineer | Java | Spring")
    assert _headline_page([card]).headline("Ana Silva") == "Senior Software Engineer | Java | Spring"


def test_the_headline_falls_back_to_the_subtitle_text():
    assert _headline_page([_card("Ana Silva", " Tech Recruiter ")]).headline("Ana Silva") == "Tech Recruiter"


def test_a_card_for_someone_else_is_ignored():
    page = _headline_page([_card("Bruno Lima", "Tech Recruiter")])
    assert page.headline("Ana Silva") is None
    assert page.scrolls == HEADLINE_SCROLLS


def test_no_card_scrolls_to_the_top_a_bounded_number_of_times():
    page = _headline_page([])
    assert page.headline("Ana Silva") is None
    assert page.scrolls == HEADLINE_SCROLLS


def test_a_card_that_loads_after_one_scroll_is_read():
    page = _headline_page([], [_card("Ana Silva", "Desenvolvedora")])
    assert page.headline("Ana Silva") == "Desenvolvedora"
    assert page.scrolls == 1


def test_reading_the_headline_never_raises():
    page = _page()

    def boom():
        raise RuntimeError("driver died")

    page._profile_cards = boom
    assert page.headline("Ana Silva") is None
