"""A pending invitation, and the rule for which ones to withdraw."""

from dataclasses import dataclass

from linkedin_bots.withdrawing.domain.sent_age import parse_sent_age


@dataclass(frozen=True)
class SentInvitation:
    """One pending invitation as the sent list shows it.

    ``key`` is the withdraw link's ``componentkey`` — unique per invitation,
    unlike the display name, so two people with the same name stay apart.
    """

    name: str
    age: str
    key: str


def targets_older_than(invitations, cutoff, today=None):
    """Every invitation provably sent on or before ``cutoff``, oldest first.

    ``invitations`` come in list order, which is only *roughly*
    newest-first: LinkedIn sometimes lists an hours-old invitation below
    month-old ones, so the whole list is filtered — no position is trusted as
    a boundary — and the result is sorted by age. Invitations of the same
    age keep bottom-up order. Ones whose age can't be parsed are skipped,
    never withdrawn.
    """
    selected = []
    for invitation in reversed(list(invitations)):
        sent = parse_sent_age(invitation.age, today=today)
        if sent is not None and sent <= cutoff:
            selected.append((sent, invitation))
    selected.sort(key=lambda pair: pair[0])
    return [invitation for _, invitation in selected]
