"""Hand-built LinkedIn pages for the connecting Page Object tests.

A tiny DOM (``Node``) answers the XPath and CSS subsets the Page Objects
use; ``FakeBrowser`` serves a virtualized results list and profile pages
from it, standing in for the Selenium driver.
"""
import re

from selenium.webdriver.common.by import By

from linkedin_bots.connecting.adapters.selenium import profile_page as profile_module
from linkedin_bots.connecting.adapters.selenium import search_results_page as results_module
from linkedin_bots.connecting.adapters.selenium.profile_page import SeleniumProfilePage
from linkedin_bots.connecting.adapters.selenium.search_results_page import SeleniumSearchResults

VIEWPORT = 520
CARD_HEIGHT = 120
MOUNT_CHUNK = 3


# --------------------------------------------------------------------------
# A DOM small enough to read, real enough to climb
# --------------------------------------------------------------------------

_STEP = re.compile(r"^(?P<axis>\.//|//|ancestor-or-self::|ancestor::)?"
                   r"(?P<tag>[a-z*]+)(?P<preds>(\[[^]]*\])*)$")
_PRED = re.compile(r"\[([^]]*)\]")
_CALL = re.compile(r"(contains|starts-with)\(@([\w-]+), '([^']*)'\)")
_SELF = re.compile(r"self::(\w+)")


class Node:
    """A DOM node that answers the handful of queries the bot actually uses."""

    def __init__(self, tag, children=(), text="", **attrs):
        self.tag = tag
        self.attrs = {k.replace("_", "-"): v for k, v in attrs.items()}
        self.parent = None
        self.own_text = text
        self.displayed = self.attrs.pop("displayed", True)
        self.children = []
        for child in children:
            self.append(child)

    def append(self, child):
        child.parent = self
        self.children.append(child)
        return self

    # -- what Selenium exposes -----------------------------------------
    @property
    def text(self):
        """Selenium's .text is the whole subtree's rendered text."""
        parts = [self.own_text] + [n.own_text for n in self._descendants()]
        return " ".join(part for part in parts if part).strip()

    def get_attribute(self, name):
        return self.attrs.get(name)

    def is_displayed(self):
        return self.displayed

    def is_enabled(self):
        return True

    def find_elements(self, by, selector):
        if by == By.CSS_SELECTOR:
            return [n for n in self._descendants() if css_matches(n, selector)]
        return self._select(selector)

    def find_element(self, by, selector):
        found = self.find_elements(by, selector)
        if not found:
            raise LookupError(selector)
        return found[0]

    # -- the mini XPath engine -----------------------------------------
    def _descendants(self):
        for child in self.children:
            yield child
            yield from child._descendants()

    def _ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def _pool(self, axis):
        if axis == "ancestor::":
            return list(self._ancestors())
        if axis == "ancestor-or-self::":
            return [self] + list(self._ancestors())
        return list(self._descendants())

    def _select(self, xpath):
        found = []
        for step in xpath.split(" | "):
            step = step.strip()
            if step == "..":
                if self.parent is not None:
                    found.append(self.parent)
                continue
            match = _STEP.match(step)
            assert match, f"unsupported xpath: {step}"
            tag = match.group("tag")
            preds = _PRED.findall(match.group("preds") or "")
            hits = [n for n in self._pool(match.group("axis"))
                    if (tag == "*" or n.tag == tag) and n._matches(preds)]
            found.extend(hits[:1] if any(p.isdigit() for p in preds) else hits)
        return found

    def _matches(self, preds):
        for pred in preds:
            if pred.isdigit():
                continue
            if "self::" in pred:
                if self.tag not in _SELF.findall(pred):
                    return False
                continue
            for term in pred.split(" and "):
                call = _CALL.match(term.strip())
                assert call, f"unsupported predicate: {term}"
                fn, attr, value = call.groups()
                actual = self.attrs.get(attr) or ""
                if fn == "contains" and value not in actual:
                    return False
                if fn == "starts-with" and not actual.startswith(value):
                    return False
        return True


_CSS_GROUP = re.compile(r"^(?P<tag>[a-z*]*)(?P<attrs>(\[[^]]*\])*)$")
_CSS_ATTR = re.compile(r"^([\w-]+)(?:([~^*$]?=)'([^']*)')?$")


def css_matches(node, selector):
    """Does this node match the selector? Enough CSS for what the bot runs:
    comma-separated groups of an optional tag name and attribute tests.

    Parsed rather than looked up, so that changing a selector in the bot
    changes what these tests see — a selector that stops matching LinkedIn's
    markup has to fail a test, not quietly match nothing.
    """
    for group in selector.split(","):
        match = _CSS_GROUP.match(group.strip())
        assert match, f"unsupported css: {group}"
        tag = match.group("tag")
        if tag and tag != "*" and node.tag != tag:
            continue
        if all(_css_attr_matches(node, test)
               for test in _PRED.findall(match.group("attrs") or "")):
            return True
    return False


