"""The linkedin-bots command."""
import logging
import os
import subprocess
import sys

import pytest

from linkedin_bots import cli
from linkedin_bots.cli._common import TemplateCompleter, require_template, start_logging
from linkedin_bots.shared.infrastructure.templates import template_dir


def test_cli_runs_from_any_folder(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "linkedin_bots", "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "linkedin-bots" in result.stdout
    for command in ("connect", "message", "withdraw", "stats"):
        assert command in result.stdout


@pytest.mark.parametrize("command", ["connect", "message", "withdraw", "stats"])
def test_help_survives_output_redirected_on_a_cp1252_system(tmp_path, command):
    """Redirected output on most Windows machines is cp1252, which has no '→'."""
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    result = subprocess.run(
        [sys.executable, "-m", "linkedin_bots", command, "--help"],
        cwd=tmp_path, capture_output=True, env=env, timeout=60)
    assert result.returncode == 0, result.stderr.decode("cp1252", "replace")


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


def test_completion_offers_the_users_own_templates_too(isolated_data_home):
    folder = isolated_data_home / "messaging" / "templates"
    folder.mkdir(parents=True)
    (folder / "mine.txt").write_text("Hi {name}!", encoding="utf-8")
    (folder / "message.txt").write_text("Hi {name}, it's me.", encoding="utf-8")
    offered = TemplateCompleter("messaging")(prefix="m")
    assert "mine.txt" in offered and "message_english.txt" in offered
    assert offered.count("message.txt") == 1


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


@pytest.mark.parametrize("argv,template", [
    (["connect"], "message.txt"),
    (["connect", "--java-devs"], "dev_message.txt"),
    (["connect", "--java-devs", "-m", "dev_message_english.txt"], "dev_message_english.txt"),
])
def test_java_devs_pick_their_own_default_template(monkeypatch, argv, template):
    from linkedin_bots.cli import connect

    asked = []

    def stop_at_the_template(name, *args):
        asked.append(name)
        raise SystemExit(0)

    monkeypatch.setattr(connect, "require_template", stop_at_the_template)
    with pytest.raises(SystemExit):
        cli.main(argv)
    assert asked == [template]


def test_message_walks_in_reverse_with_the_same_flag_as_connect():
    parser = cli.build_parser()
    assert not parser.parse_args(["message"]).reverse
    assert parser.parse_args(["message", "-r"]).reverse
    assert parser.parse_args(["message", "--reverse"]).reverse
    assert parser.parse_args(["connect", "-r"]).reverse


def _write(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


def test_by_title_reaches_the_parser():
    parser = cli.build_parser()
    assert parser.parse_args(["message"]).by_title is False
    assert parser.parse_args(["message", "--by-title"]).by_title is True


def test_a_family_takes_each_sibling_from_the_data_home_first(isolated_data_home):
    from linkedin_bots.cli.message import load_family

    folder = isolated_data_home / "messaging" / "templates"
    _write(folder, "message.txt", "Mine {name}")
    _write(folder, "dev_message.txt", "My dev {name}")
    logger = logging.getLogger("linkedin_bot")
    base = require_template("message.txt", "messaging", "-m/--message", logger)
    family = load_family("message.txt", base, logger)
    assert family.recruiter.templates.personalize("Ana") == "Mine Ana"
    assert family.dev.templates.personalize("Ana") == "My dev Ana"
    assert family.generic.source == "generic_message.txt"
    assert family.generic.templates.personalize("Ana").startswith("Olá, Ana, tudo bem?")


def test_a_missing_sibling_falls_back_to_the_base_and_warns(caplog):
    from linkedin_bots.cli.message import load_family

    logger = logging.getLogger("linkedin_bot")
    family = load_family("reconnect.txt", template_dir("messaging") / "reconnect.txt", logger)
    assert family.dev.source == "dev_reconnect.txt"
    assert family.generic.source == "reconnect.txt"
    assert "generic_reconnect.txt not found; generic contacts get reconnect.txt" in caplog.text


def test_a_base_given_as_a_path_finds_its_siblings_next_to_it(tmp_path):
    from linkedin_bots.cli.message import load_family

    _write(tmp_path, "x.txt", "X {name}")
    _write(tmp_path, "dev_x.txt", "Dev X {name}")
    family = load_family(str(tmp_path / "x.txt"), tmp_path / "x.txt",
                         logging.getLogger("linkedin_bot"))
    assert family.dev.source == "dev_x.txt"
    assert family.generic.source == "x.txt"


def test_by_title_hands_the_walk_template_families(monkeypatch):
    import linkedin_bots.messaging.application.send_follow_ups as use_case_module
    import linkedin_bots.shared.infrastructure.browser as browser
    import linkedin_bots.shared.infrastructure.sleep as sleep
    from linkedin_bots.messaging.domain.headline_audience import TemplateFamily

    monkeypatch.setattr(browser, "create_driver", lambda attach_to_existing: (None, False))
    monkeypatch.setattr(sleep, "prevent_sleep", lambda: None)
    monkeypatch.setattr(sleep, "allow_sleep", lambda: None)
    seen = {}

    class FakeUseCase:
        def __init__(self, conversations, thread, history, pause, routing, settings):
            seen.update(routing=routing, settings=settings)

        def run(self):
            pass

    monkeypatch.setattr(use_case_module, "SendFollowUps", FakeUseCase)
    cli.main(["message", "--by-title", "--last-message-regex-custom", "for 7", "message_english.txt"])
    assert seen["settings"].by_title is True
    assert isinstance(seen["routing"].default, TemplateFamily)
    assert seen["routing"].rules[0].templates.dev.source == "dev_message_english.txt"
