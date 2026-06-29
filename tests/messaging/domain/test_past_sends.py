"""Telling same-name contacts apart."""
import unittest
from datetime import date, datetime

from linkedin_bots.messaging.domain.past_sends import PastSend, homonym_check

LEGACY = PastSend(sent_at=datetime(2026, 7, 25, 3, 18, 19))
RECORDED = PastSend(sent_at=datetime(2026, 10, 10, 23, 30), photo="PHOTO-A", thread="2-a")


class HomonymCheckTest(unittest.TestCase):
    """``None`` means skip as already messaged; a set means send, unless the
    opened conversation is one of those threads."""

    def test_same_photo_is_the_same_person(self):
        self.assertIsNone(homonym_check([RECORDED], "PHOTO-A", date(2026, 10, 12)))

    def test_newer_card_than_a_name_only_send_is_someone_else(self):
        """Beatriz: invited Oct 5, the namesake was messaged Jul 25."""
        self.assertEqual(homonym_check([LEGACY], "PHOTO-B", date(2026, 10, 5)),
                         set())

    def test_card_no_newer_than_a_name_only_send_may_be_that_person(self):
        self.assertIsNone(homonym_check([LEGACY], "PHOTO-B", date(2026, 7, 25)))
        self.assertIsNone(homonym_check([LEGACY], None, date(2026, 7, 1)))

    def test_undated_card_with_a_name_only_send_is_skipped(self):
        self.assertIsNone(homonym_check([LEGACY], "PHOTO-B", None))

    def test_different_photo_defers_to_the_thread(self):
        self.assertEqual(homonym_check([RECORDED], "PHOTO-B", None), {"2-a"})
        self.assertEqual(homonym_check([RECORDED], None, None), {"2-a"})

    def test_both_kinds_of_send_must_rule_the_card_out(self):
        self.assertIsNone(
            homonym_check([LEGACY, RECORDED], "PHOTO-B", date(2026, 7, 20)))
        self.assertEqual(
            homonym_check([LEGACY, RECORDED], "PHOTO-B", date(2026, 10, 12)),
            {"2-a"})
