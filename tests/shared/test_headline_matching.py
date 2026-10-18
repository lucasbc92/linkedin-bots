"""Headline matching, shared by every bot that reads a LinkedIn headline."""
from linkedin_bots.shared.domain.headline_matching import (RECRUITER_TERMS, _matches_in_segment,
                                                           normalize, split_segments)


def test_normalize_strips_accents_case_and_punctuation():
    assert normalize("Engenheira de Software – Front-End") == "engenheira de software front end"


def test_segments_split_on_bullets_not_on_spaced_hyphens():
    assert split_segments("Tech Recruiter | Hiring • TI") == ["tech recruiter", "hiring", "ti"]


def test_recruiter_terms_match_fuzzily_within_a_segment():
    assert _matches_in_segment("recrutadora de ti".split(), RECRUITER_TERMS)
