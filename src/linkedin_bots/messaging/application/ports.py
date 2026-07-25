"""What the follow-up use case needs from the outside world."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

from linkedin_bots.messaging.domain.past_sends import PastSend
from linkedin_bots.messaging.domain.walk import ConversationCard


class SendStatus(Enum):
    SENT = "sent"
    NOT_REGISTERED = "not registered"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class SendResult:
    """How one send attempt ended, and the conversation it happened in."""

    status: SendStatus
    thread: Optional[str] = None


class HistoryUnreadable(Exception):
    """The send history exists but cannot be read; treating it as empty
    would re-message everyone in it."""


class HistoryUnwritable(Exception):
    """A send could not be recorded; carrying on would message someone who
    will look new on the next run."""


class ConversationList(Protocol):
    """LinkedIn's conversation list. Cards are opaque handles to the use case."""

    def open(self) -> bool: ...

    def scroll_to_start_date(self, target) -> bool: ...

    def start(self) -> tuple[Optional[object], bool]:
        """The first card to walk, and whether it is the clicked conversation."""

    def read(self, card) -> ConversationCard: ...

    def ensure_name(self, card) -> Optional[str]: ...

    def advance(self, card) -> Optional[object]: ...

    def refresh(self, card, name) -> Optional[object]: ...


class Thread(Protocol):
    """A conversation: open it from its card and send one message."""

    def send(self, card, name: str, message: str,
             ruled_out: frozenset = frozenset()) -> SendResult: ...


class SentHistory(Protocol):
    """Everyone messaged in earlier runs."""

    def load(self) -> dict[str, list[PastSend]]: ...

    def record(self, name: str, photo: Optional[str] = None,
               thread: Optional[str] = None) -> None:
        """Record one send; raises HistoryUnwritable when it cannot be saved."""


class Pause(Protocol):
    def __call__(self, low: float, high: float) -> None: ...
