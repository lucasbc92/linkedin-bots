"""LinkedIn's conversation list, as a Page Object.

The list is virtualized (occluded cards are emptied until they come near the
viewport), lazy-loads more conversations when its last card takes focus, and
re-sorts the moment a message is sent — reusing its <li> nodes by position.
"""
import logging
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from linkedin_bots.messaging.adapters.selenium.linkedin_ids import photo_id_from_src
from linkedin_bots.messaging.domain.card_date import first_card_on_or_before
from linkedin_bots.messaging.domain.walk import ConversationCard
from linkedin_bots.shared.infrastructure.clicking import ClickMixin

logger = logging.getLogger("linkedin_bot")

_CONVERSATION_LIST = "ul.msg-conversations-container__conversations-list"
_CARD_ITEM = "li.msg-conversation-listitem"
_NAME_SELECTOR = "h3.msg-conversation-listitem__participant-names span.truncate"
_TIME_SELECTOR = "time.msg-conversation-listitem__time-stamp"
_CARD_PILL_SELECTOR = "span.msg-conversation-card__pill"
_LAST_MESSAGE_SELECTOR = "p.msg-conversation-card__message-snippet"
_PHOTO_SELECTOR = "img.presence-entity__image"
# Pill labels that mean the conversation should be left untouched.
_SKIP_PILL_LABELS = ("sponsored", "inmail", "linkedin offer")


