"""The headline selectors, run against LinkedIn HTML saved in tests/fixtures/messaging/.

The saved pages are REDACTED, so each test writes a synthetic name and
headline into the profile card first. They need lxml for its XPath engine,
and skip rather than fail when it is absent.
"""
from pathlib import Path

import pytest

from linkedin_bots.messaging.adapters.selenium.thread_page import (CARD_HEADLINE_XPATH,
                                                                  CARD_NAME_XPATH,
                                                                  HEADLINE_TITLE_XPATH,
                                                                  PROFILE_CARD_XPATH)

html = pytest.importorskip("lxml.html")

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "messaging"
HEADLINE = "Senior Software Engineer | Java | Spring"


@pytest.mark.parametrize("page", ["message-list-detail.html", "message-list-detail-old.html"])
def test_the_profile_card_yields_the_contacts_name_and_full_headline(page):
    root = html.fromstring((FIXTURES / page).read_text(encoding="utf-8"))
    cards = root.xpath(PROFILE_CARD_XPATH)
    assert len(cards) == 1
    card = cards[0]

    (name,) = card.xpath(CARD_NAME_XPATH)
    name.xpath(".//span[@class='truncate']")[0].text = "Ana Silva"
    (subtitle,) = card.xpath(CARD_HEADLINE_XPATH)
    (inner,) = subtitle.xpath(HEADLINE_TITLE_XPATH)
    inner.set("title", HEADLINE)
    inner.text = "Senior Software Engineer | Ja…"

    assert "Ana Silva" in card.xpath(CARD_NAME_XPATH)[0].text_content()
    assert card.xpath(CARD_HEADLINE_XPATH)[0].xpath(HEADLINE_TITLE_XPATH)[0].get("title") == HEADLINE
