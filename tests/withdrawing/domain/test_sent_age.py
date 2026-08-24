"""Reading LinkedIn's relative "Sent …" ages and the --until cutoff."""
import unittest
from datetime import date

from linkedin_bots.withdrawing.domain.sent_age import (oldest_label, parse_sent_age,
                                                       parse_until, reached_cutoff)

TODAY = date(2026, 8, 20)


class ParseSentAgeEnglishTest(unittest.TestCase):
    def test_minutes_and_hours_are_today(self):
        self.assertEqual(parse_sent_age("Sent 40 minutes ago", TODAY), TODAY)
        self.assertEqual(parse_sent_age("Sent 1 hour ago", TODAY), TODAY)
        self.assertEqual(parse_sent_age("Sent 9 hours ago", TODAY), TODAY)

    def test_hours_past_a_full_day_roll_back(self):
        self.assertEqual(parse_sent_age("Sent 30 hours ago", TODAY),
                         date(2026, 8, 19))

    def test_days(self):
        self.assertEqual(parse_sent_age("Sent 1 day ago", TODAY),
                         date(2026, 8, 19))
        self.assertEqual(parse_sent_age("Sent 6 days ago", TODAY),
                         date(2026, 8, 14))

    def test_weeks(self):
        self.assertEqual(parse_sent_age("Sent 2 weeks ago", TODAY),
                         date(2026, 8, 6))

    def test_months_use_calendar_arithmetic(self):
        self.assertEqual(parse_sent_age("Sent 3 months ago", TODAY),
                         date(2026, 5, 20))
        self.assertEqual(parse_sent_age("Sent 1 month ago", TODAY),
                         date(2026, 7, 20))

    def test_months_clamp_to_short_months(self):
        # 31 March minus one month has no 31 February to land on.
        self.assertEqual(parse_sent_age("Sent 1 month ago", date(2026, 3, 31)),
                         date(2026, 2, 28))

    def test_years(self):
        self.assertEqual(parse_sent_age("Sent 1 year ago", TODAY),
                         date(2025, 8, 20))
        self.assertEqual(parse_sent_age("Sent 2 years ago", TODAY),
                         date(2024, 8, 20))

    def test_implicit_one(self):
        self.assertEqual(parse_sent_age("Sent a month ago", TODAY),
                         date(2026, 7, 20))

    def test_today_and_yesterday(self):
        self.assertEqual(parse_sent_age("Sent today", TODAY), TODAY)
        self.assertEqual(parse_sent_age("Sent yesterday", TODAY),
                         date(2026, 8, 19))


class ParseSentAgePortugueseTest(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(parse_sent_age("Enviado há 9 horas", TODAY), TODAY)

    def test_days(self):
        self.assertEqual(parse_sent_age("Enviado há 3 dias", TODAY),
                         date(2026, 8, 17))

    def test_weeks(self):
        self.assertEqual(parse_sent_age("Enviado há 2 semanas", TODAY),
                         date(2026, 8, 6))

    def test_months_singular_and_plural(self):
        self.assertEqual(parse_sent_age("Enviado há 1 mês", TODAY),
                         date(2026, 7, 20))
        self.assertEqual(parse_sent_age("Enviado há 3 meses", TODAY),
                         date(2026, 5, 20))

    def test_years(self):
        self.assertEqual(parse_sent_age("Enviado há 1 ano", TODAY),
                         date(2025, 8, 20))

    def test_yesterday(self):
        self.assertEqual(parse_sent_age("Enviado ontem", TODAY),
                         date(2026, 8, 19))


class ParseSentAgeUnknownTest(unittest.TestCase):
    def test_unparsable_returns_none(self):
        for raw in ("", None, "Pending", "Sent", "Sent a while back"):
            self.assertIsNone(parse_sent_age(raw, TODAY), raw)


class ReachedCutoffTest(unittest.TestCase):
    def test_false_while_everything_is_newer(self):
        labels = ["Sent 1 hour ago", "Sent 3 days ago", "Sent 2 weeks ago"]
        self.assertFalse(reached_cutoff(labels, date(2026, 6, 1), TODAY))

    def test_true_once_the_oldest_passes_the_cutoff(self):
        labels = ["Sent 1 hour ago", "Sent 3 days ago", "Sent 3 months ago"]
        self.assertTrue(reached_cutoff(labels, date(2026, 6, 1), TODAY))

    def test_boundary_is_inclusive(self):
        self.assertTrue(reached_cutoff(["Sent 1 month ago"],
                                       date(2026, 7, 20), TODAY))

    def test_unparsable_tail_falls_back_to_the_last_readable_label(self):
        labels = ["Sent 1 hour ago", "Sent 4 months ago", "Pending"]
        self.assertTrue(reached_cutoff(labels, date(2026, 6, 1), TODAY))

    def test_empty_list(self):
        self.assertFalse(reached_cutoff([], date(2026, 6, 1), TODAY))


class ParseUntilTest(unittest.TestCase):
    """--until accepts an absolute date or a relative age."""

    def test_absolute_slash_and_dash(self):
        self.assertEqual(parse_until("2026/06/20", TODAY), date(2026, 6, 20))
        self.assertEqual(parse_until("2026-06-20", TODAY), date(2026, 6, 20))

    def test_relative_shorthand(self):
        self.assertEqual(parse_until("2m", TODAY), date(2026, 6, 20))
        self.assertEqual(parse_until("3w", TODAY), date(2026, 7, 30))
        self.assertEqual(parse_until("10d", TODAY), date(2026, 8, 10))
        self.assertEqual(parse_until("1y", TODAY), date(2025, 8, 20))

    def test_relative_spelled_out(self):
        self.assertEqual(parse_until("2 months", TODAY), date(2026, 6, 20))
        self.assertEqual(parse_until("2 meses", TODAY), date(2026, 6, 20))

    def test_case_and_spacing_are_forgiven(self):
        self.assertEqual(parse_until("  2M  ", TODAY), date(2026, 6, 20))

    def test_rejects_nonsense(self):
        for value in ("", None, "soon", "2026", "20/06/2026", "5x", "tomorrow"):
            with self.assertRaises(ValueError, msg=value):
                parse_until(value, TODAY)

    def test_rejects_impossible_dates(self):
        with self.assertRaises(ValueError):
            parse_until("2026/02/31", TODAY)


class OldestLabelTest(unittest.TestCase):
    def test_picked_by_age_not_position(self):
        labels = ["Sent 1 hour ago", "Sent 5 months ago", "Sent 3 days ago"]
        self.assertEqual(oldest_label(labels, TODAY), "Sent 5 months ago")

    def test_unreadable_ages_fall_back_to_the_last_sent_line(self):
        self.assertEqual(oldest_label(["Sent soon", "Sent later"], TODAY), "Sent later")

    def test_lines_that_are_not_ages_are_ignored(self):
        self.assertEqual(oldest_label(["Pending", "Sent 2 weeks ago"], TODAY),
                         "Sent 2 weeks ago")

    def test_nothing_loaded(self):
        self.assertIsNone(oldest_label([], TODAY))
