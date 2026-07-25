"""Message templates ship inside the package."""
from linkedin_bots.shared.infrastructure.templates import resolve_template, template_dir


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
