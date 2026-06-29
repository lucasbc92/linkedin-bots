"""LinkedIn's people-search results, as a Page Object.

The results are a virtualized LazyColumn inside the app shell's own scroll
container: only the rows near the scroll position exist in the DOM. The
scan drives that container to the end of the list before calling a page
done, and pages through the results by button or, when a reloaded page's
buttons ignore clicks, by the ``page=N`` URL parameter.
"""
import logging
import re
import time

from selenium.common.exceptions import (ElementClickInterceptedException,
                                        NoSuchElementException, TimeoutException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from linkedin_bots.connecting.adapters.selenium.profile_page import PROFILE_TIMEOUT_SECONDS
from linkedin_bots.connecting.application.ports import ClickIntercepted
from linkedin_bots.shared.infrastructure.clicking import ClickMixin
from linkedin_bots.shared.infrastructure.scrolling import (list_state, scroll_list_step,
                                                           scroll_list_to_top)

logger = logging.getLogger("linkedin_bot")

# The results are a virtualized LazyColumn: a page holds ten people but only
# the rows near the scroll position exist in the DOM, and they mount as the
# app shell's inner container scrolls (see common/scrolling.py). Scanning
# whatever is mounted and stopping there reads a page of Follow-only cards as
# an empty page, so the scan scrolls the list to its end before giving up.
RESULT_LIST = "[data-testid='lazy-column'], [data-component-type='LazyColumn']"
RESULT_CARD = "div[role='listitem']"
CONNECT_XPATH = ("//a[starts-with(@aria-label, 'Invite ') and "
                 "contains(@aria-label, 'to connect')]")
# Cards that offer only Follow. LinkedIn puts no Connect control on these in
# the results list, but the action still exists one level down, on the
# person's own profile, behind the three-dots More menu. Deliberately not
# scoped to the card markup — that changes shape between LinkedIn releases,
# while the label does not; the card is found by climbing afterwards.
FOLLOW_XPATH = ("//button[starts-with(@aria-label, 'Follow ')] | "
                "//a[starts-with(@aria-label, 'Follow ')]")
# Both kinds of person, as one list. An XPath union returns its matches in
# document order, so a single walk hands back the page's people in the order
# it shows them, each to be invited whichever way their own card allows.
TARGET_XPATH = CONNECT_XPATH + " | " + FOLLOW_XPATH
# The Connect control a card would have to carry for its Follow button to be
# the cheap way in; a card holding one is left to the normal route. Tag-free
# on purpose: it only has to notice the control, never click it.
CARD_INVITE_XPATH = ".//*[starts-with(@aria-label, 'Invite ')]"
# Ten results per page need three or four steps; the cap only exists so a
# list that somehow keeps growing cannot hold a run forever.
MOUNT_STEP_LIMIT = 30
# How long newly scrolled-to rows get to mount before they are counted.
MOUNT_SETTLE_SECONDS = 0.6
# How long a freshly navigated page gets to render its first card.
RESULTS_TIMEOUT_SECONDS = 20
# How long a page click, or a page loaded from the URL, gets to land.
PAGE_SWAP_TIMEOUT_SECONDS = 15


def page_url(url, page):
    """``url`` pointing at results page ``page``, adding ``page=`` if absent."""
    if re.search(r"[?&]page=\d+", url):
        return re.sub(r"([?&])page=\d+", rf"\g<1>page={page}", url)
    return f"{url}{'&' if '?' in url else '?'}page={page}"


class SeleniumSearchResults(ClickMixin):
    def __init__(self, driver, guard, pause, reverse=False):
        self.driver = driver
        self.guard = guard
        self.pause = pause
        self.reverse = reverse
        self.short_wait = WebDriverWait(driver, 3)
        # The results page last reloaded in place; its page buttons ignore
        # clicks, so it is left through the URL instead.
        self.reloaded_page = None
        # Not shrunk by --fast: how long the page needs to render.
        self.mount_settle = MOUNT_SETTLE_SECONDS
        self.page_timeout = PROFILE_TIMEOUT_SECONDS

    def results_url(self):
        try:
            return self.driver.current_url
        except Exception:
            return None

    def click_connect(self, control, label):
        """Click a card's Connect control and give the modal time to open."""
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", control)
            self.pause(2, 5)
            self._robust_click(control, f"Connect control ({label})")
        except ElementClickInterceptedException as e:
            raise ClickIntercepted(str(e)) from e
        time.sleep(3)

    #: Prefixes of the "Current: ... / Past: ..." snippet under a search result.
    _ROLE_SNIPPET_PREFIXES = ("current:", "past:", "atual:", "anterior:")

    def select_search_tab(self):
        """Switch to the LinkedIn people-search tab among all open tabs."""
        try:
            handles = self.driver.window_handles
        except Exception as e:
            logger.error(f"Could not enumerate browser tabs: {e}")
            return False

        people_search = None
        any_search = None
        for h in handles:
            try:
                self.driver.switch_to.window(h)
                url = (self.driver.current_url or "").lower()
            except Exception:
                continue
            if "linkedin.com/search/results/people" in url:
                people_search = h
                break
            if any_search is None and "linkedin.com/search/results" in url:
                any_search = h

        chosen = people_search or any_search
        if chosen is not None:
            self.driver.switch_to.window(chosen)
            logger.info(f"Using tab: {self.driver.current_url}")
            return True

        logger.warning("No LinkedIn people-search tab found. Using the current tab.")
        if handles:
            self.driver.switch_to.window(handles[0])
        return False

    def current_page_number(self):
        """The results page LinkedIn is showing, or None while it is swapping."""
        try:
            current = self.driver.find_element(
                By.XPATH, "//button[@aria-current='true']")
            return int(current.text.strip())
        except Exception:
            return None

    def go_to_page_by_url(self, target, timeout=PAGE_SWAP_TIMEOUT_SECONDS):
        """Load results page ``target`` through the URL; True once it shows."""
        try:
            self.driver.get(page_url(self.driver.current_url or "", target))
        except Exception as e:
            logger.warning(f"Could not load page {target} from the URL: {e}")
            return False

        end = time.time() + timeout
        while True:
            now = self.current_page_number()
            if now == target:
                return True
            if time.time() >= end:
                logger.warning(
                    f"Loading page {target} from the URL landed on page {now}")
                return False
            time.sleep(0.5)

    def go_to_next_page(self):
        """Navigate to the next or previous results page. Returns False when none available."""
        try:
            if not self.guard.check():
                return False

            direction = "prev" if self.reverse else "next"
            nav_xpath = f"//button[starts-with(@data-testid, 'pagination-controls-{direction}-button')]"
            nav_css = f"button[data-testid^='pagination-controls-{direction}-button']"

            nav_button = None
            try:
                nav_button = self.short_wait.until(
                    EC.presence_of_element_located((By.XPATH, nav_xpath)))
            except (TimeoutException, NoSuchElementException):
                nav_button = None

            if nav_button is None:
                for host in self.driver.find_elements(
                        By.CSS_SELECTOR, "#interop-outlet, [data-testid='interop-shadowdom']"):
                    try:
                        sr = host.shadow_root
                    except Exception:
                        continue
                    found = sr.find_elements(By.CSS_SELECTOR, nav_css)
                    if found:
                        nav_button = found[0]
                        break

            if nav_button is None:
                logger.info(f"No {'previous' if self.reverse else 'next'} page button found")
                return False

            testid = nav_button.get_attribute("data-testid") or ""
            if "hidden" in testid or nav_button.get_attribute("disabled"):
                logger.info(f"No more pages ({'previous' if self.reverse else 'next'} button disabled)")
                return False

            current = self.current_page_number()
            if self.reverse and current == 1:
                logger.info("Reached first page")
                return False
            if not self.reverse and current == 100:
                logger.info("Reached LinkedIn's page limit (100)")
                return False

            if current is not None and current == self.reloaded_page:
                target = current - 1 if self.reverse else current + 1
                logger.info(
                    f"Page {current} was reloaded and its page buttons ignore "
                    f"clicks; loading page {target} from the URL")
                return self.go_to_page_by_url(target)

            self.driver.execute_script("arguments[0].scrollIntoView(true);", nav_button)
            time.sleep(1)
            current_url = self.driver.current_url
            before = self.current_page_number()
            self._robust_click(nav_button)

            # Wait for the swap rather than guessing at it: LinkedIn empties
            # the list for a moment and then remounts it, so a fixed sleep
            # either wastes time or scans the outgoing page.
            end = time.time() + PAGE_SWAP_TIMEOUT_SECONDS
            while time.time() < end:
                time.sleep(0.5)
                if self.driver.current_url != current_url:
                    return True
                now = self.current_page_number()
                if now is not None and now != before:
                    return True

            # The button sometimes takes the click and does nothing (seen
            # right after a reload); the URL's page=N reaches the same page.
            if before is not None:
                target = before - 1 if self.reverse else before + 1
                logger.warning(
                    f"The {'previous' if self.reverse else 'next'} page button "
                    f"did not move off page {before}; loading page {target} "
                    f"from the URL instead")
                if self.go_to_page_by_url(target):
                    return True

            logger.warning(
                f"Could not move off page {before}. Stopping rather than "
                f"rescanning the same page.")
            return False

        except (TimeoutException, NoSuchElementException):
            logger.warning(f"No {'previous' if self.reverse else 'next'} page button or it's disabled")
            return False
        except Exception as e:
            logger.error(f"Error navigating page: {e}")
            return False

    def results_state(self):
        """Card count and scroll position of the results list."""
        return list_state(self.driver, RESULT_LIST, RESULT_CARD)

    def wait_for_results(self, timeout=RESULTS_TIMEOUT_SECONDS):
        """Park the results list at the top and wait for its first card.

        Returns the number of cards mounted, or 0 if the page never rendered
        any — which is a page worth retrying, not a page worth skipping.
        """
        end = time.time() + timeout
        while True:
            state = scroll_list_to_top(self.driver, RESULT_LIST, RESULT_CARD)
            if state.get("cards"):
                return state["cards"]
            if time.time() >= end:
                return 0
            time.sleep(0.5)

    def mount_more_results(self):
        """Scroll one step further down the list so more rows mount.

        Returns True while there is more of the page left to scan: either new
        rows appeared, or the scroller had not yet reached the bottom.
        """
        before = self.results_state()
        after = scroll_list_step(self.driver, RESULT_LIST, RESULT_CARD)
        if self.mount_settle:
            time.sleep(self.mount_settle)
            after = self.results_state()

        if after.get("cards", 0) > before.get("cards", 0):
            logger.debug(
                f"Mounted {after['cards'] - before['cards']} more result(s) "
                f"({after['cards']} on the page)")
            return True

        # The scroller moved, so rows that were out of view are now in it.
        if after.get("top") != before.get("top"):
            return True

        # Bottom reached with nothing new: give a slow render one last chance
        # before calling the page finished. Reading the count a beat too
        # early is exactly how rows used to go unseen.
        if self.mount_settle:
            time.sleep(self.mount_settle)
            if self.results_state().get("cards", 0) > after.get("cards", 0):
                return True

        return not after.get("atBottom", True)

    def needs_profile_detour(self, control):
        """Whether this Follow button is the only way in to its card's person.

        A Follow button outside a result card has no profile behind it to
        open, and a card that carries a Connect control as well is reachable
        without leaving the page at all.
        """
        card = self.find_result_card(control)
        if card is None:
            return False
        try:
            return not card.find_elements(By.XPATH, CARD_INVITE_XPATH)
        except Exception:
            return False

    def next_target(self, processed_labels, include_follow=True):
        """Return the next (control, aria-label, kind) this page has not handled.

        One walk covers the whole page, in the order it shows people: each is
        handed back with the route their own card allows — "connect" for the
        Invite control on the card, "follow" for someone who has to be invited
        from their profile instead.

        Scrolling is part of the search: LinkedIn mounts result rows lazily,
        so a scan that finds nothing among the mounted ones has to pull the
        rest of the list into the DOM before it can conclude the page is
        done. Returns (None, None, None) once the whole list has been walked.
        """
        xpath = TARGET_XPATH if include_follow else CONNECT_XPATH
        for _ in range(MOUNT_STEP_LIMIT):
            for control in self.driver.find_elements(By.XPATH, xpath):
                try:
                    label = control.get_attribute("aria-label")
                except Exception:
                    continue
                if not label or label in processed_labels:
                    continue
                if label.startswith("Invite "):
                    return control, label, "connect"
                if self.needs_profile_detour(control):
                    return control, label, "follow"

            if not self.mount_more_results():
                return None, None, None

        logger.warning(
            f"Gave up mounting this page after {MOUNT_STEP_LIMIT} scroll steps")
        return None, None, None

    def page_action_tally(self):
        """How this page's cards break down by the action they offer.

        A page with ten cards and no Connect control is a normal LinkedIn
        result — Follow-only and Message-only profiles cannot be invited from
        search — but it used to be indistinguishable from a page the bot had
        simply failed to read. Logging the split tells the two apart, and
        says how much of the page had to go the long way round.
        """
        js = (
            "/*linkedin-connect:tally*/"
            "const cards = [...document.querySelectorAll(arguments[0])];"
            "let connect = 0, follow = 0, message = 0, other = 0;"
            "for (const c of cards) {"
            "  if (c.querySelector(\"a[aria-label^='Invite ']\")) connect++;"
            "  else if (c.querySelector(\"button[aria-label^='Follow'], "
            "                           a[aria-label^='Follow']\")) follow++;"
            "  else if (c.querySelector(\"a[aria-label^='Send a message'], "
            "                           a[href*='messaging/compose']\")) message++;"
            "  else other++;"
            "}"
            "return {cards: cards.length, connect, follow, message, other};")
        try:
            tally = self.driver.execute_script(js, RESULT_CARD)
        except Exception as e:
            logger.debug(f"Could not tally page actions: {type(e).__name__}: {e}")
            return None
        return tally if isinstance(tally, dict) else None

    def results_page_is_restorable(self):
        """True when this results page can be left and then come back to.

        LinkedIn's search URL carries ``page=N``, so reloading it — or
        navigating away and stepping back — lands on the same page. On page 1
        the parameter is absent and a reload lands there anyway. Anywhere
        else without it, leaving would silently restart the run from the top.
        """
        page = self.current_page_number()
        try:
            url = self.driver.current_url or ""
        except Exception:
            url = ""
        return "page=" in url or page in (None, 1)

    def reload_results(self):
        """Reload this results page in place, keeping our spot in the pagination."""
        before = self.current_page_number()
        if not self.results_page_is_restorable():
            logger.debug(
                f"Not reloading page {before}: this URL does not carry the "
                f"page number, so a reload would restart from page 1")
            return False

        try:
            self.driver.refresh()
        except Exception as e:
            logger.warning(f"Could not reload the page: {e}")
            return False

        if not self.wait_for_results():
            return False

        after = self.current_page_number()
        if before is not None and after is not None and after != before:
            logger.warning(f"Reloading moved from page {before} to page {after}")
        self.reloaded_page = after if after is not None else before
        return True

    def await_results(self):
        """Make sure this page actually rendered its results before scanning.

        A page that renders nothing is a page the bot cannot read, and paging
        past it loses those people silently — the failure this whole scan
        path exists to stop. So an empty page is reloaded once, and if it is
        still empty the run stops loudly instead of walking on.
        """
        if self.wait_for_results():
            return True

        logger.warning("No results rendered on this page — reloading it once")
        if self.reload_results():
            logger.info("Results rendered after the reload")
            return True

        logger.error(
            "This page still shows no results after a reload. Stopping here "
            "rather than paging past people the bot never saw.")
        return False

    def find_result_card(self, connect_button):
        """Climb from a Connect control to the ancestor holding one profile.

        Stops one level below the ancestor that contains a *second* profile
        link, which is the result list itself — going that far would read the
        neighbouring person's headline.
        """
        card = None
        element = connect_button
        for _ in range(12):
            try:
                element = element.find_element(By.XPATH, "..")
            except Exception:
                break
            try:
                links = element.find_elements(
                    By.XPATH, ".//a[contains(@href, 'linkedin.com/in/')]")
            except Exception:
                continue
            hrefs = {(link.get_attribute("href") or "").split("?")[0].rstrip("/")
                     for link in links}
            hrefs.discard("")
            if len(hrefs) > 1:
                break
            if hrefs:
                card = element
        return card

    def extract_title_texts(self, connect_button):
        """Return the headline (and role snippet) shown on this person's card.

        Both are returned because LinkedIn does not always render a headline;
        when it is missing the "Current: Tech recruiter at X" snippet carries
        the same information.
        """
        card = self.find_result_card(connect_button)
        if card is None:
            return []

        headline = None
        snippet = None
        try:
            paragraphs = card.find_elements(By.XPATH, ".//p")
        except Exception:
            paragraphs = []

        for paragraph in paragraphs:
            try:
                text = paragraph.text.strip()
            except Exception:
                continue
            if not text:
                continue
            lowered = text.lower()
            if lowered.startswith(self._ROLE_SNIPPET_PREFIXES):
                if snippet is None:
                    snippet = text
                continue
            # The name paragraph wraps the profile link; skip it.
            try:
                if paragraph.find_elements(
                        By.XPATH, ".//a[contains(@href, 'linkedin.com/in/')]"):
                    continue
            except Exception:
                pass
            if headline is None:
                headline = text

        if headline is None and snippet is None:
            # Older markup renders the headline outside a <p>; fall back to the
            # card's rendered text, whose second line is the headline.
            try:
                lines = [ln.strip() for ln in card.text.splitlines() if ln.strip()]
            except Exception:
                lines = []
            if len(lines) > 1:
                headline = lines[1]

        return [text for text in (headline, snippet) if text]

    def profile_url_for(self, control):
        """The profile URL of the person whose result card holds this control."""
        card = self.find_result_card(control)
        links = []
        if card is not None:
            try:
                links = card.find_elements(By.XPATH, ".//a[contains(@href, '/in/')]")
            except Exception:
                links = []
        if not links:
            # Some card layouts wrap the whole row in the profile link itself,
            # so there is no descendant anchor to find — only an ancestor one.
            try:
                links = [control.find_element(
                    By.XPATH, "ancestor::a[contains(@href, '/in/')][1]")]
            except Exception:
                links = []

        for link in links:
            try:
                href = link.get_attribute("href") or ""
            except Exception:
                continue
            if "/in/" in href:
                # The person's own link always comes first in their card; the
                # ones after it belong to shared connections.
                return href.split("?")[0]
        return None

    def on_results_page(self):
        """Whether the browser is showing a search-results page right now."""
        try:
            return "/search/results" in (self.driver.current_url or "")
        except Exception:
            return False

    def return_to_results(self, results_url):
        """Step back from a profile onto the results page the detour left.

        Returns False when the results could not be restored, which ends the
        run — paging on from a page the bot cannot see loses everyone on it.
        """
        if self.on_results_page():
            # The detour never left: a profile that failed to open leaves the
            # results on screen, and stepping back from *there* would land on
            # the previous page of results and rescan the wrong people.
            return bool(self.await_results())

        try:
            self.driver.back()
        except Exception as e:
            logger.warning(f"Could not go back to the results: {e}")

        end = time.time() + self.page_timeout
        while True:
            if self.on_results_page():
                break
            if time.time() >= end:
                logger.warning(
                    "Going back did not land on the search results; opening "
                    "them again directly")
                try:
                    self.driver.get(results_url)
                except Exception as e:
                    logger.error(f"Could not reopen the results page: {e}")
                    return False
                break
            time.sleep(0.5)

        return bool(self.await_results())

    def detours_allowed(self):
        """Whether Follow-only people on this page may be invited via profile.

        The detour leaves the results page, so it is only on the table when
        coming back lands on the same page of results.
        """
        if self.results_page_is_restorable():
            return True
        logger.warning(
            "This results URL does not carry its page number, so leaving it "
            "for a profile would restart the run from page 1 — the "
            "Follow-only people on this page are left alone.")
        return False
