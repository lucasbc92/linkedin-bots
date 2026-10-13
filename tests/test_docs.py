"""The documented test command runs the whole suite, guard included."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _texts():
    paths = [*ROOT.glob("README*.md"), *(ROOT / "docs").glob("*.md"),
             *(ROOT / "tests").rglob("*.py")]
    return {p: p.read_text(encoding="utf-8") for p in paths if p != Path(__file__)}


def test_no_doc_points_at_unittest_discover():
    """unittest skips conftest.py — the fixture that keeps tests off real data."""
    offenders = [str(p.relative_to(ROOT)) for p, text in _texts().items()
                 if "unittest discover" in text]
    assert offenders == []


def test_the_readme_says_how_to_run_the_tests_in_each_language():
    english, portuguese = (ROOT / "README.md").read_text(
        encoding="utf-8").split("\n## Português (Brasil)\n")
    for text in (english, portuguese):
        assert "python -m pytest" in text and "lint-imports" in text