def _css_attr_matches(node, test):
    match = _CSS_ATTR.match(test)
    assert match, f"unsupported css attribute test: {test}"
    name, operator, value = match.groups()
    actual = node.attrs.get(name)
    if actual is None:
        return False
    if operator is None:
        return True
    if operator == "=":
        return actual == value
    if operator == "^=":
        return actual.startswith(value)
    if operator == "*=":
        return value in actual
    raise AssertionError(f"unsupported css operator: {operator}")


def menu_item(text, **attrs):
    """A plain item of a profile's More menu."""
    return Node("a", [Node("div", [Node("p", text=text)])],
                role="menuitem", href="https://www.linkedin.com/in/someone/",
                **attrs)


def connect_menu_item(name):
    """The Connect item as LinkedIn actually renders it.

    The <a> carries the link and the menuitem role; the label naming the
    person sits on a *div inside it*, which is why looking for an <a> or a
    <button> with that label came up empty.
    """
    label = Node("div", [Node("div", [Node("p", text="Connect")])],
                 **({"aria_label": f"Invite {name} to connect"} if name else {}))
    return Node("a", [label], role="menuitem",
                href="/preload/custom-invite/?vanityName=x")


def top_card_connect(name):
    """The Connect control in a profile's top card, which is labelled itself."""
    return Node("a", [Node("span", text="Connect")],
                aria_label=f"Invite {name} to connect",
                href="/preload/custom-invite/?vanityName=x")


def result_card(name, action, headline="Tech Recruiter", mutuals=()):
    """One search result, shaped like LinkedIn's: the row is itself a link to
    the profile, the person's own name link comes first, and any shared
    connections are linked further down."""
    url = f"https://www.linkedin.com/in/{name.lower().replace(' ', '-')}/"
    if action == "connect":
        control = Node("a", aria_label=f"Invite {name} to connect",
                       href="/preload/custom-invite/")
    else:
        control = Node("button", aria_label=f"Follow {name}")

    card = Node("div", [
        Node("p", [Node("a", href=url)]),
        Node("p", [Node("span")]),
        Node("div", [control]),
    ])
    row = Node("a", [card], href=url)
    for mutual in mutuals:
        row.append(Node("p", [Node("a", href=f"https://www.linkedin.com/in/{mutual}/")]))
    return Node("div", [row], role="listitem"), control, url


class FakeResults:
    """A virtualized results list: rows mount as the scroller reaches them."""

    def __init__(self, cards, mounted=None):
        self.cards = list(cards)
        self.mounted = len(self.cards) if mounted is None else mounted
        self.scroll_top = 0

    @property
    def height(self):
        return self.mounted * CARD_HEIGHT

    @property
    def at_bottom(self):
        return self.scroll_top + VIEWPORT >= self.height - 8

    def state(self):
        return {"cards": self.mounted, "top": round(self.scroll_top),
                "height": self.height, "view": VIEWPORT,
                "atBottom": self.at_bottom}

    def scroll_to_top(self):
        self.scroll_top = 0
        return self.state()

    def scroll_step(self, fraction):
        self.scroll_top = min(self.scroll_top + VIEWPORT * fraction,
                              max(self.height - VIEWPORT, 0))
        if self.at_bottom:
            self.mounted = min(self.mounted + MOUNT_CHUNK, len(self.cards))
        return self.state()

    def tally(self):
        """What page_action_tally() reports for the mounted rows."""
        counts = {"cards": 0, "connect": 0, "follow": 0, "message": 0, "other": 0}
        for row, _control, _url in self.cards[:self.mounted]:
            counts["cards"] += 1
            if row._select(".//a[starts-with(@aria-label, 'Invite ')]"):
                counts["connect"] += 1
            elif row._select(".//button[starts-with(@aria-label, 'Follow ')]"):
                counts["follow"] += 1
            else:
                counts["other"] += 1
        return counts

    def controls(self, xpath):
        found = []
        for row, _control, _url in self.cards[:self.mounted]:
            found.extend(row._select(xpath.replace("//", ".//")))
        return found


