"""The follow-up walk, against an in-memory inbox."""
import logging
import re
from datetime import date, datetime

import pytest

from linkedin_bots.messaging.application.ports import (HistoryUnreadable, HistoryUnwritable,
                                                       SendResult, SendStatus)
from linkedin_bots.messaging.application.send_follow_ups import FollowUpSettings, SendFollowUps
from linkedin_bots.messaging.domain.past_sends import PastSend
from linkedin_bots.messaging.domain.routing import Routing, TemplateRoute
from linkedin_bots.messaging.domain.walk import ConversationCard
from linkedin_bots.shared.domain.messages import MessageTemplates


class Conv:
    def __init__(self, name, stamp="Oct 5", photo=None, last="You: Saudações!", pill=None):
        self.card = ConversationCard(name, stamp, photo or f"photo-{name}", pill, last)


class FakeInbox:
    """A list of conversations that re-sorts like LinkedIn's: a sent
    conversation jumps to the top. Handles are the Conv objects."""

    def __init__(self, convs, active=None, upward=False, opens=True):
        self.convs = list(convs)
        self.active = active
        self.upward = upward
        self.opens = opens
        self.read_count = 0

    def open(self):
        return self.opens

    def scroll_to_start_date(self, target):
        return True

    def start(self):
        if self.active is not None:
            return self.active, True
        if not self.convs:
            return None, False
        return (self.convs[-1] if self.upward else self.convs[0]), False

    def read(self, conv):
        self.read_count += 1
        return conv.card

    def ensure_name(self, conv):
        return conv.card.name

    def advance(self, conv):
        i = self.convs.index(conv) + (-1 if self.upward else 1)
        return self.convs[i] if 0 <= i < len(self.convs) else None

    def refresh(self, conv, name):
        return conv if conv in self.convs else None

    def jump_to_top(self, conv):
        self.convs.remove(conv)
        self.convs.insert(0, conv)


class FakeThread:
    def __init__(self, inbox, outcome=SendStatus.SENT, thread=None, interrupt_after=None):
        self.inbox = inbox
        self.outcome = outcome
        self.thread = thread
        self.interrupt_after = interrupt_after
        self.sent = []

    def send(self, conv, name, message, ruled_out=frozenset()):
        if self.interrupt_after is not None and len(self.sent) == self.interrupt_after:
            raise KeyboardInterrupt
        if self.thread and self.thread in ruled_out:
            return SendResult(SendStatus.SKIPPED, self.thread)
        self.sent.append((name, message))
        if self.outcome is SendStatus.SENT:
            self.inbox.jump_to_top(conv)
        return SendResult(self.outcome, self.thread)


class FakeHistory:
    def __init__(self, entries=None, unreadable=False):
        self.entries = entries or {}
        self.unreadable = unreadable
        self.recorded = []

    def load(self):
        if self.unreadable:
            raise HistoryUnreadable("Send history at X is unreadable (bad json).")
        return self.entries

    def record(self, name, photo=None, thread=None):
        self.recorded.append((name, photo, thread))


TEMPLATE = MessageTemplates(["Olá, {name}!"])
ROUTING = Routing(default=TEMPLATE, default_source="message.txt")


def _run(convs, history=None, routing=ROUTING, thread_kw=None, inbox_kw=None, **settings):
    inbox = FakeInbox(convs, **(inbox_kw or {}))
    thread = FakeThread(inbox, **(thread_kw or {}))
    history = history or FakeHistory()
    pauses = []
    use_case = SendFollowUps(inbox, thread, history, lambda low, high: pauses.append((low, high)),
                             routing, FollowUpSettings(**settings))
    use_case.run()
    return use_case, inbox, thread, history, pauses


def test_every_new_contact_gets_the_message_in_list_order():
    use_case, _, thread, history, _ = _run([Conv("Ana Silva"), Conv("Bruno Lima")])
    assert thread.sent == [("Ana Silva", "Olá, Ana!"), ("Bruno Lima", "Olá, Bruno!")]
    assert [r[0] for r in history.recorded] == ["Ana Silva", "Bruno Lima"]
    assert use_case.sent == 2


def test_walking_up_after_a_send_reaches_the_real_next_contact():
    convs = [Conv("Carla"), Conv("Bruno"), Conv("Ana")]
    _, _, thread, _, _ = _run(convs, inbox_kw={"active": convs[2], "upward": True},
                              upward=True)
    assert [name for name, _ in thread.sent] == ["Ana", "Bruno", "Carla"]


def test_a_namesake_invited_after_the_old_send_gets_the_message(caplog):
    caplog.set_level(logging.INFO, logger="linkedin_bot")
    history = FakeHistory({"Beatriz Teixeira": [PastSend(datetime(2026, 7, 25))]})
    july = Conv("Beatriz Teixeira", stamp="Jul 25, 2026", photo="JULY")
    october = Conv("Beatriz Teixeira", stamp="Oct 5, 2026", photo="OCT")
    _, _, thread, _, _ = _run([july, october], history=history)
    assert len(thread.sent) == 1
    assert caplog.text.count("Skipping Beatriz Teixeira — already messaged in a previous run") == 1
    assert "is a different person with the same name" in caplog.text


def test_each_contact_gets_the_template_its_preview_selects():
    english = MessageTemplates(["Hello, {name}!"])
    routing = Routing(default=TEMPLATE, default_source="message.txt",
                      rules=(TemplateRoute(re.compile("for 7"), english, "message_english.txt"),),
                      fallback=re.compile("há 7"))
    convs = [Conv("Ana Silva", last="Você: há 7 anos"), Conv("John Doe", last="You: for 7 years"),
             Conv("No Match", last="You: thanks!")]
    _, _, thread, _, _ = _run(convs, routing=routing)
    assert thread.sent == [("Ana Silva", "Olá, Ana!"), ("John Doe", "Hello, John!")]


