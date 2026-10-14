"""Decisions about a page of results."""
from linkedin_bots.connecting.domain import java_dev
from linkedin_bots.connecting.domain.page_rules import best_title, looks_stripped


def test_the_better_of_headline_and_snippet_wins():
    verdict = best_title(["Recrutadora", "Current: Tech Recruiter at Acme"])
    assert verdict.score == 1.0


def test_the_scorer_can_be_swapped():
    verdict = best_title(["Tech Recruiter", "Desenvolvedor Java Sênior"], java_dev.score_title)
    assert verdict.title == "Desenvolvedor Java Sênior"


def test_no_titles_means_no_verdict():
    assert best_title([]) is None


def test_a_page_of_cards_with_no_connect_looks_stripped():
    assert looks_stripped({"cards": 10, "connect": 0, "follow": 7})
    assert not looks_stripped({"cards": 10, "connect": 2})
    assert not looks_stripped({"cards": 0, "connect": 0})
    assert not looks_stripped(None)
