"""Decisions about a page of search results."""
from linkedin_bots.connecting.domain.tech_recruiter import score_title


def best_title(titles, score=score_title):
    """The best verdict among a card's headline and snippet, tech-recruiter by default."""
    if not titles:
        return None
    return max((score(text) for text in titles), key=lambda verdict: verdict.score)


def looks_stripped(tally):
    """A full page of results where not one card offers Connect.

    That is what LinkedIn starts serving after a burst of invitations, and a
    reload usually brings the controls back.
    """
    return bool(tally and tally.get("cards") and not tally.get("connect"))
