"""Keep every test away from the real data directory."""
import pytest


@pytest.fixture(autouse=True)
def isolated_data_home(tmp_path, monkeypatch):
    """Point LINKEDIN_BOTS_HOME at a fresh folder for each test."""
    home = tmp_path / "data"
    monkeypatch.setenv("LINKEDIN_BOTS_HOME", str(home))
    return home
