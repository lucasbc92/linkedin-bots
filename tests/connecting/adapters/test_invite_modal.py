"""The invite modal's outcome, with the shadow-DOM helpers stubbed out."""
from unittest import mock

import pytest

from linkedin_bots.connecting.adapters.selenium import invite_modal as modal_module
from linkedin_bots.connecting.adapters.selenium.invite_modal import SeleniumInviteModal
from linkedin_bots.connecting.application.ports import InviteResult, InviteStatus

LABEL = "Invite Ana Lima to connect"


class Guard:
    """check() answers from a script (then True); rate_limited() is fixed."""

    def __init__(self, checks=(), limited=False):
        self.checks = list(checks)
        self.limited = limited

    def check(self):
        return self.checks.pop(0) if self.checks else True

    def rate_limited(self):
        return self.limited


class _Button:
    def is_enabled(self):
        return True


def _modal(guard=None, shadow=True, email=False, buttons=True, closes=True, registers=True):
    modal = SeleniumInviteModal(driver=mock.Mock(), guard=guard or Guard(),
                                pause=lambda low, high: None)
    modal.clicked, modal.typed = [], []
    modal.get_modal_shadow_root = lambda timeout=10: "shadow" if shadow else None
    modal.modal_requires_email = lambda root: email
    modal.find_in_shadow = lambda root, css, **kw: _Button() if buttons else None
    modal._robust_click = lambda element, description="": modal.clicked.append(description)
    modal.fill_message_box = lambda box, text: modal.typed.append(text)
    modal.wait_modal_closed = lambda root, timeout=5: closes
    modal.verify_successful_invitation_sent = lambda label, full_name: registers
    modal.extract_name_from_modal = lambda root: "Ana"
    modal.dismiss_open_modal = lambda: modal.clicked.append("dismiss")
    return modal


@pytest.fixture(autouse=True)
def no_sleep():
    with mock.patch.object(modal_module.time, "sleep", lambda s: None):
        yield


def _complete(modal, name="Ana", note=lambda name: f"Olá, {name}!"):
    return modal.complete(LABEL, name, note)


def test_a_registered_invite_is_sent():
    modal = _modal()
    assert _complete(modal) == InviteResult(InviteStatus.SENT, "Ana")
    assert modal.typed == ["Olá, Ana!"] and "Send invitation button" in modal.clicked


def test_a_429_after_send_stops_the_run():
    assert _complete(_modal(guard=Guard(limited=True))).status is InviteStatus.STOP


def test_no_modal_is_skipped_unless_the_limit_is_up():
    assert _complete(_modal(shadow=False)).status is InviteStatus.SKIPPED
    assert _complete(_modal(shadow=False, guard=Guard([False]))).status is InviteStatus.STOP


def test_the_limit_showing_once_the_modal_opens_stops_the_run():
    assert _complete(_modal(guard=Guard([False]))).status is InviteStatus.STOP


def test_an_email_gate_is_skipped_and_dismissed():
    modal = _modal(email=True)
    assert _complete(modal).status is InviteStatus.SKIPPED
    assert modal.clicked == ["dismiss"]


def test_a_modal_that_never_closes_is_unconfirmed_unless_the_limit_is_up():
    assert _complete(_modal(closes=False)).status is InviteStatus.UNCONFIRMED
    assert _complete(_modal(closes=False, guard=Guard([True, False]))).status is InviteStatus.STOP


def test_an_invite_that_did_not_register_failed_unless_the_limit_is_up():
    assert _complete(_modal(registers=False)).status is InviteStatus.FAILED
    assert _complete(_modal(registers=False, guard=Guard([True, False]))).status is InviteStatus.STOP


def test_a_missing_button_is_skipped():
    assert _complete(_modal(buttons=False)).status is InviteStatus.SKIPPED


def test_no_note_clicks_send_without_a_note():
    modal = _modal()
    assert _complete(modal, note=None).status is InviteStatus.SENT
    assert modal.clicked == ["Send without a note button"] and modal.typed == []


def test_an_unknown_name_is_read_from_the_modal():
    modal = _modal()
    assert _complete(modal, name=None) == InviteResult(InviteStatus.SENT, "Ana")
    assert modal.typed == ["Olá, Ana!"]
