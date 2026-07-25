"""The conversation list, with the DOM reads stubbed out."""
from linkedin_bots.messaging.adapters.selenium.conversation_list import SeleniumConversationList
from linkedin_bots.messaging.domain.walk import ConversationCard


class _Slot:
    """A conversation <li> that LinkedIn reuses by position: the node
    survives a re-sort, but shows whoever now sits in its slot."""

    def __init__(self, name):
        self.name = name

    def is_displayed(self):
        return True


def _page(slots, upward=False):
    page = SeleniumConversationList(driver=None, upward=upward)
    page._get_cards = lambda: slots
    page._card_name = lambda slot: slot.name
    return page


def test_walking_up_follows_the_contact_not_the_slot():
    """Walking up from Ana, Bruno is next. Sending to Ana moves her to the
    top and shifts everyone above her down one slot, so Bruno's old node
    now shows Carla — following the node would skip Bruno."""
    slots = [_Slot("Carla"), _Slot("Bruno"), _Slot("Ana")]
    next_card = slots[1]
    for slot, name in zip(slots, ["Ana", "Carla", "Bruno"]):
        slot.name = name
    assert _page(slots).refresh(next_card, "Bruno") is slots[2]


def test_an_unmoved_card_is_kept():
    slots = [_Slot("Ana"), _Slot("Bruno")]
    assert _page(slots).refresh(slots[1], "Bruno") is slots[1]


def test_a_contact_gone_from_the_list_is_lost():
    slots = [_Slot("Ana"), _Slot("Carla")]
    gone = _Slot("Carla")
    assert _page(slots).refresh(gone, "Bruno") is None


def test_start_without_an_active_card_takes_the_end_the_walk_starts_from():
    slots = [_Slot("Ana"), _Slot("Bruno")]
    down, up = _page(slots), _page(slots, upward=True)
    for page in (down, up):
        page._active_card = lambda: None
    assert down.start() == (slots[0], False)
    assert up.start() == (slots[1], False)


def test_reading_a_card_gathers_what_it_shows():
    page = _page([])
    page._ensure_rendered = lambda card: "Ana Silva"
    page._card_timestamp = lambda card: "Oct 5"
    page._card_photo_id = lambda card: "PHOTO"
    page._card_skip_pill = lambda card: None
    page._card_last_message = lambda card: "You: Saudações!"
    assert page.read(object()) == ConversationCard("Ana Silva", "Oct 5", "PHOTO", None,
                                                   "You: Saudações!")


def test_an_unnamed_card_is_not_read_further():
    page = _page([])
    page._ensure_rendered = lambda card: None
    page._card_timestamp = lambda card: "Oct 5"
    assert page.read(object()) == ConversationCard(None, "Oct 5")
