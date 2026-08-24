"""What the withdraw use case needs from the outside world."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from linkedin_bots.withdrawing.domain.invitation import SentInvitation


@dataclass(frozen=True)
class LoadResult:
    """How a loading pass ended.

    ``exhausted`` is True when it stopped because nothing is left to load,
    False when a cap or a stop condition ended it — which is how a rolling
    run tells "the list ended" from "this batch ended".
    """

    count: int
    exhausted: bool


class StaleListError(Exception):
    """The list re-rendered mid-withdrawal; every element reference died with it."""


class SentInvitationsPage(Protocol):
    """LinkedIn's sent-invitation manager."""

    def open(self) -> None: ...

    def card_count(self) -> int: ...

    def sent_labels(self) -> list[str]: ...

    def loaded_invitations(self) -> list[SentInvitation]: ...

    def load(self, max_pages: Optional[int] = None, max_cards: Optional[int] = None,
             stop_when: Optional[Callable[[list[str]], bool]] = None,
             use_js: bool = True) -> LoadResult: ...

    def withdraw(self, invitation: SentInvitation) -> bool:
        """Withdraw one invitation; True once its card is gone.

        Raises StaleListError when the list re-rendered under it.
        """


class Confirm(Protocol):
    """Ask the person a yes/no question."""

    def __call__(self, question: str) -> bool: ...


class Pause(Protocol):
    """Wait a randomized, human-looking interval between ``low`` and ``high`` seconds."""

    def __call__(self, low: float, high: float) -> None: ...
