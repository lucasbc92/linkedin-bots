"""Reading the date on a conversation card."""
from datetime import date

from linkedin_bots.messaging.domain.card_date import (first_card_on_or_before,
                                                      parse_card_timestamp)

TODAY = date(2026, 10, 11)  # a Sunday


def test_a_time_is_today():
    assert parse_card_timestamp("10:01 PM", TODAY) == TODAY
    assert parse_card_timestamp("9:12 AM", TODAY) == TODAY


def test_a_weekday_is_the_last_one_before_today():
    assert parse_card_timestamp("Fri", TODAY) == date(2026, 10, 9)
    assert parse_card_timestamp("Sun", TODAY) == date(2026, 10, 4)


def test_month_and_day_never_land_in_the_future():
    assert parse_card_timestamp("Oct 5", TODAY) == date(2026, 10, 5)
    assert parse_card_timestamp("Dec 24", TODAY) == date(2025, 12, 24)


def test_explicit_years():
    assert parse_card_timestamp("Jun 27, 2024", TODAY) == date(2024, 6, 27)
    assert parse_card_timestamp("Mar 2024", TODAY) == date(2024, 3, 1)


def test_anything_else_is_unknown():
    assert parse_card_timestamp("yesterday-ish", TODAY) is None


def test_first_card_on_or_before_skips_newer_and_unknown_ones():
    stamps = [(0, "10:01 PM"), (1, "garbage"), (2, "Oct 5"), (3, "Sep 1")]
    assert first_card_on_or_before(stamps, date(2026, 10, 6), TODAY) == 2
    assert first_card_on_or_before(stamps, date(2020, 1, 1), TODAY) is None
