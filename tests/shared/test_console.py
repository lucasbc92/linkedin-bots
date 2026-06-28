"""Yes/no questions on the terminal."""
import pytest

from linkedin_bots.shared.infrastructure.console import ask_yes_no


@pytest.mark.parametrize("answer", ["y", "yes", "s", "sim", "  Sim \n", "YES"])
def test_english_and_portuguese_yes(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda question: answer)
    assert ask_yes_no("Continue? ") is True


@pytest.mark.parametrize("answer", ["", "n", "no", "não", "maybe"])
def test_anything_else_is_no(monkeypatch, answer):
    monkeypatch.setattr("builtins.input", lambda question: answer)
    assert ask_yes_no("Continue? ") is False
