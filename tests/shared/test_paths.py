"""Where runtime data lives."""
import pytest

from linkedin_bots.shared.infrastructure import paths


def test_home_follows_the_environment_variable(isolated_data_home):
    assert paths.data_home() == isolated_data_home


def test_context_and_log_dirs_are_created_on_first_use(isolated_data_home):
    assert not isolated_data_home.exists()
    logs = paths.log_dir("messaging")
    assert logs == isolated_data_home / "messaging" / "logs"
    assert logs.is_dir()


def test_a_home_with_spaces_works(tmp_path, monkeypatch):
    home = tmp_path / "my data" / "linkedin bots"
    monkeypatch.setenv("LINKEDIN_BOTS_HOME", str(home))
    assert paths.context_dir("connecting") == home / "connecting"
    assert (home / "connecting").is_dir()


def test_without_the_variable_it_is_the_user_data_dir(monkeypatch):
    monkeypatch.delenv("LINKEDIN_BOTS_HOME")
    home = paths.data_home()
    assert home.is_absolute()
    assert home.name == "linkedin-bots"


def test_a_home_under_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LINKEDIN_BOTS_HOME", "~/lb-data")
    assert paths.data_home() == tmp_path / "lb-data"


def test_a_relative_home_is_refused(monkeypatch):
    """A relative home would give every folder its own empty send history."""
    monkeypatch.setenv("LINKEDIN_BOTS_HOME", "lb-data")
    with pytest.raises(paths.DataHomeError):
        paths.data_home()
