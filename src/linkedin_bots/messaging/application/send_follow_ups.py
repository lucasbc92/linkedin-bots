"""Send a follow-up to each conversation, walking the list one card at a time.

The walk goes strictly in one direction — downward (newer→older) by
default, upward with ``upward`` — and the next contact is ALWAYS the
adjacent card. The list re-sorts the moment a message is sent (the messaged
contact jumps to the top), so the next card is captured *before* sending.
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from linkedin_bots.messaging.application.ports import (ConversationList, HistoryUnreadable,
                                                       HistoryUnwritable, Pause, SendStatus,
                                                       SentHistory, Thread)
from linkedin_bots.messaging.domain.routing import Routing
from linkedin_bots.messaging.domain.walk import Skip, Stop, assess
from linkedin_bots.shared.domain.names import display_first_name

logger = logging.getLogger("linkedin_bot")

# Gap after each real send attempt, before the next contact.
BETWEEN_CONTACTS = (10, 20)


@dataclass(frozen=True)
class FollowUpSettings:
    """How a run behaves; see ``linkedin-bots message --help`` for each flag."""

    date_limit: Optional[date] = None
    start_date: Optional[date] = None
    dry_run: bool = False
    max_messages: Optional[int] = None
    upward: bool = False


class SendFollowUps:
    def __init__(self, conversations: ConversationList, thread: Thread,
                 history: SentHistory, pause: Pause, routing: Routing,
                 settings: FollowUpSettings):
        self.conversations = conversations
        self.thread = thread
        self.history = history
        self.pause = pause
        self.routing = routing
        self.settings = settings
        self.sent = 0
        self.failed = 0
        self.skipped = 0

    def run(self):
        """Walk the list; the tally is logged however the run ends."""
        try:
            self._walk()
        finally:
            logger.info(
                f"Run complete — "
                f"sent: {self.sent} | failed: {self.failed} | skipped: {self.skipped}")

    def _walk(self):
        s = self.settings
        if not self.conversations.open():
            logger.error("Conversation list never rendered any cards. Nothing to do.")
            return
        if s.start_date and not self.conversations.scroll_to_start_date(s.start_date):
            logger.error(f"No conversation dated on or before "
                         f"{s.start_date} was found. Nothing to do.")
            return

        # Durable record of everyone already messaged in past runs; used
        # only to decide whether to skip a card, never to navigate.
        try:
            history = self.history.load()
        except HistoryUnreadable as e:
            logger.error(f"{e} Refusing to run: every contact in it would look "
                         f"new. Fix the file (or restore a backup), then run "
                         f"again — removing it would message everyone in it "
                         f"a second time.")
            return
        # (name, photo) walked past in this run — the photo keeps two people
        # who share a name apart.
        handled = set()

        current, from_active = self.conversations.start()
        if from_active:
            logger.info(f"Starting from the active (clicked) conversation, "
                        f"walking {'up' if s.upward else 'down'}.")
        elif s.upward:
            logger.info("No active conversation — starting from the bottom (reverse).")
        else:
            logger.info("No active conversation — starting from the top.")

        while current is not None:
            card = self.conversations.read(current)
            verdict = assess(card, history=history, handled=handled,
                             routing=self.routing, date_limit=s.date_limit,
                             upward=s.upward)
            if isinstance(verdict, Stop):
                logger.info(verdict.reason)
                return
            if isinstance(verdict, Skip):
                logger.info(f"Skipping {card.name or '(unnamed card)'} — {verdict.reason}.")
                if card.name:
                    handled.add((card.name, card.photo))
                current = self.conversations.advance(current)
                continue

            handled.add((card.name, card.photo))
            if verdict.namesake:
                logger.info(
                    f"{card.name} is in the send history, but this card "
                    + ("may be someone else; checking its conversation."
                       if verdict.namesake == "maybe" else
                       "is a different person with the same name."))
            message = verdict.templates.personalize(display_first_name(card.name))
            if verdict.matched:
                logger.info(f"{card.name}: last message matches '{verdict.matched}' "
                            f"→ using {verdict.source}")

            if s.dry_run:
                first_line = message.splitlines()[0] if message else ""
                logger.info(f"[DRY-RUN] Would send to {card.name} "
                            f"({verdict.source}): {first_line}")
                current = self.conversations.advance(current)
                continue

            # Capture the next card BEFORE sending — sending moves the
            # current card to the top of the list.
            next_card = self.conversations.advance(current)
            next_name = (self.conversations.ensure_name(next_card)
                         if next_card is not None else None)

            if not self._send(current, card, message, verdict.ruled_out):
                return

            if s.max_messages and self.sent >= s.max_messages:
                logger.info(f"Reached --max {s.max_messages}. Stopping.")
                return

            current = self.conversations.refresh(next_card, next_name)
            if current is None and next_card is not None:
                logger.warning(
                    f"Lost track of the next card ({next_name or 'unnamed'}) "
                    f"after the list re-sorted. Stopping instead of "
                    f"re-walking from the top.")
                return

        logger.info(f"Reached the {'top' if s.upward else 'bottom'} "
                    f"of the conversation list.")

    def _send(self, handle, card, message, ruled_out):
        """Send to one card; False when the walk must stop."""
        first = display_first_name(card.name)
        result = self.thread.send(handle, card.name, message, ruled_out)
        if result.status is SendStatus.SENT:
            self.sent += 1
            try:
                self.history.record(card.name, photo=card.photo, thread=result.thread)
            except HistoryUnwritable as e:
                logger.error(f"Message sent to {first or card.name}, but it could not "
                             f"be recorded: {e} Stopping so no one is messaged twice.")
                return False
            logger.info(f"Message sent to {first or card.name} "
                        f"[sent={self.sent}, failed={self.failed}, "
                        f"skipped={self.skipped}]")
            self.pause(*BETWEEN_CONTACTS)
        elif result.status is SendStatus.NOT_REGISTERED:
            self.failed += 1
            logger.warning(f"Message to {card.name} did not register "
                           f"[sent={self.sent}, failed={self.failed}, "
                           f"skipped={self.skipped}]")
            self.pause(*BETWEEN_CONTACTS)
        elif result.status is SendStatus.SKIPPED:
            self.skipped += 1
        else:
            self.failed += 1
        return True
