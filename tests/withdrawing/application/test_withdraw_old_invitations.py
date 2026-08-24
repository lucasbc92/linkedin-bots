"""The withdraw use case, against an in-memory sent list."""
import logging

import pytest

from linkedin_bots.withdrawing.application.ports import LoadResult
from linkedin_bots.withdrawing.application.withdraw_old_invitations import (
    WithdrawOldInvitations, WithdrawSettings)
from linkedin_bots.withdrawing.domain.invitation import SentInvitation
from linkedin_bots.withdrawing.domain.sent_age import parse_until

OLD = "Sent 2 months ago"
RECENT = "Sent 3 days ago"


class FakeSentPage:
    """Shows a window of the list, grows it on load, drops withdrawn cards."""

    def __init__(self, ages, loaded=None, page=2, fails=(), stuck=False,
                 interrupt_after=None):
        self.invitations = [SentInvitation(f"P{i}", age, f"k{i}")
                            for i, age in enumerate(ages)]
        self.window = len(ages) if loaded is None else loaded
        self.page = page
        self.fails = set(fails)
        self.stuck = stuck
        self.interrupt_after = interrupt_after
        self.loads = []
        self.attempts = []

    def visible(self):
        return self.invitations[:self.window]

    def open(self):
        pass

    def card_count(self):
        return len(self.visible())

    def sent_labels(self):
        return [i.age for i in self.visible()]

    def loaded_invitations(self):
        return list(self.visible())

    def load(self, max_pages=None, max_cards=None, stop_when=None, use_js=True):
        self.loads.append({"max_pages": max_pages, "max_cards": max_cards,
                           "stop_when": stop_when, "use_js": use_js})
        assert len(self.loads) < 50, "kept loading forever"
        if not self.stuck:
            self.window = min(self.window + self.page, len(self.invitations))
        exhausted = not self.stuck and self.window >= len(self.invitations)
        return LoadResult(len(self.visible()), exhausted=exhausted)

    def withdraw(self, invitation):
        if self.interrupt_after is not None and len(self.attempts) == self.interrupt_after:
            raise KeyboardInterrupt
        self.attempts.append(invitation.key)
        if invitation.key in self.fails:
            return False
        self.invitations = [i for i in self.invitations if i.key != invitation.key]
        self.window = max(0, self.window - 1)
        return True


def _use_case(page, confirm=lambda question: True, **settings):
    pauses = []
    settings.setdefault("until", parse_until("1m"))
    settings.setdefault("auto_continue", True)
    use_case = WithdrawOldInvitations(
        page, confirm, lambda low, high: pauses.append((low, high)),
        WithdrawSettings(**settings))
    use_case.pauses = pauses
    return use_case


class TestExpandedRun:
    """Default run: load the whole list, then withdraw what is old."""

    def test_a_recent_card_at_the_bottom_does_not_stop_the_run(self):
        page = FakeSentPage([RECENT, OLD, OLD, RECENT])
        use_case = _use_case(page)
        use_case.run()
        assert sorted(page.attempts) == ["k1", "k2"]
        assert use_case.withdrawn == 2

    def test_old_cards_between_recent_ones_are_withdrawn_oldest_first(self):
        page = FakeSentPage([OLD, RECENT, "Sent 5 months ago", "Sent 3 hours ago",
                             OLD, RECENT])
        _use_case(page).run()
        assert page.attempts == ["k2", "k4", "k0"]

    def test_nothing_past_the_cutoff_withdraws_nothing(self):
        page = FakeSentPage([RECENT, "Sent 3 hours ago"])
        _use_case(page).run()
        assert page.attempts == []

    def test_full_expansion_has_no_stop_condition(self):
        page = FakeSentPage([OLD])
        _use_case(page).run()
        assert page.loads[0]["stop_when"] is None

    def test_stop_early_stops_once_the_cutoff_is_in_view(self):
        page = FakeSentPage([OLD])
        _use_case(page, until=parse_until("2m"), stop_early=True).run()
        stop = page.loads[0]["stop_when"]
        assert not stop(["Sent 1 hour ago", "Sent 3 weeks ago"])
        assert stop(["Sent 1 hour ago", "Sent 5 months ago"])
        assert not stop(["Pending", "Pending"])

    def test_declining_the_prompt_withdraws_nothing(self):
        page = FakeSentPage([OLD, OLD])
        _use_case(page, confirm=lambda question: False, auto_continue=False).run()
        assert page.attempts == []

    def test_a_dry_run_clicks_nothing_and_previews_everything(self):
        page = FakeSentPage([OLD, OLD])
        use_case = _use_case(page, dry_run=True, auto_continue=False)
        use_case.run()
        assert page.attempts == []
        assert use_case.previewed == 2
        assert use_case.pauses == []

    def test_paces_between_real_withdrawals(self):
        page = FakeSentPage([OLD, OLD])
        use_case = _use_case(page)
        use_case.run()
        assert use_case.pauses == [(1.5, 3.0), (1.5, 3.0)]


class TestRollingRun:
    """--rolling: withdraw what is loaded, load two more pages, repeat."""

    def test_drains_the_list_down_to_the_oldest(self):
        page = FakeSentPage([OLD] * 10, loaded=3)
        use_case = _use_case(page, rolling=True)
        use_case.run()
        assert use_case.withdrawn == 10
        assert page.invitations == []

    def test_loads_more_than_one_batch(self):
        page = FakeSentPage([OLD] * 10, loaded=3, page=2)
        _use_case(page, rolling=True).run()
        assert len(page.loads) > 1

    def test_invitations_inside_the_cutoff_are_left_alone(self):
        page = FakeSentPage([RECENT] * 3 + [OLD] * 4, loaded=3)
        use_case = _use_case(page, rolling=True)
        use_case.run()
        assert use_case.withdrawn == 4
        assert [i.age for i in page.invitations] == [RECENT] * 3

    def test_unreadable_ages_are_never_withdrawn(self):
        page = FakeSentPage([OLD, "Pending", OLD], loaded=3)
        use_case = _use_case(page, rolling=True)
        use_case.run()
        assert use_case.withdrawn == 2
        assert [i.age for i in page.invitations] == ["Pending"]

    def test_a_failed_withdrawal_is_tried_once_and_then_skipped(self):
        page = FakeSentPage([OLD] * 4, loaded=3, fails={"k1"})
        use_case = _use_case(page, rolling=True)
        use_case.run()
        assert page.attempts.count("k1") == 1
        assert (use_case.failed, use_case.withdrawn) == (1, 3)

    def test_a_list_that_stops_loading_ends_the_run(self):
        page = FakeSentPage([RECENT] * 3 + [OLD] * 5, loaded=3, stuck=True)
        use_case = _use_case(page, rolling=True)
        use_case.run()
        assert use_case.withdrawn == 0

    def test_tops_up_by_two_pages_unless_max_pages_says_otherwise(self):
        page = FakeSentPage([OLD] * 6, loaded=2)
        _use_case(page, rolling=True).run()
        assert page.loads[0]["max_pages"] == 2
        page = FakeSentPage([OLD] * 6, loaded=2)
        _use_case(page, rolling=True, max_pages=5).run()
        assert page.loads[0]["max_pages"] == 5


def test_ctrl_c_still_reports_the_tally(caplog):
    caplog.set_level(logging.INFO, logger="linkedin_bot")
    page = FakeSentPage([OLD, OLD, OLD], interrupt_after=1)
    with pytest.raises(KeyboardInterrupt):
        _use_case(page).run()
    assert "Withdrawn: 1" in caplog.text
