"""Choosing which invitations to withdraw."""
import unittest
from datetime import date

from linkedin_bots.withdrawing.domain.invitation import SentInvitation, targets_older_than
from linkedin_bots.withdrawing.domain.sent_age import parse_sent_age, parse_until

TODAY = date(2026, 8, 20)


def _card(name, age):
    return SentInvitation(name=name, age=age, key=f"key-{name}")


class TargetsOlderThanTest(unittest.TestCase):
    def setUp(self):
        # List order: newest first, the way LinkedIn renders it.
        self.cards = [
            _card("Camilla", "Sent 1 hour ago"),
            _card("Ana", "Sent 3 days ago"),
            _card("Caroline", "Sent 2 months ago"),
            _card("Anderson", "Sent 5 months ago"),
        ]

    def test_only_cards_past_the_cutoff_are_selected(self):
        picked = targets_older_than(self.cards, date(2026, 7, 1), TODAY)
        self.assertEqual([c.name for c in picked], ["Anderson", "Caroline"])

    def test_result_is_oldest_first(self):
        picked = targets_older_than(self.cards, date(2026, 8, 19), TODAY)
        self.assertEqual([c.name for c in picked],
                         ["Anderson", "Caroline", "Ana"])

    def test_unparsable_cards_are_never_withdrawn(self):
        cards = self.cards + [_card("Mystery", "Pending")]
        picked = targets_older_than(cards, date(2026, 7, 1), TODAY)
        self.assertNotIn("Mystery", [c.name for c in picked])

    def test_nothing_selected_when_all_are_newer(self):
        self.assertEqual(targets_older_than(self.cards, date(2020, 1, 1), TODAY), [])

    def test_rounding_direction_keeps_ambiguous_cards(self):
        # "2 months ago" spans 20 May–20 June; a 1 June cutoff can't prove the
        # card is older, so it stays.
        cards = [_card("Caroline", "Sent 2 months ago")]
        self.assertEqual(targets_older_than(cards, date(2026, 6, 1), TODAY), [])

    def test_a_recent_card_at_the_bottom_does_not_hide_older_ones(self):
        # LinkedIn doesn't always sort the list: here the last card is a week
        # old while month-old ones sit above it. Walking up from the bottom
        # stopped at that card and withdrew nothing.
        cards = [
            _card("Camilla", "Sent 1 hour ago"),
            _card("Caroline", "Sent 2 months ago"),
            _card("Anderson", "Sent 5 months ago"),
            _card("Ana", "Sent 3 days ago"),
            _card("Bruno", "Sent 1 week ago"),
        ]
        picked = targets_older_than(cards, date(2026, 7, 1), TODAY)
        self.assertEqual([c.name for c in picked], ["Anderson", "Caroline"])

    def test_out_of_order_cards_come_back_oldest_first(self):
        cards = [
            _card("Caroline", "Sent 2 months ago"),
            _card("Camilla", "Sent 1 hour ago"),
            _card("Anderson", "Sent 5 months ago"),
            _card("Beatriz", "Sent 1 year ago"),
        ]
        picked = targets_older_than(cards, date(2026, 7, 1), TODAY)
        self.assertEqual([c.name for c in picked],
                         ["Beatriz", "Anderson", "Caroline"])

    def test_same_age_cards_keep_bottom_up_order(self):
        cards = [
            _card("Caroline", "Sent 5 months ago"),
            _card("Camilla", "Sent 1 hour ago"),
            _card("Anderson", "Sent 5 months ago"),
        ]
        picked = targets_older_than(cards, date(2026, 7, 1), TODAY)
        self.assertEqual([c.name for c in picked], ["Anderson", "Caroline"])

    def test_relative_matches_the_card_labels_it_targets(self):
        # The whole point of the shorthand: "--until 2m" must select exactly
        # the cards reading "Sent 2 months ago" and older, with no drift
        # between how a cutoff and a card age are computed.
        cutoff = parse_until("2m", TODAY)
        self.assertEqual(parse_sent_age("Sent 2 months ago", TODAY), cutoff)
        cards = [
            _card("newer", "Sent 1 month ago"),
            _card("boundary", "Sent 2 months ago"),
            _card("older", "Sent 5 months ago"),
        ]
        self.assertEqual([c.name for c in targets_older_than(cards, cutoff, TODAY)],
                         ["older", "boundary"])


class SentInvitationTest(unittest.TestCase):
    def test_is_a_value_object(self):
        self.assertEqual(_card("Ana", "Sent 1 week ago"), _card("Ana", "Sent 1 week ago"))
        with self.assertRaises(AttributeError):
            _card("Ana", "Sent 1 week ago").name = "Bia"
