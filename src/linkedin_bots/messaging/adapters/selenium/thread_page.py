"""A LinkedIn conversation, as a Page Object: open it from its card and send."""
import logging
import random
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from linkedin_bots.messaging.adapters.selenium.linkedin_ids import thread_id_from_url
from linkedin_bots.messaging.application.ports import SendResult, SendStatus
from linkedin_bots.shared.domain.names import display_first_name
from linkedin_bots.shared.infrastructure.clicking import ClickMixin

logger = logging.getLogger("linkedin_bot")

_COMPOSE_BOX = "div.msg-form__contenteditable[contenteditable='true'][role='textbox']"
_THREAD_HEADER_NAME = (
    "h2.msg-entity-lockup__entity-title,"
    "span.msg-thread__link-to-profile-name,"
    "span.msg-entity-lockup__entity-title"
)

# The profile card at the very start of a conversation's history carries the
# contact's name and headline; the conversation list shows neither.
PROFILE_CARD_XPATH = "//div[contains(concat(' ', normalize-space(@class), ' '), ' msg-s-profile-card ')]"
CARD_NAME_XPATH = ".//div[contains(concat(' ', normalize-space(@class), ' '), ' artdeco-entity-lockup__title ')]"
CARD_HEADLINE_XPATH = ".//div[contains(concat(' ', normalize-space(@class), ' '), ' artdeco-entity-lockup__subtitle ')]"
# Holds the full headline even when the visible text is truncated.
HEADLINE_TITLE_XPATH = "./div[@title]"
MESSAGE_LIST_CSS = "div.msg-s-message-list"
# Long conversations load their start on demand: scroll up at most this often.
HEADLINE_SCROLLS = 3


