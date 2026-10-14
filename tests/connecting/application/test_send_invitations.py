"""The invitation walk, against in-memory pages."""
import logging

import pytest

from linkedin_bots.connecting.application.ports import (ClickIntercepted, InviteResult,
                                                        InviteStatus)
from linkedin_bots.connecting.application.send_invitations import (InviteSettings,
                                                                   SendInvitations)
from linkedin_bots.connecting.domain.audiences import JAVA_DEVS
from linkedin_bots.shared.domain.messages import MessageTemplates


class Results:
    """A page of people, each ("Invite X to connect" | "Follow X", headline)."""

    def __init__(self, people, pages=1, on_reload=None, restorable=True, back_ok=True,
                 intercept=()):
        self.people = list(people)
        self.intercept = set(intercept)
        self.pages_left = pages - 1
        self.on_reload = on_reload
        self.restorable = restorable
        self.back_ok = back_ok
        self.reloads = 0
        self.clicked = []
        self.returns = 0

    def select_search_tab(self):
        return True

    def await_results(self):
        return True

    def detours_allowed(self):
        return self.restorable

    def results_url(self):
        return "https://www.linkedin.com/search/results/people/?page=7"

    def next_target(self, processed, include_follow=True):
        for label, _headline in self.people:
            if label in processed:
                continue
            if label.startswith("Invite "):
                return label, label, "connect"
            if include_follow:
                return label, label, "follow"
        return None, None, None

    def page_action_tally(self):
        connect = sum(1 for label, _ in self.people if label.startswith("Invite "))
        return {"cards": len(self.people), "connect": connect,
                "follow": len(self.people) - connect, "message": 0, "other": 0}

    def reload_results(self):
        self.reloads += 1
        if self.on_reload:
            self.on_reload(self)
        return True

    def extract_title_texts(self, control):
        return [headline for label, headline in self.people if label == control and headline]

    def click_connect(self, control, label):
        if label in self.intercept:
            raise ClickIntercepted("covered")
        self.clicked.append(label)

    def profile_url_for(self, control):
        return f"https://www.linkedin.com/in/{control.split()[1].lower()}/"

    def return_to_results(self, url):
        self.returns += 1
        return self.back_ok

    def go_to_next_page(self):
        if self.pages_left <= 0:
            return False
        self.pages_left -= 1
        return True


class Profile:
    def __init__(self, has_connect=True):
        self.has_connect = has_connect
        self.opened = []

    def open(self, url):
        self.opened.append(url)

    def open_connect(self, full_name):
        return self.has_connect


class Modal:
    def __init__(self, status=InviteStatus.SENT):
        self.status = status
        self.notes = []
        self.dismissed = 0

    def complete(self, target_label, name, note):
        self.notes.append(note(name) if note else None)
        return InviteResult(self.status, name)

    def dismiss_open_modal(self):
        self.dismissed += 1


class Guard:
    def __init__(self, ok=True):
        self.ok = ok

    def check(self):
        return self.ok


class Ledger:
    def __init__(self):
        self.recorded = []

    def record(self, name):
        self.recorded.append(name)

    def count_for_week(self, week=None):
        return 195


TECH = "Tech Recruiter"
NOTE = MessageTemplates(["Olá, {name}!"], max_length=300)


def _run(results, profile=None, modal=None, guard=None, ledger=None, max_pages=100, **settings):
    use_case = SendInvitations(results, profile or Profile(), modal or Modal(), guard or Guard(),
                               ledger or Ledger(), lambda low, high: None, NOTE,
                               InviteSettings(**settings))
    use_case.run(max_pages=max_pages)
    return use_case


def test_both_routes_are_taken_on_one_page():
    results = Results([("Invite Ana Lima to connect", TECH), ("Follow Bia Souza", TECH),
                       ("Invite Caio Reis to connect", TECH)])
    profile = Profile()
    use_case = _run(results, profile=profile)
    assert results.clicked == ["Invite Ana Lima to connect", "Invite Caio Reis to connect"]
    assert profile.opened == ["https://www.linkedin.com/in/bia/"]
    assert (use_case.sent, use_case.profile_invites_sent) == (3, 1)


def test_a_stripped_page_is_reloaded_before_ten_detours_are_paid_for():
    def restore(results):
        results.people = [(f"Invite P{i} X to connect", TECH) for i in range(3)]

    results = Results([(f"Follow P{i} X", TECH) for i in range(3)], on_reload=restore)
    profile = Profile()
    _run(results, profile=profile)
    assert results.reloads == 1 and profile.opened == [] and len(results.clicked) == 3


def test_a_page_with_connectable_people_further_down_is_not_reloaded():
    results = Results([("Follow A A", TECH), ("Invite B B to connect", TECH)])
    _run(results)
    assert results.reloads == 0


def test_a_page_still_stripped_after_its_reload_is_walked_by_profile():
    results = Results([("Follow A A", TECH), ("Follow B B", TECH)])
    profile = Profile()
    _run(results, profile=profile)
    assert results.reloads == 1 and len(profile.opened) == 2


def test_follow_cards_are_left_alone_where_the_page_must_not_be_left():
    results = Results([("Follow A A", TECH), ("Invite B B to connect", TECH)], restorable=False)
    profile = Profile()
    _run(results, profile=profile)
    assert profile.opened == [] and results.clicked == ["Invite B B to connect"]


