"""What happens to one conversation card on the walk down (or up) the list."""
from dataclasses import dataclass
from typing import Optional

from linkedin_bots.messaging.domain.card_date import parse_card_timestamp
from linkedin_bots.messaging.domain.past_sends import homonym_check


@dataclass(frozen=True)
class ConversationCard:
    """What a conversation card shows, read once from the page."""

    name: Optional[str]
    stamp: Optional[str]
    photo: Optional[str] = None
    pill: Optional[str] = None
    last_message: Optional[str] = None

    def date(self, today=None):
        return parse_card_timestamp(self.stamp, today=today) if self.stamp else None


@dataclass(frozen=True)
class Stop:
    """The walk ends here (the date limit was crossed)."""

    reason: str


@dataclass(frozen=True)
class Skip:
    """Walk past this card without messaging it."""

    reason: str


@dataclass(frozen=True)
class Send:
    """Message this card with ``templates``.

    ``ruled_out`` holds thread IDs the opened conversation must not be.
    ``namesake`` is None, or "maybe" / "different" when the name is already
    in the history but this card is (probably) someone else.
    """

    templates: object
    source: str
    matched: Optional[str]
    ruled_out: frozenset
    namesake: Optional[str]


def assess(card, *, history, handled, routing, date_limit=None, upward=False, today=None):
    """The verdict for one card, in the order the walk has always checked."""
    name = card.name
    card_date = card.date(today)
    if date_limit and card_date:
        if upward and card_date > date_limit:
            return Stop(f"Card for {name or '(unknown)'} dated {card_date} "
                        f"is after date limit {date_limit}. Stopping (reverse).")
        if not upward and card_date < date_limit:
            return Stop(f"Card for {name or '(unknown)'} dated {card_date} "
                        f"is before date limit {date_limit}. Stopping.")

    if not name:
        return Skip("card has no readable name")

    ruled_out = frozenset()
    if name in history:
        ruled_out = homonym_check(history[name], card.photo, card_date)

    if card.pill:
        return Skip(card.pill)
    if (name, card.photo) in handled:
        return Skip("already handled in this run")
    if ruled_out is None:
        return Skip("already messaged in a previous run")

    templates, source, matched = routing.choose(card.last_message)
    if templates is None:
        patterns = ", ".join(f"'{p}'" for p in routing.patterns())
        return Skip(f"last message matches no regex ({patterns})")

    namesake = None
    if name in history:
        namesake = "maybe" if ruled_out else "different"
    return Send(templates, source, matched, frozenset(ruled_out), namesake)
