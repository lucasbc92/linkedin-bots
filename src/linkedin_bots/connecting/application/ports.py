"""What the invitation use case needs from the outside world."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Protocol


class InviteStatus(Enum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNCONFIRMED = "unconfirmed"   # Send clicked, modal never closed; not counted
    STOP = "stop"


@dataclass(frozen=True)
class InviteResult:
    """How the invite modal ended, and the first name it was sent under."""

    status: InviteStatus
    name: Optional[str] = None


class ClickIntercepted(Exception):
    """Another element took the click meant for a Connect control."""


class SearchResults(Protocol):
    """The people-search results page. Controls are opaque handles."""

    def select_search_tab(self) -> bool: ...
    def await_results(self) -> bool: ...
    def detours_allowed(self) -> bool: ...
    def results_url(self) -> Optional[str]: ...
    def next_target(self, processed_labels: set, include_follow: bool = True) -> tuple: ...
    def page_action_tally(self) -> Optional[dict]: ...
    def reload_results(self) -> bool: ...
    def extract_title_texts(self, control) -> list[str]: ...
    def click_connect(self, control, label: str) -> None:
        """Raises ClickIntercepted when another element takes the click."""
    def profile_url_for(self, control) -> Optional[str]: ...
    def return_to_results(self, results_url: Optional[str]) -> bool: ...
    def go_to_next_page(self) -> bool: ...


class ProfilePage(Protocol):
    def open(self, url: str) -> None: ...
    def open_connect(self, full_name: str) -> bool:
        """Click the Connect control for ``full_name``; False when there is none."""


class InviteModal(Protocol):
    def complete(self, target_label: str, name: Optional[str],
                 note: Optional[Callable[[Optional[str]], str]]) -> InviteResult:
        """Drive the open modal; ``note`` is None to send without a note."""
    def dismiss_open_modal(self) -> None: ...


class LimitGuard(Protocol):
    def check(self) -> bool:
        """False when the weekly limit means the run must stop."""


class InviteLedger(Protocol):
    def record(self, name: str) -> None: ...
    def count_for_week(self, week=None) -> int: ...


class Pause(Protocol):
    def __call__(self, low: float, high: float) -> None: ...
