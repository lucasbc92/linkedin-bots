"""A LinkedIn profile, as a Page Object: find and click its owner's Connect.

A profile page carries Connect buttons for *other* people too — the "More
profiles for you" rail — so the control is always matched by name.
"""
import logging
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from linkedin_bots.connecting.domain.labels import full_name_from_label, same_person
from linkedin_bots.shared.infrastructure.clicking import ClickMixin

logger = logging.getLogger("linkedin_bot")

# The Connect control as it appears on a profile page: in the top card, in the
# "Connect if you know each other" prompt, or inside the More menu once it is
# open. Shadow roots only take CSS, so this is CSS.
#
# It matches any tag, because the three places do not agree on which one
# carries the label. In the top card it is the <a> itself; in the More menu
# the item is an <a href="/preload/custom-invite/…"> whose *inner div* holds
# the label. Matching only a/button is why the menu route found nothing.
PROFILE_CONNECT_CSS = "[aria-label^='Invite '][aria-label*='to connect']"
# An open profile menu, and its items. Used to find Connect by where it is
# when the name on it cannot be matched.
MENU_CSS = "[role='menu']"
MENU_ITEM_CSS = "[role='menuitem']"
# From the labelled element to the thing that actually carries the action.
CLICKABLE_XPATH = "ancestor-or-self::*[self::a or self::button][1]"
# The three-dots button in a profile's top card. The sticky header renders a
# second one, so the search takes whichever is on screen and tries the next if
# the menu it opens has no Connect in it.
MORE_BUTTON_XPATH = ("//button[@aria-label='More' or "
                     "starts-with(@aria-label, 'More actions')]")
MORE_BUTTON_ATTEMPTS = 3
# How long a profile page gets to render, and its More menu to open.
PROFILE_TIMEOUT_SECONDS = 20
MENU_TIMEOUT_SECONDS = 5


