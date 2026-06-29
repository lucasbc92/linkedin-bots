"""Past sends, and telling apart two people who share a name."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class PastSend:
    """One message sent in an earlier run to someone with a given name.

    ``photo`` is the asset ID in the contact's photo URL and ``thread`` the
    conversation ID; sends recorded before those existed carry neither.
    """

    sent_at: datetime
    photo: Optional[str] = None
    thread: Optional[str] = None


def homonym_check(sends, photo, card_date):
    """Decide whether a card whose name is already in the history is someone
    new who just shares the name.

    Returns None when the card may be a person already messaged (skip it);
    otherwise the set of recorded thread IDs the card's conversation must not
    be — empty when nothing is left to check once it is opened.

    - A recorded photo that matches is the same person.
    - A name-only (older) send can only be ruled out by date: a card whose
      last activity is newer than every such send was not that conversation.
    - Sends with a thread ID are ruled out by opening the conversation.
    """
    if photo and any(s.photo == photo for s in sends):
        return None

    name_only = [s for s in sends if not s.thread]
    if name_only:
        latest = max(s.sent_at.date() for s in name_only)
        if card_date is None or card_date <= latest:
            return None

    return frozenset(s.thread for s in sends if s.thread)
