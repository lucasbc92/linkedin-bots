"""The generic templates the Windows executable ships in place of the author's own."""
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "packaging" / "templates"
INVITE_LIMIT = 300
NAME_ROOM = 40  # left for long names once {name} is filled in
PERSONAL = ("Lucas", "lucasbc92", "wa.me", "+55")


def read(context):
    return (TEMPLATES / context / "message.txt").read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("context", ["connecting", "messaging"])
def test_each_bot_has_a_generic_template_that_greets_by_name(context):
    text = read(context)
    assert "{name}" in text
    for marker in PERSONAL:
        assert marker not in text


def test_the_invitation_note_leaves_room_for_long_names():
    # LinkedIn counts UTF-16 code units, so an emoji takes two.
    units = len(read("connecting").replace("{name}", "").encode("utf-16-le")) // 2
    assert units + NAME_ROOM <= INVITE_LIMIT
