"""A logging week starts Sunday 21:00 in São Paulo."""
from datetime import date, datetime

from linkedin_bots.shared.domain.weeks import BRT, current_week_start


def test_the_week_turns_at_sunday_2100_brt():
    assert current_week_start(datetime(2026, 7, 19, 20, 59, tzinfo=BRT)) == date(2026, 7, 12)
    assert current_week_start(datetime(2026, 7, 19, 21, 1, tzinfo=BRT)) == date(2026, 7, 19)


def test_midweek_belongs_to_the_previous_sunday():
    assert current_week_start(datetime(2026, 7, 22, 10, tzinfo=BRT)) == date(2026, 7, 19)
