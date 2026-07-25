"""Opening a conversation and sending, with the browser stubbed out."""
import types

from linkedin_bots.messaging.adapters.selenium.thread_page import SeleniumThreadPage
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