class SeleniumProfilePage(ClickMixin):
    def __init__(self, driver, pause):
        self.driver = driver
        self.pause = pause
        # How long a profile page gets to render, and its More menu to open.
        self.page_timeout = PROFILE_TIMEOUT_SECONDS
        self.menu_timeout = MENU_TIMEOUT_SECONDS

    def open(self, url):
        self.driver.get(url)

    def open_connect(self, full_name):
        """Click the Connect control for ``full_name`` on the open profile.

        Returns False when the profile never rendered or offers no Connect —
        not in its top card, not behind More.
        """
        if not self.wait_for_profile(full_name):
            return False
        # The actions have rendered by now, so a Connect in the top card is
        # already there to be found; anything else is behind the menu.
        control = self.find_profile_connect(full_name, timeout=0)
        if control is None:
            control = self.connect_from_more_menu(full_name)
        if control is None:
            logger.warning(
                f"No Connect action on {full_name}'s profile — not even "
                f"behind More. Skipping.")
            return False
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", control)
        except Exception:
            pass
        self.pause(2, 4)
        self._robust_click(control, f"Connect control on {full_name}'s profile")
        time.sleep(3)
        return True

    def find_everywhere(self, css):
        """Every element matching this CSS, document and shadow roots alike.

        LinkedIn renders its overlays — the invite modal, and the popover the
        More menu lives in — into an open Shadow DOM host, where a plain
        document query cannot see them.
        """
        found = []
        try:
            found.extend(self.driver.find_elements(By.CSS_SELECTOR, css))
        except Exception:
            pass
        for host_sel in ("#interop-outlet", "[data-testid='interop-shadowdom']"):
            try:
                hosts = self.driver.find_elements(By.CSS_SELECTOR, host_sel)
            except Exception:
                continue
            for host in hosts:
                try:
                    found.extend(host.shadow_root.find_elements(By.CSS_SELECTOR, css))
                except Exception:
                    continue
        return found

    def clickable_for(self, element):
        """The anchor or button that actually carries this control's action.

        A menu item labels its inner <div>, not the <a href="/preload/custom-
        invite/…"> around it. A real click on the div bubbles up to the
        anchor, but the JavaScript click at the bottom of the click ladder
        would not follow the link, so the anchor is what gets handed back.
        """
        try:
            found = element.find_elements(By.XPATH, CLICKABLE_XPATH)
        except Exception:
            return element
        return found[0] if found else element

    def find_profile_connect(self, full_name, timeout=None):
        """The 'Invite <full_name> to connect' control on the open profile.

        Matched by name on purpose: a profile page carries Connect buttons for
        *other* people too — the "More profiles for you" rail — and clicking
        one of those would send the invitation to the wrong person.
        """
        end = time.time() + (self.menu_timeout if timeout is None else timeout)
        while True:
            for control in self.find_everywhere(PROFILE_CONNECT_CSS):
                try:
                    if not control.is_displayed():
                        continue
                    label = control.get_attribute("aria-label") or ""
                except Exception:
                    continue
                if full_name and not same_person(
                        full_name_from_label(label), full_name):
                    continue
                return self.clickable_for(control)
            if time.time() >= end:
                return None
            time.sleep(0.3)

    def connect_in_open_menu(self):
        """The Connect item of whatever profile menu is open, found by place.

        Matching on the name is the safe search, but it leans on the card and
        the profile spelling that name the same way. Inside the person's own
        More menu there is only one person Connect can mean, so a Connect item
        there is taken even when the names did not line up — or when LinkedIn
        labelled the item with nothing at all and only its text says what it
        does.
        """
        for menu in self.find_everywhere(MENU_CSS):
            try:
                if not menu.is_displayed():
                    continue
            except Exception:
                continue

            try:
                labelled = menu.find_elements(By.CSS_SELECTOR, PROFILE_CONNECT_CSS)
            except Exception:
                labelled = []
            for control in labelled:
                try:
                    if control.is_displayed():
                        return self.clickable_for(control)
                except Exception:
                    continue

            try:
                items = menu.find_elements(By.CSS_SELECTOR, MENU_ITEM_CSS)
            except Exception:
                items = []
            for item in items:
                try:
                    if item.is_displayed() and (item.text or "").strip().casefold() == "connect":
                        return self.clickable_for(item)
                except Exception:
                    continue
        return None

    def close_open_menu(self):
        """Press Escape to close whatever dropdown is open."""
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        except Exception as e:
            logger.debug(f"Could not close the open menu: {type(e).__name__}: {e}")

    def connect_from_more_menu(self, full_name):
        """Open the profile's three-dots menu and return the Connect item in it.

        For someone you can only Follow, Connect is not in the top card at
        all — it lives one level down, behind More. The sticky header renders
        a second More button, so each one is tried in turn until a menu with
        Connect in it opens.
        """
        try:
            buttons = self.driver.find_elements(By.XPATH, MORE_BUTTON_XPATH)
        except Exception as e:
            logger.debug(f"Could not look for a More button: {type(e).__name__}: {e}")
            return None

        tried = 0
        for button in buttons:
            if tried >= MORE_BUTTON_ATTEMPTS:
                break
            try:
                if not button.is_displayed():
                    continue
            except Exception:
                continue
            tried += 1
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", button)
            except Exception:
                pass
            self.pause(2, 5)
            self._robust_click(button, f"More button on {full_name}'s profile")
            control = self.find_profile_connect(full_name)
            if control is None:
                control = self.connect_in_open_menu()
                if control is not None:
                    logger.info(
                        f"Taking Connect from the open menu on {full_name}'s "
                        f"profile — nothing on the page carries that name")
            if control is not None:
                return control
            logger.debug("That More menu holds no Connect; closing it")
            self.close_open_menu()

        return None

    def wait_for_profile(self, full_name, timeout=None):
        """Wait until the profile page has rendered its action buttons."""
        timeout = self.page_timeout if timeout is None else timeout
        end = time.time() + timeout
        while True:
            try:
                if (self.driver.find_elements(By.XPATH, MORE_BUTTON_XPATH)
                        or self.driver.find_elements(
                            By.CSS_SELECTOR, PROFILE_CONNECT_CSS)):
                    return True
            except Exception:
                pass
            if time.time() >= end:
                logger.warning(
                    f"{full_name}'s profile did not render its actions "
                    f"within {timeout}s")
                return False
            time.sleep(0.5)
