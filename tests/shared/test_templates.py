"""Message templates: the user's own first, then the ones shipped inside the package."""
from linkedin_bots.shared.infrastructure.templates import (resolve_template, template_dir,
                                                           user_template_dir)


def test_bare_names_resolve_inside_the_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = resolve_template("message.txt", "messaging")
    assert path.is_file()
    assert path.parent == template_dir("messaging")


def test_paths_are_used_as_given(tmp_path):
    custom = tmp_path / "mine.txt"
    assert resolve_template(str(custom), "connecting") == custom


def test_every_context_ships_its_default_template():
    for context in ("connecting", "messaging"):
        assert (template_dir(context) / "message.txt").is_file()


def test_the_users_own_templates_live_in_the_data_home(isolated_data_home):
    assert user_template_dir("messaging") == isolated_data_home / "messaging" / "templates"


def test_a_template_of_the_users_own_wins_over_the_shipped_one(isolated_data_home):
    own = isolated_data_home / "messaging" / "templates" / "message.txt"
    own.parent.mkdir(parents=True)
    own.write_text("Hi {name}, it's me.", encoding="utf-8")
    assert resolve_template("message.txt", "messaging") == own


def test_the_shipped_template_fills_in_for_one_the_user_lacks(isolated_data_home):
    folder = isolated_data_home / "messaging" / "templates"
    folder.mkdir(parents=True)
    (folder / "reconnect.txt").write_text("Long time no see!", encoding="utf-8")
    assert resolve_template("message.txt", "messaging") == template_dir("messaging") / "message.txt"
