"""The templates shipped in the package are generic: personal ones live in the data home."""
import pytest

from linkedin_bots.shared.infrastructure.templates import template_dir

SHIPPED = {
    "connecting": {"message.txt", "message_english.txt", "dev_message.txt", "dev_message_english.txt"},
    "messaging": {"message.txt", "message_english.txt", "reconnect.txt", "reconnect_english.txt",
                  "dev_message.txt", "dev_message_english.txt", "dev_reconnect.txt",
                  "dev_reconnect_english.txt", "message_hired.txt", "message_hired_english.txt"},
}
INVITE_LIMIT = 300
NAME_ROOM = 40  # left for long names once {name} is filled in
PERSONAL = ("Lucas", "lucasbc92", "wa.me", "+55")


def read(context, name):
    return (template_dir(context) / name).read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("context", SHIPPED)
def test_each_context_ships_exactly_its_generic_templates(context):
    assert {p.name for p in template_dir(context).glob("*.txt")} == SHIPPED[context]


@pytest.mark.parametrize("context,name", [(c, n) for c, names in SHIPPED.items() for n in sorted(names)])
def test_a_shipped_template_greets_by_name_and_holds_no_personal_data(context, name):
    text = read(context, name)
    assert "{name}" in text
    for marker in PERSONAL:
        assert marker not in text


@pytest.mark.parametrize("name", sorted(SHIPPED["connecting"]))
def test_an_invitation_note_leaves_room_for_long_names(name):
    # LinkedIn counts UTF-16 code units, so an emoji takes two.
    units = len(read("connecting", name).replace("{name}", "").encode("utf-16-le")) // 2
    assert units + NAME_ROOM <= INVITE_LIMIT