def test_non_tech_headlines_are_skipped_before_any_click():
    results = Results([("Invite Ana Lima to connect", "Sales Recruiter"),
                       ("Invite Caio Reis to connect", None)])
    use_case = _run(results)
    assert results.clicked == []
    assert (use_case.skipped, use_case.non_tech_skipped) == (2, 2)


def test_any_title_invites_everyone():
    results = Results([("Invite Ana Lima to connect", "Sales Recruiter")])
    _run(results, tech_only=False)
    assert results.clicked == ["Invite Ana Lima to connect"]


def test_the_java_dev_audience_invites_senior_java_devs_only(caplog):
    results = Results([("Invite Ana Lima to connect", "Desenvolvedora Java Sênior"),
                       ("Invite Caio Reis to connect", TECH),
                       ("Invite Davi Melo to connect", "Desenvolvedor Java Júnior")])
    with caplog.at_level(logging.INFO, logger="linkedin_bot"):
        use_case = _run(results, audience=JAVA_DEVS)
    assert results.clicked == ["Invite Ana Lima to connect"]
    assert use_case.non_tech_skipped == 2
    assert "Senior Java dev confirmed for Ana" in caplog.text
    assert "(of which 2 not senior Java devs)" in caplog.text


def test_a_sent_invite_is_recorded_under_the_full_name():
    ledger = Ledger()
    _run(Results([("Invite Ana Lima to connect", TECH)]), ledger=ledger)
    assert ledger.recorded == ["Ana Lima"]


def test_the_note_is_personalized_or_absent():
    modal = Modal()
    _run(Results([("Invite Ana Lima to connect", TECH)]), modal=modal)
    assert modal.notes == ["Olá, Ana!"]
    modal = Modal()
    _run(Results([("Invite Ana Lima to connect", TECH)]), modal=modal, no_message=True)
    assert modal.notes == [None]


def test_max_stops_the_run_once_reached():
    results = Results([(f"Invite P{i} X to connect", TECH) for i in range(5)], pages=3)
    use_case = _run(results, max_invites=2)
    assert use_case.sent == 2 and len(results.clicked) == 2


def test_a_stop_from_the_modal_ends_the_run():
    results = Results([("Invite A A to connect", TECH), ("Invite B B to connect", TECH)])
    _run(results, modal=Modal(InviteStatus.STOP))
    assert results.clicked == ["Invite A A to connect"]


def test_a_limit_warning_declined_stops_before_the_page():
    results = Results([("Invite A A to connect", TECH)])
    _run(results, guard=Guard(ok=False))
    assert results.clicked == []


def test_an_unconfirmed_invite_is_not_counted():
    use_case = _run(Results([("Invite A A to connect", TECH)]),
                    modal=Modal(InviteStatus.UNCONFIRMED))
    assert (use_case.sent, use_case.failed, use_case.skipped) == (0, 0, 0)


def test_an_invite_that_did_not_register_counts_as_failed():
    use_case = _run(Results([("Invite A A to connect", TECH)]), modal=Modal(InviteStatus.FAILED))
    assert use_case.failed == 1


def test_an_intercepted_click_dismisses_and_moves_on():
    results = Results([("Invite A A to connect", TECH), ("Invite B B to connect", TECH)],
                      intercept={"Invite A A to connect"})
    modal = Modal()
    _run(results, modal=modal)
    assert modal.dismissed == 1 and results.clicked == ["Invite B B to connect"]


def test_the_detour_counts_only_an_invite_that_went_out():
    use_case = _run(Results([("Follow Bia Souza", TECH)]), modal=Modal(InviteStatus.SKIPPED))
    assert (use_case.profile_invites_sent, use_case.skipped) == (0, 1)


def test_a_profile_with_no_connect_anywhere_is_skipped_and_the_results_restored():
    results = Results([("Follow Bia Souza", TECH)])
    use_case = _run(results, profile=Profile(has_connect=False))
    assert use_case.skipped == 1 and results.returns == 1


def test_losing_the_results_stops_the_run():
    results = Results([("Follow Bia Souza", TECH), ("Invite Caio Reis to connect", TECH)],
                      back_ok=False)
    _run(results)
    assert results.clicked == []


def test_pages_are_walked_until_the_last(caplog):
    caplog.set_level(logging.INFO, logger="linkedin_bot")
    _run(Results([("Invite A A to connect", TECH)], pages=3))
    assert "--- Processing page 3 ---" in caplog.text
    assert "Reached the last page." in caplog.text


def test_ctrl_c_still_reports_the_tally(caplog):
    caplog.set_level(logging.INFO, logger="linkedin_bot")
    results = Results([("Invite A A to connect", TECH)], pages=3)
    original = results.go_to_next_page

    def interrupt():
        original()
        raise KeyboardInterrupt

    results.go_to_next_page = interrupt
    _run(results)   # must not propagate
    assert "Session summary — sent: 1" in caplog.text
    assert "195 invitation(s) sent" in caplog.text


def test_an_unexpected_error_still_reports_the_tally(caplog):
    caplog.set_level(logging.INFO, logger="linkedin_bot")
    results = Results([("Invite A A to connect", TECH)], pages=3)

    def boom():
        raise RuntimeError("driver died")

    results.go_to_next_page = boom
    with pytest.raises(RuntimeError):
        _run(results)
    assert "Session summary — sent: 1" in caplog.text