class FakeProfile:
    """A profile page: its top card, its rail, and the menu More opens.

    ``menu_connect`` says how the open menu offers Connect:
      ``"labelled"``   — the item LinkedIn ships, whose inner div carries
                         "Invite <name> to connect";
      ``"unlabelled"`` — the same item with no aria-label anywhere, so only
                         the word Connect in its text says what it does;
      ``None``         — the menu has no Connect in it at all.
    """

    def __init__(self, name, connect_in_top_card=False,
                 menu_connect="labelled", rail=("Someone Else",),
                 more_buttons=2):
        self.name = name
        self.menu_connect = menu_connect
        self.more_clicks = 0
        self.menu = None
        self.more_buttons = [Node("button", aria_label="More")
                             for _ in range(more_buttons)]
        self.own_connect = (top_card_connect(name) if connect_in_top_card
                            else None)
        # Every profile page also carries Connect buttons for other people.
        self.rail = [top_card_connect(other) for other in rail]

    def click_more(self):
        self.more_clicks += 1
        items = [menu_item("Send profile in a message"), menu_item("Save to PDF")]
        if self.menu_connect:
            items.append(connect_menu_item(
                self.name if self.menu_connect == "labelled" else None))
        items.append(menu_item(f"Report {self.name.split()[0]}"))
        self.menu = Node("div", items, role="menu")

    def menus(self):
        return [self.menu] if self.menu is not None else []

    def connect_controls(self):
        """Everything on the page that PROFILE_CONNECT_CSS matches."""
        found = list(self.rail)
        if self.own_connect is not None:
            found.insert(0, self.own_connect)
        if self.menu is not None:
            found.extend(self.menu.find_elements(
                By.CSS_SELECTOR, profile_module.PROFILE_CONNECT_CSS))
        return found


class FakeBrowser:
    """Answers only the queries the detour issues."""

    def __init__(self, results, profiles=None,
                 url="https://www.linkedin.com/search/results/people/?page=7",
                 page_number=7, back_lands_on_results=True, on_refresh=None):
        self.results = results
        self.profiles = profiles or {}
        self.results_url = url
        self.current_url = url
        self.page_number = page_number
        self.back_lands_on_results = back_lands_on_results
        self.on_refresh = on_refresh
        self.refreshed = 0
        self.visited = []
        self.backs = 0
        self.clicked = []

    # -- navigation -----------------------------------------------------
    @property
    def profile(self):
        return self.profiles.get(self.current_url)

    def get(self, url):
        self.visited.append(url)
        self.current_url = url

    def click(self, element):
        """Clicking More on a profile is what opens its menu."""
        self.clicked.append(element.get_attribute("aria-label"))
        if self.profile is not None and element in self.profile.more_buttons:
            self.profile.click_more()
        return True

    def back(self):
        self.backs += 1
        if self.back_lands_on_results:
            self.current_url = self.results_url

    def refresh(self):
        self.refreshed += 1
        self.results.mounted = min(4, len(self.results.cards))
        self.results.scroll_top = 0
        if self.on_refresh:
            self.on_refresh(self)

    # -- queries --------------------------------------------------------
    def execute_script(self, script, *args):
        if "linkedin-scroll:state" in script:
            return self.results.state()
        if "linkedin-scroll:top" in script:
            return self.results.scroll_to_top()
        if "linkedin-scroll:step" in script:
            return self.results.scroll_step(args[-1])
        if "linkedin-connect:tally" in script:
            return self.results.tally()
        if "scrollIntoView" in script:
            return None
        raise AssertionError(f"unexpected script: {script[:60]}")

    def find_elements(self, by, selector):
        if by == By.XPATH and selector in (results_module.TARGET_XPATH,
                                           results_module.CONNECT_XPATH,
                                           results_module.FOLLOW_XPATH):
            return self.results.controls(selector)
        if by == By.XPATH and selector == profile_module.MORE_BUTTON_XPATH:
            return self.profile.more_buttons if self.profile else []
        if by == By.CSS_SELECTOR and selector == profile_module.PROFILE_CONNECT_CSS:
            return self.profile.connect_controls() if self.profile else []
        if by == By.CSS_SELECTOR and selector == profile_module.MENU_CSS:
            return self.profile.menus() if self.profile else []
        if by == By.CSS_SELECTOR and "interop" in selector:
            return []
        raise AssertionError(f"unexpected find_elements: {selector}")

    def find_element(self, by, selector):
        if "aria-current" in selector:
            if self.page_number is None:
                raise LookupError("no current page button")
            return Node("button", text=str(self.page_number))
        raise AssertionError(f"unexpected find_element: {selector}")


class PassGuard:
    """A limit guard that never sees a limit."""

    def check(self):
        return True

    def rate_limited(self):
        return False


def results_page(browser, reverse=False):
    page = SeleniumSearchResults(browser, guard=PassGuard(), pause=lambda *_: None,
                                 reverse=reverse)
    page.mount_settle = 0
    page.page_timeout = 0
    page._robust_click = lambda element, description="element": browser.click(element)
    return page


def profile_page(browser):
    page = SeleniumProfilePage(browser, pause=lambda *_: None)
    page.page_timeout = 0
    page.menu_timeout = 0
    page._robust_click = lambda element, description="element": browser.click(element)
    return page