class SeleniumConversationList(ClickMixin):
    def __init__(self, driver, upward=False):
        self.driver = driver
        self.upward = upward

    def open(self, timeout=10):
        """Focus the messaging tab and wait for its first card; False if none renders."""
        self._select_messaging_tab()
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, _CARD_ITEM)))
            return True
        except TimeoutException:
            return False

    def scroll_to_start_date(self, target):
        return self._scroll_to_start_date(target)

    def start(self):
        """The clicked conversation, else the end of the list the walk starts from."""
        current = self._active_card()
        if current is not None:
            return current, True
        cards = self._get_cards()
        if not cards:
            return None, False
        return (cards[-1] if self.upward else cards[0]), False

    def read(self, card):
        name = self._ensure_rendered(card)
        if not name:
            return ConversationCard(name=None, stamp=self._card_timestamp(card))
        return ConversationCard(name=name, stamp=self._card_timestamp(card),
                                photo=self._card_photo_id(card),
                                pill=self._card_skip_pill(card),
                                last_message=self._card_last_message(card))

    def ensure_name(self, card):
        return self._ensure_rendered(card)

    def advance(self, card):
        return self._prev_card(card) if self.upward else self._next_card(card)

    def refresh(self, card, name):
        return self._refresh_card(card, name)

    def _select_messaging_tab(self):
        """Switch to the LinkedIn messaging tab; fall back to the current tab."""
        handles = self.driver.window_handles
        for h in handles:
            try:
                self.driver.switch_to.window(h)
                url = (self.driver.current_url or "").lower()
                if "linkedin.com/messaging" in url or "linkedin.com/msg" in url:
                    logger.info(f"Using messaging tab: {self.driver.current_url}")
                    return True
            except Exception:
                continue
        logger.warning("No LinkedIn messaging tab found. Using the current tab.")
        return False

    def _get_cards(self):
        """Return all conversation-list <li> elements currently in the DOM."""
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, _CARD_ITEM)
        except Exception:
            return []

    def _card_name(self, card):
        try:
            el = card.find_element(By.CSS_SELECTOR, _NAME_SELECTOR)
            return el.text.strip()
        except Exception:
            return None

    def _card_timestamp(self, card):
        try:
            el = card.find_element(By.CSS_SELECTOR, _TIME_SELECTOR)
            return el.text.strip()
        except Exception:
            return None

    def _card_photo_id(self, card):
        """The participant's photo asset ID (see ``photo_id_from_src``)."""
        try:
            img = card.find_element(By.CSS_SELECTOR, _PHOTO_SELECTOR)
            return photo_id_from_src(img.get_attribute("src"))
        except Exception:
            return None

    def _card_skip_pill(self, card):
        """Return the pill label ("Sponsored"/"InMail") if the card carries a
        pill that means we should not message it, else ``None``.

        Sponsored ads and InMails share the same pill component; we match on
        the pill text so both are skipped without messaging.
        """
        try:
            pills = card.find_elements(By.CSS_SELECTOR, _CARD_PILL_SELECTOR)
        except Exception:
            return None
        for p in pills:
            try:
                text = p.text.lower()
            except Exception:
                continue
            for label in _SKIP_PILL_LABELS:
                if label in text:
                    return p.text.strip() or label.capitalize()
        return None

    def _card_last_message(self, card):
        """Return the last message preview text from the card, or None."""
        try:
            el = card.find_element(By.CSS_SELECTOR, _LAST_MESSAGE_SELECTOR)
            return el.text.strip()
        except Exception:
            return None

    def _scroll_list_bottom(self):
        """Scroll the conversation list container to trigger lazy-loading."""
        try:
            container = self.driver.find_element(By.CSS_SELECTOR, _CONVERSATION_LIST)
            self.driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight;", container)
            time.sleep(2)
        except Exception:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

    def _visible_card_timestamps(self):
        """Return ``[(index, raw timestamp), …]`` for every card that has a
        rendered ``<time>`` element, in list order.

        Done in one JS round-trip: with hundreds of cards loaded, probing each
        ``<li>`` through Selenium takes seconds per pass. Occluded
        (virtualized) cards have their content emptied by LinkedIn and simply
        don't appear in the result.
        """
        try:
            return self.driver.execute_script(
                "const out = [];"
                "document.querySelectorAll(arguments[0]).forEach((li, i) => {"
                "  const t = li.querySelector(arguments[1]);"
                "  if (t && t.textContent.trim()) out.push([i, t.textContent.trim()]);"
                "});"
                "return out;",
                _CARD_ITEM, _TIME_SELECTOR) or []
        except Exception as e:
            logger.debug(f"Could not collect card timestamps: {e}")
            return []

    def _focus_last_card(self):
        """Focus the second-to-last card to make the list lazy-load more.

        Same technique as focusLastElementLinkedinMessage.js: setting
        ``scrollTop`` alone doesn't reliably make the virtualized list fetch
        the next page, but moving focus to the last card does.
        """
        try:
            self.driver.execute_script(
                "const items = document.querySelectorAll(arguments[0]);"
                "const el = items[items.length - 2] || items[items.length - 1];"
                "if (el) el.focus();",
                _CARD_ITEM)
        except Exception:
            self._scroll_list_bottom()

    def _scroll_to_start_date(self, target):
        """Scroll until a conversation dated on or before ``target`` appears,
        then click it so the run starts from that card (inclusive).

        Returns True once the start card was clicked, False if the bottom of
        the list was reached without finding one.
        """
        logger.info(
            f"Looking for the first conversation dated on or before {target} …")
        while True:
            idx = first_card_on_or_before(self._visible_card_timestamps(), target)
            if idx is not None:
                cards = self._get_cards()
                if idx >= len(cards):
                    # List changed between the JS scan and now; rescan.
                    time.sleep(1)
                    continue
                card = cards[idx]
                name = self._card_name(card)
                ts = self._card_timestamp(card)
                logger.info(
                    f"Start card found at index {idx}: "
                    f"{name or '(unknown)'} — dated '{ts}'. Clicking it.")
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", card)
                except Exception:
                    pass
                time.sleep(1)
                self._robust_click(card, f"start card ({name or ts})")
                time.sleep(3)
                return True

            count_before = len(self._get_cards())
            logger.debug(
                f"No card on or before {target} among {count_before} loaded; "
                f"focusing the last card to load more …")
            self._focus_last_card()
            time.sleep(3)
            if len(self._get_cards()) <= count_before:
                logger.warning(
                    f"Reached the bottom of the list without finding a "
                    f"conversation dated on or before {target}.")
                return False

    def _active_card(self):
        """Return the <li> of the currently active conversation, or None."""
        try:
            return self.driver.execute_script(
                "const a = document.querySelector("
                "  '.msg-conversations-container__convo-item-link--active');"
                "return a ? a.closest(arguments[0]) : null;",
                _CARD_ITEM)
        except Exception as e:
            logger.debug(f"Could not find the active card: {e}")
            return None

    def _next_card(self, card):
        """Return the conversation <li> right after ``card`` in the list,
        lazy-loading one more page if ``card`` is currently the last one.
        Returns None only when the true bottom of the list was reached.
        """
        for attempt in (1, 2):
            try:
                nxt = self.driver.execute_script(
                    "let el = arguments[0].nextElementSibling;"
                    "while (el && !el.matches(arguments[1]))"
                    "  el = el.nextElementSibling;"
                    "return el;",
                    card, _CARD_ITEM)
            except Exception as e:
                logger.debug(f"Could not get the next card: {e}")
                return None
            if nxt is not None:
                return nxt
            if attempt == 1:
                logger.debug("At the last loaded card; focusing it to load more …")
                self._focus_last_card()
                time.sleep(3)
        return None

    def _prev_card(self, card):
        """Return the conversation <li> right before ``card`` in the list.

        No lazy-loading counterpart is needed here: by the time the walk
        reaches an old card (either clicked manually or via --start-date),
        every card above it toward the top was already loaded to get there.
        """
        try:
            return self.driver.execute_script(
                "let el = arguments[0].previousElementSibling;"
                "while (el && !el.matches(arguments[1]))"
                "  el = el.previousElementSibling;"
                "return el;",
                card, _CARD_ITEM)
        except Exception as e:
            logger.debug(f"Could not get the previous card: {e}")
            return None

    def _ensure_rendered(self, card, tries=3):
        """Return the card's name, scrolling it into view first if LinkedIn's
        virtualization has emptied it (occluded cards have no content until
        they get near the viewport)."""
        for _ in range(tries):
            name = self._card_name(card)
            if name:
                return name
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", card)
            except Exception:
                return None
            time.sleep(1)
        return self._card_name(card)

    def _card_by_name(self, name):
        """Find a conversation card by its participant name, or None."""
        for card in self._get_cards():
            if self._card_name(card) == name:
                return card
        return None

    def _refresh_card(self, card, name):
        """Return a usable element for a previously captured card.

        The list re-sorts after every send, and LinkedIn reuses the <li>
        nodes by position: walking up, everyone above the sent card shifts
        down one slot, so the captured node now shows the *following* contact
        (skipping the real next one). A node that no longer shows ``name`` —
        or went stale — is re-found by name instead.
        """
        if card is None:
            return None
        if not name:
            try:
                card.is_displayed()   # probe: raises if the node went stale
                return card
            except Exception:
                return None
        if self._card_name(card) == name:
            return card
        logger.debug(
            f"Captured card for {name!r} now shows someone else or went "
            f"stale; re-finding by name.")
        return self._card_by_name(name)
