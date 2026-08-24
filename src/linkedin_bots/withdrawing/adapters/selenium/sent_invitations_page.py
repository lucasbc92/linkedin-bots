"""LinkedIn's sent-invitation manager, as a Page Object.

The page renders a LazyColumn: only the first page of invitations exists in
the DOM, and every further page is appended by a "Load more" button at the
bottom of the list (or, on some builds, by scrolling alone). Reaching the
oldest invitations means loading page after page until the list ends.
"""

import logging
import random
import time

from selenium.common.exceptions import StaleElementReferenceException

from linkedin_bots.shared.infrastructure.clicking import ClickMixin
from linkedin_bots.withdrawing.adapters.selenium.withdraw_dialog import WithdrawDialog
from linkedin_bots.withdrawing.application.ports import LoadResult, StaleListError
from linkedin_bots.withdrawing.domain.invitation import SentInvitation
from linkedin_bots.withdrawing.domain.sent_age import oldest_label

logger = logging.getLogger("linkedin_bot")

SENT_URL = "https://www.linkedin.com/mynetwork/invitation-manager/sent/"
# Selectors. LinkedIn's SDUI markup has hashed, per-build class names, so
# everything here anchors on roles, test ids and aria labels instead.
_LIST_CONTAINER = "div[data-testid='lazy-column'], [data-component-type='LazyColumn']"
# Card selectors from most to least specific. LinkedIn ships several SDUI
# builds; whichever one is live decides which of these matches, so the bot
# probes them at runtime instead of betting on one.
_CARD_SELECTORS = (
    "div[data-testid='lazy-column'] > div[role='listitem']",
    "[data-testid='lazy-column'] [role='listitem']",
    "[data-component-type='LazyColumn'] [role='listitem']",
    "div[role='listitem']",
)
_WITHDRAW_LINK = "a[aria-label^='Withdraw invitation sent to'], a[aria-label^='Retirar convite']"
# "Load more" carries no id and no stable class — it is found by its label.
# Both UI languages are accepted: the account language decides which shows.
_LOAD_MORE_LABELS = ("load more", "carregar mais", "ver mais", "mostrar mais")
# Anything LinkedIn might render "Load more" as — SDUI swaps between a real
# button and a div carrying role="button".
_CLICKABLE = "button, [role='button'], a[role='button']"
# Pull a card's age line out by wording. Cards carry the age *and* the
# invitation note, both as <p><span>, with the note last — so position is not
# a usable signal and the text itself has to be matched.
_AGE_FROM_CARD_JS = (
    "const AGE_RE = /^(sent|enviad)/i;"
    "const ageOf = (card) => {"
    "  const spans = [...card.querySelectorAll('p span, p, time')];"
    "  for (const el of spans) {"
    "    const t = (el.textContent || '').trim();"
    "    if (t && t.length < 60 && AGE_RE.test(t)) return t;"
    "  }"
    "  return null;"
    "};"
)
# The list lives inside LinkedIn's app shell, which scrolls an inner
# container rather than the document — window.scrollTo() moves nothing and the
# list never lazy-loads. This walks up from the list to whichever ancestor
# actually scrolls, then drives that one.
_SCROLLER_JS = (
    "const findScroller = (listSel) => {"
    "  const list = document.querySelector(listSel);"
    "  let el = list;"
    "  while (el && el !== document.body) {"
    "    const oy = getComputedStyle(el).overflowY;"
    "    if (/(auto|scroll|overlay)/.test(oy) && el.scrollHeight > el.clientHeight + 4)"
    "      return el;"
    "    el = el.parentElement;"
    "  }"
    "  return document.scrollingElement || document.documentElement;"
    "};"
    "const scrollBottom = (listSel, cardSel) => {"
    "  const s = findScroller(listSel);"
    "  if (s) s.scrollTop = s.scrollHeight;"
    "  window.scrollTo(0, document.body.scrollHeight);"
    "  const cards = document.querySelectorAll(cardSel);"
    "  const last = cards[cards.length - 1];"
    "  if (last) last.scrollIntoView({block: 'end'});"
    "  return s ? {tag: s.tagName, id: s.id || null,"
    "              cls: (s.className || '').toString().slice(0, 40),"
    "              scrollTop: Math.round(s.scrollTop),"
    "              scrollHeight: s.scrollHeight, clientHeight: s.clientHeight} : null;"
    "};"
)
# How long to wait for a clicked "Load more" to append its page.
GROWTH_TIMEOUT_SECONDS = 12
# How long a withdrawn card gets to disappear from the list.
REMOVAL_TIMEOUT_SECONDS = 10
# Gap between pages. Fast enough to walk ~1000 invitations, slow enough that
# the page settles and the request rate stays unremarkable.
PAGE_PAUSE_RANGE = (1.2, 2.4)
# Every loading budget below is counted in *pages*, not in clicks: some
# LinkedIn builds page on scroll alone, with no "Load more" button to click,
# and a budget that only counted clicks would never be spent on those — which
# is how a two-page top-up once expanded a 969-invitation list to its end.
#
# The in-page loader runs in chunks so the cutoff check stays in Python
# between them, instead of the date logic being duplicated in JavaScript.
JS_CHUNK_PAGES = 10
# …and a much smaller chunk when a stop condition is armed, so the loader
# overshoots the cutoff by at most a page or two rather than a full chunk.
JS_STOP_CHECK_PAGES = 2
JS_PAUSE_MS = 700


