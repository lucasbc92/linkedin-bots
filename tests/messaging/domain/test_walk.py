"""What happens to one conversation card."""
import re
from datetime import date, datetime

from linkedin_bots.messaging.domain.past_sends import PastSend
from linkedin_bots.messaging.domain.routing import Routing, TemplateRoute
from linkedin_bots.messaging.domain.walk import ConversationCard, Send, Skip, Stop, assess

TODAY = date(2026, 10, 11)
ROUTING = Routing(default="DEFAULT", default_source="message.txt")


def _assess(card, history=None, handled=(), routing=ROUTING, **kw):
    return assess(card, history=history or {}, handled=set(handled), routing=routing,
                  today=TODAY, **kw)


def _card(name="Ana Silva", stamp="Oct 5", photo="P", pill=None, last="You: Saudações!"):
    return ConversationCard(name=name, stamp=stamp, photo=photo, pill=pill, last_message=last)


def test_a_new_contact_gets_the_default_template():
    verdict = _assess(_card())
    assert verdict == Send("DEFAULT", "message.txt", None, frozenset(), None)


def test_an_unreadable_name_is_skipped():
    assert _assess(_card(name=None)) == Skip("card has no readable name")


def test_a_pill_is_skipped_by_its_label():
    assert _assess(_card(pill="Sponsored")) == Skip("Sponsored")


def test_a_contact_already_handled_in_this_run_is_skipped():
    assert _assess(_card(), handled={("Ana Silva", "P")}) == Skip("already handled in this run")


def test_a_contact_messaged_before_is_skipped():
    history = {"Ana Silva": [PastSend(datetime(2026, 10, 9), photo="P")]}
    assert _assess(_card(), history=history) == Skip("already messaged in a previous run")


def test_a_namesake_after_a_name_only_send_is_flagged_as_different():
    history = {"Ana Silva": [PastSend(datetime(2026, 7, 25))]}
    verdict = _assess(_card(stamp="Oct 5", photo="Q"), history=history)
    assert isinstance(verdict, Send) and verdict.namesake == "different"


def test_a_namesake_with_a_recorded_thread_must_be_checked():
    history = {"Ana Silva": [PastSend(datetime(2026, 10, 1), photo="OLD", thread="2-a")]}
    verdict = _assess(_card(photo="NEW"), history=history)
    assert verdict.namesake == "maybe" and verdict.ruled_out == frozenset({"2-a"})


def test_no_matching_rule_names_every_pattern():
    routing = Routing(default="D", default_source="m.txt",
                      rules=(TemplateRoute(re.compile("^You: Hi"), "EN", "en.txt"),),
                      fallback=re.compile("^You: O"))
    assert _assess(_card(last="Ana: thanks"), routing=routing) == Skip(
        "last message matches no regex ('^You: Hi', '^You: O')")


def test_walking_down_stops_at_a_card_older_than_the_limit():
    verdict = _assess(_card(stamp="Sep 1"), date_limit=date(2026, 9, 15))
    assert verdict == Stop("Card for Ana Silva dated 2026-09-01 is before date limit "
                           "2026-09-15. Stopping.")


def test_walking_up_stops_at_a_card_newer_than_the_limit():
    verdict = _assess(_card(stamp="Oct 5"), date_limit=date(2026, 9, 15), upward=True)
    assert verdict == Stop("Card for Ana Silva dated 2026-10-05 is after date limit "
                           "2026-09-15. Stopping (inv).")


def test_an_undated_card_never_stops_the_walk():
    assert isinstance(_assess(_card(stamp=None), date_limit=date(2026, 9, 15)), Send)
