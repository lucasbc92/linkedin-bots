"""Message templates: variations, {name}, LinkedIn's length cap."""
from linkedin_bots.shared.domain.messages import DEFAULT_MESSAGE, MessageTemplates, truncate_units


def test_variations_are_split_on_a_dash_line():
    templates = MessageTemplates.from_text("Oi, {name}!\n---\nOlá, {name}!")
    assert sorted({templates.personalize("Ana") for _ in range(200)}) == ["Oi, Ana!", "Olá, Ana!"]


def test_an_empty_text_falls_back_to_the_default():
    assert MessageTemplates.from_text("  \n").personalize() == DEFAULT_MESSAGE.replace(" {name}", "")


def test_no_name_drops_the_placeholder_and_its_comma():
    assert MessageTemplates.from_text("Olá, {name}, tudo bem?").personalize() == "Olá, tudo bem?"


def test_a_name_that_breaks_the_cap_is_omitted():
    templates = MessageTemplates.from_text("Hi {name}" + "x" * 290, max_length=300)
    assert "{name}" not in templates.personalize("A" * 20)
    assert len(templates.personalize("A" * 20)) <= 300


def test_emoji_count_as_two_units():
    """149 emoji are 298 units; adding " Ana" (4) would exceed 300."""
    templates = MessageTemplates.from_text("😊" * 149 + " {name}", max_length=300)
    assert templates.personalize("Ana") == "😊" * 149


def test_no_variations_means_no_message():
    assert MessageTemplates([]).personalize("Ana") == ""


def _units(text):
    return len(text.encode("utf-16-le")) // 2


def test_truncation_counts_utf16_units():
    """151 emoji are 302 units; LinkedIn's cap is 300."""
    templates = MessageTemplates.from_text("😊" * 151, max_length=300)
    assert _units(templates.personalize()) <= 300


def test_truncation_never_splits_an_emoji():
    assert truncate_units("ab😊", 3) == "ab"
    assert truncate_units("ab😊", 4) == "ab😊"


def test_plain_text_is_cut_at_the_limit():
    assert truncate_units("x" * 310, 300) == "x" * 300
