"""The linkedin-bots command."""
import subprocess
import sys

import pytest

from linkedin_bots import cli
from linkedin_bots.cli._common import start_logging


def test_cli_runs_from_any_folder(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "linkedin_bots", "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "linkedin-bots" in result.stdout
    for command in ("connect",):
        assert command in result.stdout


def test_every_command_defaults_to_info():
    parser = cli.build_parser()
    for command in ("connect",):
        assert parser.parse_args([command]).log_level == "INFO"


def test_missing_template_stops_before_the_browser(monkeypatch):
    import linkedin_bots.shared.infrastructure.browser as browser

    def no_browser(*args, **kwargs):
        raise AssertionError("the browser must not be touched")

    monkeypatch.setattr(browser, "create_driver", no_browser)
    with pytest.raises(SystemExit) as stopped:
        cli.main(["connect", "-m", "nope.txt"])
    assert stopped.value.code == 1


def test_runs_log_their_log_file(isolated_data_home):
    logger, path = start_logging("connecting", "INFO")
    try:
        assert path.parent == isolated_data_home / "connecting" / "logs"
        assert path.name.startswith("week-")
        assert f"Log file: {path}" in path.read_text(encoding="utf-8")
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


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