def test_a_dry_run_never_opens_a_thread():
    use_case, _, thread, history, _ = _run([Conv("Ana Silva")], dry_run=True)
    assert thread.sent == [] and history.recorded == [] and use_case.sent == 0


def test_max_stops_after_that_many_sends():
    _, _, thread, _, _ = _run([Conv("A a"), Conv("B b"), Conv("C c")], max_messages=2)
    assert len(thread.sent) == 2


def test_the_date_limit_stops_the_walk():
    convs = [Conv("Ana Silva", stamp="Oct 5, 2026"), Conv("Old Contact", stamp="Jan 3, 2026")]
    _, _, thread, _, _ = _run(convs, date_limit=date(2026, 6, 1))
    assert [name for name, _ in thread.sent] == ["Ana Silva"]


def test_a_message_that_did_not_register_counts_as_failed_and_is_not_recorded():
    use_case, _, _, history, _ = _run([Conv("Ana Silva")],
                                      thread_kw={"outcome": SendStatus.NOT_REGISTERED})
    assert (use_case.failed, history.recorded) == (1, [])


def test_paces_between_contacts_after_each_real_attempt():
    _, _, _, _, pauses = _run([Conv("A a"), Conv("B b")])
    assert pauses == [(10, 20), (10, 20)]


def test_an_unreadable_history_stops_before_any_card(caplog):
    use_case, inbox, thread, _, _ = _run([Conv("Ana Silva")], history=FakeHistory(unreadable=True))
    assert inbox.read_count == 0 and thread.sent == []
    assert "Refusing to run" in caplog.text


def test_no_conversations_rendered_ends_quietly(caplog):
    _, inbox, _, _, _ = _run([Conv("Ana Silva")], inbox_kw={"opens": False})
    assert inbox.read_count == 0
    assert "never rendered any cards" in caplog.text


def test_ctrl_c_still_reports_the_tally(caplog):
    caplog.set_level(logging.INFO, logger="linkedin_bot")
    with pytest.raises(KeyboardInterrupt):
        _run([Conv("A a"), Conv("B b"), Conv("C c")], thread_kw={"interrupt_after": 1})
    assert "Run complete — sent: 1 | failed: 0 | skipped: 0" in caplog.text


class SlotInbox(FakeInbox):
    """Handles are positions, as LinkedIn reuses its <li> nodes by slot: after
    a re-sort the same handle shows whoever now sits there."""

    def start(self):
        if self.active is not None:
            return self.active, True
        return (len(self.convs) - 1 if self.upward else 0), False

    def read(self, i):
        self.read_count += 1
        return self.convs[i].card

    def ensure_name(self, i):
        return self.convs[i].card.name

    def advance(self, i):
        j = i + (-1 if self.upward else 1)
        return j if 0 <= j < len(self.convs) else None

    def refresh(self, i, name):
        if self.convs[i].card.name == name:
            return i
        return next((j for j, c in enumerate(self.convs) if c.card.name == name), None)


class SlotThread(FakeThread):
    def send(self, i, name, message, ruled_out=frozenset()):
        return super().send(self.inbox.convs[i], name, message, ruled_out)


def test_slot_reuse_after_a_send_is_followed_by_name():
    convs = [Conv("Carla"), Conv("Bruno"), Conv("Ana")]
    inbox = SlotInbox(convs, active=2, upward=True)
    thread = SlotThread(inbox)
    SendFollowUps(inbox, thread, FakeHistory(), lambda low, high: None, ROUTING,
                  FollowUpSettings(upward=True)).run()
    assert [name for name, _ in thread.sent] == ["Ana", "Bruno", "Carla"]


def test_a_send_records_the_photo_and_thread():
    _, _, _, history, _ = _run([Conv("Ana Silva", photo="PHOTO-A")],
                               thread_kw={"thread": "2-ana"})
    assert history.recorded == [("Ana Silva", "PHOTO-A", "2-ana")]


def test_a_recorded_thread_is_skipped_once_opened():
    history = FakeHistory({"Ana Silva": [PastSend(datetime(2026, 10, 1), photo="OLD",
                                                  thread="2-ana")]})
    use_case, _, thread, history, _ = _run([Conv("Ana Silva", photo="NEW")], history=history,
                                           thread_kw={"thread": "2-ana"})
    assert (use_case.skipped, thread.sent, history.recorded) == (1, [], [])


def test_an_error_counts_as_failed_without_a_pause():
    use_case, _, _, _, pauses = _run([Conv("Ana Silva")], thread_kw={"outcome": SendStatus.ERROR})
    assert (use_case.failed, pauses) == (1, [])


def test_a_send_that_cannot_be_recorded_stops_the_walk(caplog):
    class Unwritable(FakeHistory):
        def record(self, name, photo=None, thread=None):
            raise HistoryUnwritable("Could not write send history at X (locked).")

    use_case, _, thread, _, _ = _run([Conv("A a"), Conv("B b")], history=Unwritable())
    assert len(thread.sent) == 1 and use_case.sent == 1
    assert "could not be recorded" in caplog.text


def test_the_unreadable_history_advice_never_says_to_move_it(caplog):
    _run([Conv("Ana Silva")], history=FakeHistory(unreadable=True))
    assert "move" not in caplog.text and "restore a backup" in caplog.text
