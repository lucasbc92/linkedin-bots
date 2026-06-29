"""The connect selectors, run against LinkedIn HTML saved in tests/fixtures/connecting/."""
import unittest
from pathlib import Path

from tests.connecting.fakes import profile_module, results_module


class SavedMarkupTests(unittest.TestCase):
    """The selectors, run against the LinkedIn HTML saved in tests/fixtures/connecting/.

    Every other test here uses a hand-built DOM, which proves the logic but
    not that the selectors match what LinkedIn actually ships. These cases
    close that gap. They need lxml for its XPath engine — it is not needed to
    *run* the bots, so they skip rather than fail when it is absent.
    """

    @classmethod
    def setUpClass(cls):
        try:
            from lxml import html
        except ImportError:  # pragma: no cover - depends on the environment
            raise unittest.SkipTest("lxml is not installed")
        cls.html = html
        cls.examples = Path(__file__).resolve().parents[2] / "fixtures" / "connecting"

    def load(self, name):
        return self.html.fromstring(
            self.examples.joinpath(name).read_text(encoding="utf-8"))

    def card_for(self, control):
        """What find_result_card() climbs to, in lxml terms."""
        node, card = control, None
        for _ in range(12):
            node = node.getparent()
            if node is None:
                break
            hrefs = {a.get("href", "").split("?")[0].rstrip("/")
                     for a in node.xpath(".//a[contains(@href, 'linkedin.com/in/')]")}
            hrefs.discard("")
            if len(hrefs) > 1:
                break
            if hrefs:
                card = node
        return card

    def test_the_follow_only_card_offers_follow_and_nothing_else(self):
        card_html = self.load("follow-person.html")
        follows = card_html.xpath(results_module.FOLLOW_XPATH)
        self.assertEqual([f.get("aria-label") for f in follows],
                         ["Follow Silvana Ferreira Alcides"])
        self.assertEqual(card_html.xpath(results_module.CONNECT_XPATH), [],
                         "this is the card the detour exists for")

    def test_the_card_climb_lands_on_the_right_person(self):
        """The row also links the shared connections; picking one of those
        would open a stranger's profile."""
        card_html = self.load("follow-person.html")
        control = card_html.xpath(results_module.FOLLOW_XPATH)[0]
        card = self.card_for(control)
        self.assertIsNotNone(card)
        self.assertEqual(card.xpath(results_module.CARD_INVITE_XPATH), [])
        links = card.xpath(".//a[contains(@href, '/in/')]")
        self.assertEqual(
            links[0].get("href").split("?")[0],
            "https://www.linkedin.com/in/silvana-ferreira-alcides-09831623/")

    def test_a_connectable_results_page_offers_no_follow_detours(self):
        page = self.load("search-results-section-new.html")
        self.assertTrue(page.xpath(results_module.CONNECT_XPATH))
        self.assertEqual(page.xpath(results_module.FOLLOW_XPATH), [])

    def test_the_more_menu_labels_its_connect_on_an_inner_div(self):
        """Saved from a live Follow-only profile with the menu open. The
        first cut of this feature looked for a labelled <a> or <button> and
        found nothing here, so every one of those people was skipped."""
        menu = self.load("profile-more-menu.html")

        self.assertEqual(
            menu.xpath("//a[starts-with(@aria-label, 'Invite ')] | "
                       "//button[starts-with(@aria-label, 'Invite ')]"), [],
            "the link does not carry the label")

        labelled = menu.xpath("//*[starts-with(@aria-label, 'Invite ') and "
                              "contains(@aria-label, 'to connect')]")
        self.assertEqual([e.tag for e in labelled], ["div"])
        self.assertEqual(labelled[0].get("aria-label"),
                         "Invite Alex Nájera Arcia to connect")

        clickable = labelled[0].xpath(profile_module.CLICKABLE_XPATH)
        self.assertEqual(clickable[0].tag, "a",
                         "the <a> around it is what carries the action")
        self.assertIn("/preload/custom-invite/", clickable[0].get("href"))

    def test_the_more_menu_item_reads_connect(self):
        """The last-resort match, for a menu that carries no label at all."""
        menu = self.load("profile-more-menu.html")
        items = menu.xpath("//*[@role='menu']//*[@role='menuitem']")
        texts = [" ".join(item.text_content().split()) for item in items]
        self.assertIn("Connect", texts)

    def test_the_profile_carries_a_more_button_and_a_named_connect(self):
        profile = self.load("profile.html")
        self.assertTrue(profile.xpath(profile_module.MORE_BUTTON_XPATH))
        # PROFILE_CONNECT_CSS as XPath — lxml's CSS support is optional.
        connects = profile.xpath(
            "//a[starts-with(@aria-label, 'Invite ') and "
            "contains(@aria-label, 'to connect')] | "
            "//button[starts-with(@aria-label, 'Invite ') and "
            "contains(@aria-label, 'to connect')]")
        self.assertEqual([c.get("aria-label") for c in connects],
                         ["Invite Renata Santos to connect"])
