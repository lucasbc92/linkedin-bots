"""Reading template files."""
from linkedin_bots.shared.domain.messages import DEFAULT_MESSAGE
from linkedin_bots.shared.infrastructure.template_files import load_templates


def test_reads_a_file(tmp_path):
    path = tmp_path / "t.txt"
    path.write_text("Olá, {name}!", encoding="utf-8")
    assert load_templates(str(path)).personalize("Ana") == "Olá, Ana!"


def test_a_missing_file_falls_back_to_the_default(tmp_path, caplog):
    templates = load_templates(str(tmp_path / "nope.txt"))
    assert templates.personalize("Ana") == DEFAULT_MESSAGE.replace("{name}", "Ana")
    assert "not found. Using default." in caplog.text


def test_no_file_at_all_is_the_default():
    assert load_templates(None).personalize("Ana") == DEFAULT_MESSAGE.replace("{name}", "Ana")
