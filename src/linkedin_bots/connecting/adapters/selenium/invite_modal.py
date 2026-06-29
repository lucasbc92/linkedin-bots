"""LinkedIn's invite modal, as a Page Object.

The modal lives inside an open Shadow DOM host (``#interop-outlet``), which
Selenium's XPath cannot reach, so every interaction uses CSS selectors on
the shadow root.
"""
import logging
import time

from selenium.webdriver.common.by import By

from linkedin_bots.connecting.application.ports import InviteResult, InviteStatus
from linkedin_bots.connecting.domain.labels import full_name_from_label
from linkedin_bots.shared.domain.names import display_first_name
from linkedin_bots.shared.infrastructure.clicking import ClickMixin

logger = logging.getLogger("linkedin_bot")


class SeleniumInviteModal(ClickMixin):
    def __init__(self, driver, guard, pause):
        self.driver = driver
        self.guard = guard
        self.pause = pause

    def complete(self, target_label, name, note):
        """Drive the open invite modal through to a confirmed invitation.

        Shared by both routes into it — the Connect control on a search card
        and the one behind a profile's More menu. ``note`` composes the note
        from a first name, or is None to send without one.
        """
        shadow = self.get_modal_shadow_root(timeout=10)
        if shadow is None:
            if not self.guard.check():
                return InviteResult(InviteStatus.STOP, name)
            logger.warning(f"No modal appeared for {target_label}. Skipping.")
            return InviteResult(InviteStatus.SKIPPED, name)

        if not self.guard.check():
            return InviteResult(InviteStatus.STOP, name)

        if self.modal_requires_email(shadow):
            logger.warning(f"{target_label} requires email to connect. Skipping.")
            self.dismiss_open_modal()
            self.wait_modal_closed(shadow, timeout=3)
            self.pause(2, 4)
            return InviteResult(InviteStatus.SKIPPED, name)

        if not name:
            name = self.extract_name_from_modal(shadow)

        if note is None:
            send_btn = self.find_in_shadow(
                shadow, "button[aria-label='Send without a note']", require_enabled=True)
            if send_btn is None:
                if not self.guard.check():
                    return InviteResult(InviteStatus.STOP, name)
                logger.warning(f"No 'Send without a note' button for {target_label}. Skipping.")
                return InviteResult(InviteStatus.SKIPPED, name)
            self._robust_click(send_btn, "Send without a note button")
            logger.info(f"Sending without note to {name or target_label}")
        else:
            add_note_btn = self.find_in_shadow(
                shadow, "button[aria-label='Add a note']", require_enabled=True)
            if add_note_btn is None:
                if not self.guard.check():
                    return InviteResult(InviteStatus.STOP, name)
                logger.warning(f"No 'Add a note' button for {target_label}. Skipping.")
                return InviteResult(InviteStatus.SKIPPED, name)
            self._robust_click(add_note_btn, "Add a note button")

            message_box = self.find_in_shadow(shadow, "#custom-message")
            if message_box is None:
                if not self.guard.check():
                    return InviteResult(InviteStatus.STOP, name)
                logger.warning(f"No message box appeared for {target_label}. Skipping.")
                return InviteResult(InviteStatus.SKIPPED, name)

            personalized_message = note(name)
            logger.info(
                f"Sending to {name or target_label}: "
                f"{personalized_message.splitlines()[0] if personalized_message else ''}")

            self.fill_message_box(message_box, personalized_message)
            time.sleep(1)

            try:
                textarea_len = self.driver.execute_script(
                    "return (arguments[0].value || '').length;", message_box)
                logger.debug(
                    f"Textarea length as seen by LinkedIn: {textarea_len} "
                    f"(expected {len(personalized_message.encode('utf-16-le')) // 2})")
            except Exception:
                pass

            send_btn = self.find_in_shadow(
                shadow, "button[aria-label='Send invitation']", require_enabled=True)
            if send_btn is None:
                if not self.guard.check():
                    return InviteResult(InviteStatus.STOP, name)
                logger.warning(
                    f"Send button never became clickable for {target_label}. Skipping.")
                return InviteResult(InviteStatus.SKIPPED, name)

            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", send_btn)
            except Exception:
                pass
            logger.debug(f"Clicking Send (enabled={send_btn.is_enabled()}) for {target_label}")
            self._robust_click(send_btn, "Send invitation button")

        if not self.wait_modal_closed(shadow, timeout=5):
            if not self.guard.check():
                return InviteResult(InviteStatus.STOP, name)
            logger.warning(f"Modal never closed for {target_label}. Skipping.")
            return InviteResult(InviteStatus.UNCONFIRMED, name)

        if self.guard.rate_limited():
            return InviteResult(InviteStatus.STOP, name)

        if self.verify_successful_invitation_sent(target_label, full_name_from_label(target_label)):
            return InviteResult(InviteStatus.SENT, name)
        if not self.guard.check():
            return InviteResult(InviteStatus.STOP, name)
        return InviteResult(InviteStatus.FAILED, name)

    def fill_message_box(self, message_box, text):
        """Type the note into the modal textarea so LinkedIn registers it and enables Send.

        Non-BMP characters (emoji) break ChromeDriver's send_keys, so we type
        the BMP part first to activate the framework binding, then inject the
        full text via the native value setter.
        """
        try:
            message_box.click()
        except Exception:
            self.driver.execute_script("arguments[0].focus();", message_box)

        message_box.clear()
        bmp_text = ''.join(ch for ch in text if ord(ch) <= 0xFFFF)

        if bmp_text == text:
            message_box.send_keys(text)
            return

        if bmp_text:
            message_box.send_keys(bmp_text)
        self.driver.execute_script(
            "const el = arguments[0], val = arguments[1];"
            "const setter = Object.getOwnPropertyDescriptor("
            "window.HTMLTextAreaElement.prototype, 'value').set;"
            "setter.call(el, val);"
            "el.dispatchEvent(new Event('input', { bubbles: true }));"
            "el.dispatchEvent(new Event('change', { bubbles: true }));",
            message_box, text)

    def get_modal_shadow_root(self, timeout=10):
        """Return the #interop-outlet shadow root once the invite modal is inside it.

        LinkedIn renders the connect modal inside an open Shadow DOM host.
        Selenium can't reach shadow content with XPath, so every modal
        interaction goes through this shadow root (CSS selectors only).
        Returns the ShadowRoot, or None if the modal never appeared.
        """
        end = time.time() + timeout
        while time.time() < end:
            for host_sel in ("#interop-outlet", "[data-testid='interop-shadowdom']"):
                hosts = self.driver.find_elements(By.CSS_SELECTOR, host_sel)
                for host in hosts:
                    try:
                        sr = host.shadow_root
                    except Exception:
                        continue
                    try:
                        if sr.find_elements(
                                By.CSS_SELECTOR,
                                "[data-test-modal-id='send-invite-modal'], "
                                "[data-test-modal] [id='send-invite-modal']"):
                            return sr
                    except Exception:
                        continue
            time.sleep(0.3)
        return None

    def find_in_shadow(self, shadow_root, css, timeout=10, require_enabled=False):
        """Wait for and return a visible element matching css inside a shadow root."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                for el in shadow_root.find_elements(By.CSS_SELECTOR, css):
                    try:
                        if el.is_displayed() and (not require_enabled or el.is_enabled()):
                            return el
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.3)
        return None

    def wait_modal_closed(self, shadow_root, timeout=5):
        """Return True once the invite modal is no longer present in the shadow root."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                if not shadow_root.find_elements(
                        By.CSS_SELECTOR, "[data-test-modal-id='send-invite-modal']"):
                    return True
            except Exception:
                return True
            time.sleep(0.3)
        return False

    def modal_requires_email(self, shadow_root):
        """Detect the 'enter their email to connect' screen; caller cancels and skips."""
        try:
            return bool(shadow_root.find_elements(
                By.CSS_SELECTOR,
                "input[type='email'], input[name='email'], "
                "[data-test-send-invite-modal-check-email-link]"))
        except Exception:
            return False

    def dismiss_open_modal(self):
        """Best-effort close of any open invite modal (shadow DOM first, then light DOM)."""
        try:
            for host_sel in ("#interop-outlet", "[data-testid='interop-shadowdom']"):
                for host in self.driver.find_elements(By.CSS_SELECTOR, host_sel):
                    try:
                        sr = host.shadow_root
                    except Exception:
                        continue
                    btns = sr.find_elements(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                    if btns:
                        self._robust_click(btns[0])
                        return
        except Exception:
            pass
        try:
            btns = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Dismiss')]")
            if btns:
                self.driver.execute_script("arguments[0].click();", btns[0])
        except Exception:
            pass

    def extract_name_from_modal(self, shadow_root=None):
        """Extract name from the invite modal body (<strong>Full Name</strong>)."""
        try:
            if shadow_root is not None:
                try:
                    for el in shadow_root.find_elements(
                            By.CSS_SELECTOR, ".artdeco-modal__content strong"):
                        text = el.text.strip()
                        if text:
                            first_name = display_first_name(text)
                            logger.debug(f"Extracted name from modal body: {first_name}")
                            return first_name
                except Exception:
                    pass

            strong_elements = self.driver.find_elements(
                By.XPATH,
                "//div[@data-test-modal]//div[contains(@class, 'artdeco-modal__content')]//strong | "
                "//div[contains(@class, 'artdeco-modal')]//div[contains(@class, 'artdeco-modal__content')]//strong")
            for el in strong_elements:
                text = el.text.strip()
                if text:
                    first_name = display_first_name(text)
                    logger.debug(f"Extracted name from modal body: {first_name}")
                    return first_name

            modal_name_elements = self.driver.find_elements(
                By.XPATH, "//div[contains(@class, 'artdeco-modal')]//span[@aria-hidden='true']")
            for elem in modal_name_elements:
                name_text = elem.text.strip()
                if name_text and len(name_text.split()) >= 1:
                    if name_text.lower() in ("connect", "add a note", "send", "include", "add", "invite"):
                        continue
                    return name_text.split()[0]

            for selector in (
                "//div[contains(@class, 'artdeco-modal')]//h2",
                "//div[contains(@class, 'artdeco-modal')]//h3",
                "//div[contains(@class, 'send-invite')]//h2",
            ):
                try:
                    for element in self.driver.find_elements(By.XPATH, selector):
                        text = element.text.strip()
                        if not text:
                            continue
                        if "Connect with " in text:
                            return text.replace("Connect with ", "").split()[0]
                        if "Invite " in text and " to connect" in text:
                            return text.replace("Invite ", "").replace(" to connect", "").split()[0]
                except Exception:
                    continue

            logger.debug("Could not extract name from modal")
            return None
        except Exception as e:
            logger.debug(f"Error extracting name from modal: {e}")
            return None

    def verify_successful_invitation_sent(self, target_label=None, full_name=None):
        """Confirm the invite registered by checking that the Connect control turned Pending."""
        try:
            time.sleep(2)

            if not self.guard.check():
                return False

            if not target_label:
                return True

            if full_name:
                pending = self.driver.find_elements(
                    By.XPATH, "//a[contains(@aria-label, 'Pending')] | "
                              "//button[contains(@aria-label, 'Pending')]")
                for el in pending:
                    label = el.get_attribute("aria-label") or ""
                    if full_name in label:
                        logger.debug(f"Confirmed Pending state for {full_name}")
                        return True

            still_connect = self.driver.find_elements(
                By.XPATH, "//a[@aria-label=" + self._xpath_literal(target_label) + "]")
            if still_connect:
                logger.warning(
                    f"Connect control still present for {target_label} — "
                    "invite did NOT register (likely an ignored click)")
                return False

            logger.debug(f"Connect control for {target_label} is gone — assuming sent")
            return True

        except Exception as e:
            logger.debug(f"Error verifying invitation: {e}")
            return True

    @staticmethod
    def _xpath_literal(value):
        """Build a safe XPath string literal that handles embedded quotes."""
        if '"' not in value:
            return f'"{value}"'
        if "'" not in value:
            return f"'{value}'"
        parts = value.split('"')
        return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"
