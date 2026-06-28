"""Names read out of the action labels LinkedIn puts on result cards."""
import re
import unicodedata

from linkedin_bots.shared.domain.names import display_first_name


def full_name_from_label(aria_label):
    """The person's full name out of a card's action label.

    Both shapes a card can offer name the person: 'Invite <Full Name> to
    connect' and 'Follow <Full Name>'.
    """
    if not aria_label:
        return None
    match = re.match(r"Invite\s+(.+?)\s+to connect", aria_label, re.IGNORECASE)
    if match is None:
        match = re.match(r"Follow\s+(.+)", aria_label, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).strip() or None


def first_name_from_label(aria_label):
    """The display first name from a card's Connect or Follow label."""
    full_name = full_name_from_label(aria_label)
    return display_first_name(full_name) if full_name else None


def same_person(one, other):
    """Compare two names ignoring case, whitespace and unicode form.

    "Nájera" can reach us composed from the card and decomposed from the
    profile; the two spell the same name and must compare equal.
    """
    def key(name):
        return unicodedata.normalize("NFC", " ".join((name or "").split())).casefold()

    return key(one) == key(other)
