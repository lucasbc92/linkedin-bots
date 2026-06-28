"""Humanizing pauses."""
from linkedin_bots.shared.infrastructure.pacing import (FAST_PAUSE_FACTOR, MIN_FAST_PAUSE,
                                                        HumanPause)


def test_a_normal_pause_stays_in_its_window():
    pause = HumanPause()
    assert all(8 <= pause.seconds(8, 18) <= 18 for _ in range(200))


def test_fast_shrinks_the_window_but_keeps_a_floor():
    pause = HumanPause(fast=True)
    for _ in range(200):
        assert MIN_FAST_PAUSE <= pause.seconds(8, 18) <= 18 * FAST_PAUSE_FACTOR
        assert pause.seconds(2, 5) == MIN_FAST_PAUSE


def test_calling_it_sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr("linkedin_bots.shared.infrastructure.pacing.time.sleep", slept.append)
    HumanPause()(1, 1)
    assert slept == [1]