class SeleniumThreadPage(ClickMixin):
    def __init__(self, driver, pause):
        self.driver = driver
        self.pause = pause
        self._thread = None
        self._opened = False

    def send(self, card, name, message, ruled_out=frozenset()):
        """Open ``card``'s conversation and send ``message``.

        ``ruled_out`` holds thread IDs already messaged under this name; the
        conversation is skipped once it opens as one of them.
        """
        return self.open(card, name, ruled_out) or self.send_open(name, message)

    def open(self, card, name, ruled_out=frozenset()):
        """Open ``card``'s conversation; None once it is open as this contact,
        else the result that ends this contact."""
        self._thread, self._opened = None, False
        logger.info(f"Opening thread with {name} …")
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", card)
            self.pause(2, 5)
            self._robust_click(card, f"conversation card ({name})")
            self.pause(2, 4)

            if not self._wait_thread_open(name):
                logger.warning(f"Thread for {name} did not open. Skipping.")
                return SendResult(SendStatus.SKIPPED)

            thread = thread_id_from_url(self.driver.current_url)
            if thread and thread in ruled_out:
                logger.info(
                    f"Skipping {name} — same conversation as an earlier "
                    f"send to that name.")
                return SendResult(SendStatus.SKIPPED, thread)
        except Exception as e:
            logger.error(f"Error processing {name}: {e}")
            return SendResult(SendStatus.ERROR)
        self._thread, self._opened = thread, True
        return None

    def headline(self, name):
        """The headline on the open conversation's profile card, or None.

        Only a card naming this contact counts: a card still on screen from
        the previous conversation must not choose the template.
        """
        expected = name.split()[0].lower() if name else ""
        try:
            for attempt in range(HEADLINE_SCROLLS + 1):
                for card in self._profile_cards():
                    found = self._card_headline(card, expected)
                    if found:
                        return found
                if attempt < HEADLINE_SCROLLS:
                    self._scroll_history_to_top()
                    self.pause(1, 2)
        except Exception as e:
            logger.debug(f"Could not read {name}'s headline: {e}")
        return None

    def _profile_cards(self):
        return self.driver.find_elements(By.XPATH, PROFILE_CARD_XPATH)

    def _scroll_history_to_top(self):
        self.driver.execute_script(
            "const list = document.querySelector(arguments[0]);"
            "if (list) list.scrollTop = 0;", MESSAGE_LIST_CSS)

    @staticmethod
    def _card_headline(card, expected):
        names = card.find_elements(By.XPATH, CARD_NAME_XPATH)
        if not names or expected not in names[0].text.lower():
            return None
        for subtitle in card.find_elements(By.XPATH, CARD_HEADLINE_XPATH):
            for inner in subtitle.find_elements(By.XPATH, HEADLINE_TITLE_XPATH):
                title = (inner.get_attribute("title") or "").strip()
                if title:
                    return title
            text = subtitle.text.strip()
            if text:
                return text
        return None

    def send_open(self, name, message):
        """Send ``message`` in the conversation ``open`` just opened."""
        if not self._opened:
            logger.error(f"No open conversation for {name}. Skipping.")
            return SendResult(SendStatus.ERROR)
        self._opened = False  # one send per open
        first = display_first_name(name)
        thread = self._thread
        try:
            compose = self._get_compose_box()
            if compose is None:
                logger.warning(f"No compose box found for {name}. Skipping.")
                return SendResult(SendStatus.SKIPPED, thread)

            # Re-confirm identity right before typing: the panel can switch
            # to a different (already-messaged) contact between the click and
            # now (list re-sort, LinkedIn's own focus changes). Sending here
            # would resend to that earlier contact instead of this one.
            if not self._wait_thread_open(name, timeout=1):
                logger.warning(
                    f"Active thread switched away from {name} "
                    f"just before sending. Skipping to avoid "
                    f"messaging the wrong contact.")
                return SendResult(SendStatus.SKIPPED, thread)

            # Pause as if reading the thread before starting to type.
            self.pause(1.5, 3.5)

            logger.info(
                f"Sending to {first or name}: "
                f"{message.splitlines()[0] if message else ''}")

            if self._send_message(compose, message, name):
                return SendResult(SendStatus.SENT, thread)
            return SendResult(SendStatus.NOT_REGISTERED, thread)

        except Exception as e:
            logger.error(f"Error processing {name}: {e}")
            return SendResult(SendStatus.ERROR)

    def _insert_text(self, compose_box, text):
        """Insert text into the contenteditable compose box without triggering send.

        LinkedIn's DM box sends on Enter, so we cannot use send_keys for
        multi-line text.  ``execCommand('insertText')`` injects the full body
        (including newlines as soft-breaks) in one atomic operation.
        """
        try:
            compose_box.click()
        except Exception:
            self.driver.execute_script("arguments[0].focus();", compose_box)

        inserted = self.driver.execute_script(
            "arguments[0].focus();"
            "return document.execCommand('insertText', false, arguments[1]);",
            compose_box, text)

        if not inserted:
            # Fallback: set innerText and fire input event
            logger.debug("execCommand returned false; falling back to innerText setter")
            self.driver.execute_script(
                "const el = arguments[0];"
                "el.innerText = arguments[1];"
                "el.dispatchEvent(new Event('input', {bubbles: true}));"
                "el.dispatchEvent(new Event('change', {bubbles: true}));",
                compose_box, text)

    def _box_is_empty(self, compose_box):
        try:
            content = self.driver.execute_script(
                "return (arguments[0].textContent || '').trim();", compose_box)
            return not content
        except Exception:
            return False

    def _send_message(self, compose_box, text, contact_label):
        """Type text into the compose box and send it. Returns True on success."""
        try:
            self._insert_text(compose_box, text)
            time.sleep(random.uniform(1.5, 3.5))

            # Verify the box has content
            if self._box_is_empty(compose_box):
                logger.warning(f"Compose box appears empty after insert for {contact_label}. Skipping.")
                return False

            # Primary send: trusted Enter key
            compose_box.send_keys(Keys.ENTER)
            time.sleep(random.uniform(2, 4))

            # Verify sent: box should be empty / placeholder restored
            if self._box_is_empty(compose_box):
                return True

            # Fallback: click the Send button
            logger.debug("Box still has content after Enter; trying Send button fallback")
            try:
                send_btn = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "button.msg-form__send-button, "
                    "button[data-test-msg-send-btn]")
                self._robust_click(send_btn, "Send button")
                time.sleep(random.uniform(2, 4))
                return self._box_is_empty(compose_box)
            except NoSuchElementException:
                logger.warning(f"No Send button found for {contact_label}.")
                return False

        except Exception as e:
            logger.error(f"Error sending message to {contact_label}: {e}")
            return False

    def _wait_thread_open(self, name_full, timeout=8):
        """Wait until the active thread panel shows the contact's name.

        A header is only a match when it actually mentions the expected
        first name. Treating "some header is visible" as a match (regardless
        of whose name it shows) let the bot proceed while a *different*,
        already-messaged contact's thread was still open — sending the next
        message to the wrong person.
        """
        expected = name_full.split()[0].lower() if name_full else None
        end = time.time() + timeout
        while time.time() < end:
            try:
                for sel in _THREAD_HEADER_NAME.split(","):
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel.strip()):
                        text = el.text.strip()
                        if not text or not el.is_displayed():
                            continue
                        if expected is None or expected in text.lower():
                            return True
            except Exception:
                pass
            time.sleep(0.8)
        return False

    def _get_compose_box(self, timeout=8):
        """Return the compose contenteditable div once it's available."""
        end = time.time() + timeout
        while time.time() < end:
            els = self.driver.find_elements(By.CSS_SELECTOR, _COMPOSE_BOX)
            for el in els:
                try:
                    if el.is_displayed():
                        return el
                except Exception:
                    continue
            time.sleep(0.8)
        return None