class SeleniumSentInvitationsPage(ClickMixin):
    def __init__(self, driver):
        self.driver = driver
        # Resolved against the live page on first use.
        self._card_sel = None
        self._tab_logged = False
        # Withdraw links of the last list read, by invitation key.
        self._links = {}
        self._dialog = WithdrawDialog(driver, self)

    def select_sent_tab(self):
        """Switch to the sent-invitation tab among all open tabs.

        Attaching to a running Chrome lands on whichever tab Selenium reports
        first, which is rarely the one the user is looking at. Both other bots
        pick their tab explicitly; without it this bot reads an unrelated
        page, counts zero cards and gives up.
        """
        try:
            handles = self.driver.window_handles
        except Exception as e:
            logger.error(f"Could not enumerate browser tabs: {e}")
            return False

        invitation_manager = None
        any_linkedin = None
        for h in handles:
            try:
                self.driver.switch_to.window(h)
                url = (self.driver.current_url or "").lower()
            except Exception:
                continue
            if "invitation-manager/sent" in url:
                invitation_manager = h
                break
            if any_linkedin is None and "linkedin.com" in url:
                any_linkedin = h

        chosen = invitation_manager or any_linkedin
        if chosen is not None:
            self.driver.switch_to.window(chosen)
            # A rolling run comes back here on every top-up; saying it once is
            # informative, saying it forty times buries the withdrawals.
            log = logger.debug if self._tab_logged else logger.info
            log(f"Using tab: {self.driver.current_url}")
            self._tab_logged = True
            return invitation_manager is not None

        logger.warning("No LinkedIn tab found. Using the current tab.")
        if handles:
            self.driver.switch_to.window(handles[0])
        return False

    def open(self):
        """Focus the sent-invitation tab, navigating there if none is open."""
        self.select_sent_tab()
        if "invitation-manager/sent" not in (self.driver.current_url or ""):
            logger.info(f"Opening {SENT_URL}")
            self.driver.get(SENT_URL)
            time.sleep(3)
        # The list mounts after the shell; give it a beat before counting.
        if not self.card_count():
            time.sleep(2)
            self._resolve_card_selector(force=True)

    def _resolve_card_selector(self, force=False):
        """Pick the card selector that actually matches the live page.

        Tries the candidates most-specific first and keeps the first one that
        matches anything, so a markup change costs a fallback rather than a
        silent zero-card run.
        """
        if self._card_sel and not force:
            return self._card_sel
        try:
            counts = self.driver.execute_script(
                "return arguments[0].map(s => document.querySelectorAll(s).length);",
                list(_CARD_SELECTORS)) or []
        except Exception as e:
            logger.debug(f"Selector probe failed: {type(e).__name__}: {e}")
            counts = []
        for sel, found in zip(_CARD_SELECTORS, counts):
            if found:
                if sel != self._card_sel:
                    logger.debug(f"Card selector: {sel} ({found} matched)")
                self._card_sel = sel
                return sel
        self._card_sel = _CARD_SELECTORS[0]
        return self._card_sel

    def card_count(self):
        """How many invitation cards are loaded, counted in the browser.

        Counting in JS rather than through ``find_elements`` keeps the growth
        check to one round-trip; with ~1000 cards loaded, materializing every
        WebElement on each poll costs whole seconds.
        """
        try:
            return self.driver.execute_script(
                "return document.querySelectorAll(arguments[0]).length;",
                self._resolve_card_selector()) or 0
        except Exception as e:
            logger.debug(f"Could not count cards: {type(e).__name__}: {e}")
            return 0

    def sent_labels(self):
        """Return the raw "Sent …" line of every loaded card, in list order.

        The age is matched by its wording, not by position. Taking the card's
        last text span instead picks up the invitation note ("Saudações,
        …!"), which every card with a note carries *below* the age — that
        misread every age as unparseable and made the whole list look
        ageless.
        """
        try:
            return self.driver.execute_script(
                _AGE_FROM_CARD_JS +
                "const out = [];"
                "document.querySelectorAll(arguments[0]).forEach(card => {"
                "  const age = ageOf(card);"
                "  if (age) out.push(age);"
                "});"
                "return out;",
                self._resolve_card_selector()) or []
        except Exception as e:
            logger.debug(f"Could not read sent labels: {type(e).__name__}: {e}")
            return []

    def loaded_invitations(self):
        """Every loaded invitation, newest first, as ``SentInvitation`` values.

        The withdraw links are remembered by key, so ``withdraw`` can click the
        one belonging to an invitation without handing elements upward.
        """
        try:
            rows = self.driver.execute_script(
                _AGE_FROM_CARD_JS +
                "const out = [];"
                "document.querySelectorAll(arguments[0]).forEach(card => {"
                "  const link = card.querySelector(arguments[1]);"
                "  if (!link) return;"
                "  const label = link.getAttribute('aria-label') || '';"
                "  out.push({"
                "    link: link,"
                "    name: label.replace(/^.*?(sent to|convite para)\\s*/i, '').trim(),"
                "    age: ageOf(card) || '',"
                "    key: link.getAttribute('componentkey') || label,"
                "  });"
                "});"
                "return out;",
                self._resolve_card_selector(), _WITHDRAW_LINK) or []
        except Exception as e:
            logger.warning(f"Could not read the invitation list: "
                           f"{type(e).__name__}: {e}")
            return []

        self._links = {}
        invitations = []
        for row in rows:
            invitation = SentInvitation(name=row.get("name") or "",
                                        age=row.get("age") or "",
                                        key=row.get("key") or "")
            self._links[invitation.key] = row.get("link")
            invitations.append(invitation)
        return invitations

    def probe(self):
        """Report what the live page exposes, selector by selector.

        A run that finds nothing looks identical whether the tab is wrong,
        the markup changed, or the list simply hasn't mounted. This prints
        the evidence for each so the next fix isn't a guess.
        """
        report = {}
        try:
            tabs = []
            for h in self.driver.window_handles:
                self.driver.switch_to.window(h)
                tabs.append(self.driver.current_url)
            report["tabs"] = tabs
        except Exception as e:
            report["tabs"] = f"unavailable: {type(e).__name__}: {e}"

        self.select_sent_tab()
        report["active tab"] = self.driver.current_url

        try:
            report["selector counts"] = dict(zip(
                _CARD_SELECTORS,
                self.driver.execute_script(
                    "return arguments[0].map(s => document.querySelectorAll(s).length);",
                    list(_CARD_SELECTORS)) or []))
            report["list containers"] = self.driver.execute_script(
                "return document.querySelectorAll(arguments[0]).length;",
                _LIST_CONTAINER)
            report["withdraw links"] = self.driver.execute_script(
                "return document.querySelectorAll(arguments[0]).length;",
                _WITHDRAW_LINK)
            report["buttons on page"] = self.driver.execute_script(
                "return [...document.querySelectorAll(\"button, [role='button']\")]"
                "  .map(b => ((b.innerText || b.textContent || '').trim() ||"
                "             (b.getAttribute('aria-label') || '').trim()))"
                "  .filter(Boolean).slice(-12);")
            report["page scrolls"] = self.driver.execute_script(
                "const e = document.scrollingElement || document.body;"
                "return {scrollHeight: e.scrollHeight, innerHeight: window.innerHeight};")
        except Exception as e:
            report["dom probe"] = f"failed: {type(e).__name__}: {e}"

        report["scroller (before)"] = self._scroll_list_bottom()
        time.sleep(2)
        report["scroller (after scroll)"] = self._scroll_list_bottom()
        report["cards after scrolling"] = self.card_count()
        report["load more found"] = self._find_load_more() is not None
        labels = self.sent_labels()
        report["sent labels"] = (labels[:3] + ["…"] + labels[-3:]
                                 if len(labels) > 6 else labels)

        print("\n--- withdraw bot probe ---")
        for key, value in report.items():
            if isinstance(value, (list, dict)) and value:
                print(f"{key}:")
                items = value.items() if isinstance(value, dict) else enumerate(value)
                for k, v in items:
                    print(f"    {k}: {v}" if isinstance(value, dict) else f"    {v}")
            else:
                print(f"{key}: {value}")
        print("--- end probe ---\n")
        return report

    def _scroll_list_bottom(self):
        """Scroll the real scroll container to the bottom of the list.

        Drives whichever ancestor actually scrolls, nudges the window, and
        pulls the last card into view — the list only mounts more rows once
        the bottom is genuinely reached.
        """
        try:
            info = self.driver.execute_script(
                _SCROLLER_JS + "return scrollBottom(arguments[0], arguments[1]);",
                _LIST_CONTAINER, self._resolve_card_selector())
            if info:
                logger.debug(
                    f"Scrolled {info.get('tag')}#{info.get('id') or '-'} to "
                    f"{info.get('scrollTop')}/{info.get('scrollHeight')} "
                    f"(viewport {info.get('clientHeight')})")
            return info
        except Exception as e:
            logger.debug(f"Scroll failed: {type(e).__name__}: {e}")
            return None

    def _find_load_more(self):
        """Return the "Load more" button element, or None when the list ends.

        Matched by visible label: the button has no id, no test id and only
        hashed class names, all of which change between LinkedIn builds.
        """
        try:
            return self.driver.execute_script(
                "const labels = arguments[0];"
                "const cands = [...document.querySelectorAll("
                "  \"button, [role='button'], a[role='button']\")];"
                "const text = el => ((el.innerText || el.textContent || '') + ' ' +"
                "  (el.getAttribute('aria-label') || '')).trim().toLowerCase();"
                "return cands.find(b => labels.includes(text(b)))"
                "  || cands.find(b => labels.some(l => text(b).includes(l)))"
                "  || null;",
                list(_LOAD_MORE_LABELS))
        except Exception as e:
            logger.debug(f"Could not locate 'Load more': {type(e).__name__}: {e}")
            return None

    def _wait_for_growth(self, previous, timeout=GROWTH_TIMEOUT_SECONDS):
        """Wait for the card count to exceed ``previous``; return the count."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            current = self.card_count()
            if current > previous:
                return current
            time.sleep(0.5)
        return self.card_count()

    def _page_pause(self):
        time.sleep(random.uniform(*PAGE_PAUSE_RANGE))

    def expand_in_page(self, max_pages=JS_CHUNK_PAGES, max_cards=None,
                       pause_ms=JS_PAUSE_MS,
                       growth_timeout_ms=GROWTH_TIMEOUT_SECONDS * 1000):
        """Run the load-more loop inside the page, in one round-trip.

        Each Selenium-driven page costs a scroll, an element lookup, a click
        and a polling loop across the wire; in the browser the same work is a
        ``setTimeout`` chain, which walks a thousand invitations in a fraction
        of the time. It runs in bounded chunks so the cutoff check stays on
        the Python side, where the date logic lives.

        The catch is that ``btn.click()`` fires an untrusted event, which
        LinkedIn ignores on some controls — hence ``scroll_to_end``'s fallback
        to the trusted-click ladder the moment a chunk stops making progress.

        Scrolling comes first and clicking second: the "Load more" button is
        mounted lazily at the bottom of the list, so on a freshly opened page
        it does not exist until the scroller actually reaches the end. A pass
        that only looked for the button therefore saw an empty page-one list
        and reported the end of a 969-invitation list after one second.
        Growth from scrolling alone also counts as progress, since some
        builds page on scroll with no button at all.

        ``max_cards`` is checked in the browser, before each page load, so
        a card cap stops mid-chunk instead of overshooting by the rest of it.

        ``max_pages`` counts pages that actually arrived, from a click or
        from scrolling — the loop below spends its budget on growth, not on
        button presses, because a build that pages on scroll alone never
        presses one.

        Returns ``{"cards": n, "pages": n, "scrolls": n, "reason": …}``, or
        None when the script itself failed. ``reason`` is one of
        ``chunk-done`` (budget spent), ``cap`` (max_cards reached), ``end``
        (nothing left to load) or ``stalled`` (clicked, nothing loaded).
        """
        script = (
            _SCROLLER_JS +
            "const [cardSel, listSel, btnSel, labels, maxPages, maxCards,"
            "       pauseMs, growthTimeout, done] = arguments;"
            "const count = () => document.querySelectorAll(cardSel).length;"
            "const text = el => ((el.innerText || el.textContent || '') + ' ' +"
            "  (el.getAttribute('aria-label') || '')).trim().toLowerCase();"
            "const findBtn = () => {"
            "  const cands = [...document.querySelectorAll(btnSel)]"
            "    .filter(b => b.offsetParent !== null);"
            "  return cands.find(b => labels.includes(text(b)))"
            "    || cands.find(b => labels.some(l => text(b).includes(l)))"
            "    || null;"
            "};"
            "let pages = 0, scrolls = 0, idle = 0;"
            "const finish = (reason) => done({cards: count(), pages, scrolls, reason});"
            "const step = () => {"
            "  if (maxCards && count() >= maxCards) return finish('cap');"
            "  if (pages >= maxPages) return finish('chunk-done');"
            "  const before = count();"
            "  scrollBottom(listSel, cardSel);"
            "  scrolls++;"
            "  const btn = findBtn();"
            "  if (btn) {"
            "    idle = 0;"
            "    btn.scrollIntoView({block: 'end'});"
            "    btn.click();"
            "  }"
            "  const deadline = Date.now() + (btn ? growthTimeout : 2500);"
            "  const waitGrow = () => {"
            # A page is a page: however it arrived, it costs one budget.
            "    if (count() > before) {"
            "      idle = 0; pages++;"
            "      return setTimeout(step, pauseMs);"
            "    }"
            "    if (Date.now() > deadline) {"
            "      if (btn) return finish('stalled');"
            "      idle++;"
            # Three scrolls with no button and no new rows: the list is out.
            "      return idle >= 3 ? finish('end') : setTimeout(step, 400);"
            "    }"
            "    setTimeout(waitGrow, 250);"
            "  };"
            "  setTimeout(waitGrow, 250);"
            "};"
            "step();"
        )
        budget = max_pages * (growth_timeout_ms + pause_ms) / 1000 + 30
        try:
            self.driver.set_script_timeout(budget)
            return self.driver.execute_async_script(
                script, self._resolve_card_selector(), _LIST_CONTAINER,
                _CLICKABLE, list(_LOAD_MORE_LABELS), max_pages,
                max_cards or 0, pause_ms, growth_timeout_ms)
        except Exception as e:
            logger.warning(f"In-page expansion failed ({type(e).__name__}: {e}); "
                           f"falling back to trusted clicks.")
            return None

    def load(self, max_pages=None, max_cards=None, stop_when=None,
                      use_js=True):
        """Load invitation pages until the oldest one is in the DOM.

        Clicks "Load more" repeatedly, scrolling it into view each time, and
        stops at the first of: the button disappearing (true end of the
        list), the list refusing to grow, ``max_pages`` or ``max_cards``
        reached, or ``stop_when`` returning True.

        Args:
            max_pages: Cap on pages loaded. ``None`` = unlimited. With ~1000
                       invitations the fully expanded DOM gets heavy, so cap
                       it when only recent pages are needed. A page counts
                       however it arrived: some builds have no "Load more"
                       button at all and page on scroll instead.
            max_cards: Cap on loaded invitation cards — the same bound as
                       max_pages, expressed in the unit the caller actually
                       cares about. ``None`` = unlimited.
            stop_when: Callable taking the list of raw "Sent …" labels (list
                       order, newest first) and returning True to stop early
                       — e.g. once a card older than the cutoff date has
                       appeared, there is no reason to keep loading.
            use_js: Load pages with the in-page loop (fast), dropping to the
                    trusted-click ladder the first time a chunk stalls.
                    False forces the slow path from the start.

        Returns a LoadResult: the number of invitation cards loaded, and
        whether the list has nothing left to load.
        """
        self.open()

        count = self.card_count()
        if not count:
            logger.warning(
                "No invitation cards found — is the Sent tab open and loaded?")
            return LoadResult(0, exhausted=True)

        logger.info(f"{count} invitation(s) loaded; expanding the list …")
        pages = 0

        while True:
            if max_cards is not None and count >= max_cards:
                logger.info(
                    f"Reached the {max_cards}-invitation load limit with "
                    f"{count} loaded "
                    f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
                return LoadResult(count, exhausted=False)

            if stop_when is not None and stop_when(self.sent_labels()):
                logger.info(
                    f"Stop condition met with {count} invitation(s) loaded "
                    f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
                return LoadResult(count, exhausted=False)

            if max_pages is not None and pages >= max_pages:
                logger.info(
                    f"Reached the {max_pages}-page limit with {count} "
                    f"invitation(s) loaded.")
                return LoadResult(count, exhausted=False)

            if use_js:
                # The in-page loop can't evaluate the cutoff (the date logic
                # lives in Python), so a stop condition is only seen between
                # chunks. Ten pages per chunk means overshooting the cutoff by
                # up to ten page loads — on a slow list that reads as "it
                # never stops". Shrink the chunk whenever something is
                # waiting to stop it.
                budget = JS_STOP_CHECK_PAGES if stop_when else JS_CHUNK_PAGES
                if max_pages is not None:
                    budget = min(budget, max_pages - pages)
                result = self.expand_in_page(max_pages=budget,
                                             max_cards=max_cards)
                if result is None:
                    use_js = False
                    continue

                pages += result.get("pages", 0)
                grown = result.get("cards", count)
                if grown > count:
                    count = grown
                    logger.info(
                        f"{count} invitation(s) loaded — {pages} page(s), "
                        f"{result.get('scrolls', 0)} scroll(s) this chunk "
                        f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")

                reason = result.get("reason")
                if reason == "cap":
                    logger.info(
                        f"Reached the {max_cards}-invitation load limit with "
                        f"{count} loaded "
                        f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
                    return LoadResult(count, exhausted=False)
                if reason == "end":
                    logger.info(
                        f"End of the list: {count} invitation(s) loaded "
                        f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
                    return LoadResult(count, exhausted=True)
                if reason == "stalled":
                    # An untrusted click LinkedIn ignored, or a genuinely
                    # exhausted list — the ladder below tells them apart.
                    logger.info(
                        "In-page loop stopped making progress; switching to "
                        "trusted clicks.")
                    use_js = False
                continue

            self._scroll_list_bottom()
            button = self._find_load_more()
            if button is None:
                # "Load more" is mounted lazily at the bottom of the list, so
                # on a page that has only ever shown its first rows it does
                # not exist yet. Scroll, settle, look again — and if the list
                # grew from the scrolling alone, that was the page load.
                self._page_pause()
                self._scroll_list_bottom()
                grown = self._wait_for_growth(count, timeout=4)
                if grown > count:
                    # No button was pressed, but a page arrived all the same;
                    # not counting it here is what let a bounded run walk the
                    # whole list.
                    pages += 1
                    count = grown
                    logger.info(
                        f"{count} invitation(s) loaded by scrolling — "
                        f"{pages} page(s) "
                        f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
                    continue
                button = self._find_load_more()
            if button is None:
                logger.info(
                    f"End of the list: {count} invitation(s) loaded "
                    f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
                return LoadResult(count, exhausted=True)

            try:
                clicked = self._robust_click(button, "'Load more'")
            except StaleElementReferenceException:
                # The list re-rendered under us; the next pass re-finds it.
                logger.debug("'Load more' went stale; retrying.")
                continue
            if not clicked:
                logger.warning(
                    f"Could not click 'Load more'; stopping with {count} "
                    f"invitation(s) loaded.")
                return LoadResult(count, exhausted=True)

            pages += 1
            grown = self._wait_for_growth(count)
            if grown <= count:
                logger.warning(
                    f"'Load more' clicked but the list stayed at {count} "
                    f"invitation(s); stopping.")
                return LoadResult(count, exhausted=True)

            logger.info(
                f"Page {pages}: {grown} invitation(s) loaded "
                f"(oldest: {oldest_label(self.sent_labels()) or 'unknown'}).")
            count = grown
            self._page_pause()

    def withdraw(self, invitation):
        """Withdraw one invitation. Returns True when its card is gone."""
        name = invitation.name or "(unknown)"
        age = invitation.age or "unknown age"
        link = self._links.get(invitation.key)
        if link is None:
            logger.warning(f"Could not click withdraw for {name}.")
            return False

        try:
            if not self._robust_click(link, f"withdraw ({name})"):
                logger.warning(f"Could not click withdraw for {name}.")
                return False

            if not self._dialog.confirm(name):
                # Either no dialog appeared or it was for someone else. Both
                # leave the click unfinished; clear anything still open so the
                # next card isn't blocked by a modal.
                self._dialog.dismiss()
                logger.warning(f"Withdrawal of {name} was not confirmed. Skipping.")
                return False

            if not self._wait_card_gone(invitation.key):
                logger.warning(
                    f"Withdrawal of {name} did not take — the card is still "
                    f"listed. Moving on.")
                self._dialog.dismiss()
                return False
        except StaleElementReferenceException as e:
            raise StaleListError(str(e)) from e

        logger.info(f"Withdrew: {name} — {age}")
        return True

    def _wait_card_gone(self, key, timeout=REMOVAL_TIMEOUT_SECONDS):
        """True once the card with this ``componentkey`` has left the DOM."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                still_there = self.driver.execute_script(
                    "const key = arguments[0];"
                    "return [...document.querySelectorAll(arguments[1])].some("
                    "  a => (a.getAttribute('componentkey') || "
                    "        a.getAttribute('aria-label')) === key);",
                    key, _WITHDRAW_LINK)
            except Exception:
                return True
            if not still_there:
                return True
            time.sleep(0.4)
        return False
