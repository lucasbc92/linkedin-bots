"""The linkedin-bots command."""
import logging
import subprocess
import sys

import pytest

from linkedin_bots import cli
from linkedin_bots.cli._common import require_template, start_logging
from linkedin_bots.shared.infrastructure.templates import template_dir


def test_cli_runs_from_any_folder(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "linkedin_bots", "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "linkedin-bots" in result.stdout
    for command in ("connect", "message", "withdraw", "stats"):
        assert command in result.stdout


def test_message_pairs_are_collected_repeatably():
    parser = cli.build_parser()
    assert parser.parse_args(["message"]).last_message_regex_custom == []

    args = parser.parse_args([
        "message",
        "--last-message-regex", ".*há 7.*",
        "--last-message-regex-custom", ".*for 7.*", "message_english.txt",
        "--last-message-regex-custom", ".*hace 7.*", "message_es.txt",
    ])
    assert args.last_message_regex == ".*há 7.*"
    assert args.last_message_regex_custom == [
        [".*for 7.*", "message_english.txt"],
        [".*hace 7.*", "message_es.txt"],
    ]


def test_every_command_defaults_to_info():
    parser = cli.build_parser()
    for command in ("connect", "message", "withdraw"):
        assert parser.parse_args([command]).log_level == "INFO"


def test_a_missing_template_exits_with_an_error(caplog):
    logger = logging.getLogger("linkedin_bot")
    with pytest.raises(SystemExit) as stopped:
        require_template("nope.txt", "messaging", "-m/--message", logger)
    assert stopped.value.code == 1
    assert "nope.txt" in caplog.text
    assert require_template("message_english.txt", "messaging", "-m/--message",
                            logger) == template_dir("messaging") / "message_english.txt"


def test_missing_template_stops_before_the_browser(monkeypatch):
    import linkedin_bots.shared.infrastructure.browser as browser

    def no_browser(*args, **kwargs):
        raise AssertionError("the browser must not be touched")

    monkeypatch.setattr(browser, "create_driver", no_browser)
    with pytest.raises(SystemExit) as stopped:
        cli.main(["connect", "-m", "nope.txt"])
    assert stopped.value.code == 1


def test_runs_log_their_log_file(isolated_data_home):
    logger, path = start_logging("withdrawing", "INFO")
    try:
        assert path.parent == isolated_data_home / "withdrawing" / "logs"
        assert path.name.startswith("week-")
        assert f"Log file: {path}" in path.read_text(encoding="utf-8")
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def test_an_empty_template_name_exits_instead_of_sending_the_fallback(caplog):
    """``-m ""`` resolves to the templates folder itself, which exists."""
    with pytest.raises(SystemExit) as stopped:
        require_template("", "messaging", "-m/--message", logging.getLogger("linkedin_bot"))
    assert stopped.value.code == 1


def test_a_relative_data_home_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.setenv("LINKEDIN_BOTS_HOME", "lb-data")
    with pytest.raises(SystemExit) as stopped:
        cli.main(["stats"])
    assert stopped.value.code == 2
    assert "LINKEDIN_BOTS_HOME" in capsys.readouterr().err


def test_withdraw_keeps_the_pc_awake_and_restores_it(monkeypatch):
    import linkedin_bots.shared.infrastructure.browser as browser
    import linkedin_bots.shared.infrastructure.sleep as sleep
    import linkedin_bots.withdrawing.adapters.selenium.sent_invitations_page as page_module

    calls = []
    monkeypatch.setattr(browser, "create_driver", lambda attach_to_existing: (None, False))
    monkeypatch.setattr(sleep, "prevent_sleep", lambda: calls.append("prevent"))
    monkeypatch.setattr(sleep, "allow_sleep", lambda: calls.append("allow"))

    class FakePage:
        def __init__(self, driver):
            pass

        def probe(self):
            calls.append("probe")
            raise KeyboardInterrupt

    monkeypatch.setattr(page_module, "SeleniumSentInvitationsPage", FakePage)
    cli.main(["withdraw", "--probe"])
    assert calls == ["prevent", "probe", "allow"]


def test_the_fast_flag_reaches_the_parser():
    parser = cli.build_parser()
    assert not parser.parse_args(["connect"]).fast
    assert parser.parse_args(["connect", "-f"]).fast
    assert parser.parse_args(["connect", "--fast"]).fast


def test_connect_keeps_the_pc_awake_and_restores_it(monkeypatch):
    import linkedin_bots.connecting.adapters.selenium.limit_guard as guard_module
    import linkedin_bots.connecting.adapters.selenium.search_results_page as results_module
    import linkedin_bots.shared.infrastructure.browser as browser
    import linkedin_bots.shared.infrastructure.sleep as sleep

    calls = []
    monkeypatch.setattr(browser, "create_driver", lambda attach_to_existing: (None, False))
    monkeypatch.setattr(sleep, "prevent_sleep", lambda: calls.append("prevent"))
    monkeypatch.setattr(sleep, "allow_sleep", lambda: calls.append("allow"))
    monkeypatch.setattr(guard_module.SeleniumLimitGuard, "check", lambda self: True)
    monkeypatch.setattr(results_module.SeleniumSearchResults, "select_search_tab",
                        lambda self: calls.append("walk") or True)
    monkeypatch.setattr(results_module.SeleniumSearchResults, "await_results", lambda self: False)
    cli.main(["connect", "--max", "1"])
    assert calls == ["prevent", "walk", "allow"]


def test_help_points_at_files_that_exist():
    import re
    from pathlib import Path

    import linkedin_bots
    from linkedin_bots.cli import connect

    src = Path(linkedin_bots.__file__).resolve().parents[1]
    named = re.findall(r"\blinkedin_bots/[\w/]+\.py\b", connect.EPILOG)
    assert named
    for path in named:
        assert (src / path).is_file(), path
