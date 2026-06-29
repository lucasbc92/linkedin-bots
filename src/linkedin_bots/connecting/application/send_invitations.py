"""Invite the people on each page of search results, one walk per page.

Each person is invited whichever way their own card allows: the Connect
control in place, or — when the card offers only Follow — the Connect behind
their profile's More menu, after which the walk steps back into the results.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from linkedin_bots.connecting.application.ports import (ClickIntercepted, InviteLedger,
                                                        InviteModal, InviteStatus, LimitGuard,
                                                        Pause, ProfilePage, SearchResults)
from linkedin_bots.connecting.domain.labels import first_name_from_label, full_name_from_label
from linkedin_bots.connecting.domain.page_rules import best_title, looks_stripped
from linkedin_bots.connecting.domain.tech_recruiter import DEFAULT_MIN_SCORE
from linkedin_bots.shared.domain.weeks import current_week_start

logger = logging.getLogger("linkedin_bot")


@dataclass(frozen=True)
class InviteSettings:
    """How a run behaves; see ``linkedin-bots connect --help`` for each flag."""

    no_message: bool = False
    max_invites: Optional[int] = None
    tech_only: bool = True
    min_title_score: float = DEFAULT_MIN_SCORE
    reverse: bool = False


class SendInvitations:
    def __init__(self, results: SearchResults, profile: ProfilePage, modal: InviteModal,
                 guard: LimitGuard, ledger: InviteLedger, pause: Pause, templates,
                 settings: InviteSettings):
        self.results = results
        self.profile = profile
        self.modal = modal
        self.guard = guard
        self.ledger = ledger
        self.pause = pause
        self.templates = templates
        self.settings = settings
        self.sent = 0
        self.failed = 0
        self.skipped = 0
        self.non_tech_skipped = 0
        # Of the invitations sent, how many took the profile detour.
        self.profile_invites_sent = 0

    def run(self, max_pages=100):
        """Walk the result pages; the tally is reported however the run ends."""
        page_num = 1
        self.results.select_search_tab()
        try:
            while page_num <= max_pages:
                logger.info(f"--- Processing page {page_num} ---")

                if not self.guard.check():
                    logger.info("Stopping due to invitation limit.")
                    break

                if not self._process_page():
                    logger.info("Stopped.")
                    break

                if not self.results.go_to_next_page():
                    direction = "first" if self.settings.reverse else "last"
                    logger.info(f"Reached the {direction} page.")
                    break

                page_num += 1
                self.pause(12, 25)
        except KeyboardInterrupt:
            # Swallowed here so the summary below still runs.
            logger.warning("Stopped by user (Ctrl+C)")
        finally:
            self._log_summary(page_num)

    # ------------------------------------------------------------------
    # One page
    # ------------------------------------------------------------------

    def _process_page(self):
        """Process every reachable person on the current page. Returns False to stop."""
        results = self.results
        if not results.await_results():
            return False

        include_follow = results.detours_allowed()
        results_url = results.results_url()
        processed_labels = set()
        reloaded = False
        probed = False

        while True:
            if not self.guard.check():
                logger.info("Stopping due to invitation limit.")
                return False

            target, target_label, kind = results.next_target(
                processed_labels, include_follow=include_follow)

            if target is None:
                tally = results.page_action_tally()
                # A full page of results where not one card offers Connect is
                # what LinkedIn starts serving after a burst of invitations:
                # the run's last two sessions each went dead this way, nine
                # pages in a row, and came back the moment the page was
                # loaded afresh. So the verdict is only accepted once it
                # survives a reload.
                if not processed_labels and not reloaded and looks_stripped(tally):
                    logger.info(
                        f"{tally['cards']} result(s) but none connectable — "
                        f"reloading the page before accepting that")
                    reloaded = True
                    if results.reload_results():
                        continue

                self._log_page_scanned(len(processed_labels), tally)
                break

            # The first person on this page can only be reached through
            # their profile. Before paying for that — and for the nine behind
            # them — find out whether the page is one LinkedIn has stripped
            # of its Connect controls, which is what it starts serving after
            # a burst of invitations, and which a reload usually undoes. The
            # connect-only scan walks the whole list, so the answer is about
            # the page rather than about the handful of rows mounted so far.
            if kind == "follow" and not processed_labels and not probed:
                probed = True
                connectable, _, _ = results.next_target(set(), include_follow=False)
                if connectable is None and not reloaded:
                    tally = results.page_action_tally()
                    if tally and tally.get("cards"):
                        logger.info(
                            f"{tally['cards']} result(s) and not one Connect "
                            f"control — reloading before spending a profile "
                            f"detour on each of them")
                        reloaded = True
                        if results.reload_results():
                            continue
                # The scan above moved the list, so the walk starts over to
                # pick the same person up by a handle that is still attached.
                continue

            processed_labels.add(target_label)

            name = first_name_from_label(target_label)
            if name:
                logger.info(f"Processing {target_label} → first name: {name}")

            # Judge the headline before clicking: a skipped card must cost
            # nothing against the weekly invitation quota — and, for a
            # Follow-only card, nothing in page loads either.
            if self.settings.tech_only:
                titles = results.extract_title_texts(target)
                if not titles:
                    logger.debug(f"No headline found on the card for {target_label}")
                    verdict = None
                else:
                    verdict = best_title(titles)
                    logger.debug(f"Title for {target_label}: {verdict!r}")
                if verdict is None:
                    logger.warning(
                        f"Could not read a headline for {target_label}. "
                        f"Skipping (tech-recruiter filter is on).")
                    self.skipped += 1
                    self.non_tech_skipped += 1
                    continue
                if verdict.score < self.settings.min_title_score:
                    logger.info(
                        f"Skipping {name or target_label} — not a tech "
                        f"recruiter: {verdict.title!r} "
                        f"(score {verdict.score:.2f} < {self.settings.min_title_score:.2f}; "
                        f"{verdict.reason})")
                    self.skipped += 1
                    self.non_tech_skipped += 1
                    continue
                logger.info(
                    f"Tech recruiter confirmed for {name or target_label}: "
                    f"{verdict.title!r} (score {verdict.score:.2f}; {verdict.reason})")

            if kind == "follow":
                # The page is about to be left and restored, so every element
                # found on it goes stale; the scan picks up from the labels
                # already processed. Errors are caught here rather than in the
                # handler below, which assumes the results are still on screen.
                try:
                    status = self._invite_via_profile(target, target_label, name)
                except Exception as e:
                    logger.error(f"Error on the profile detour for {target_label}: {e}")
                    self.skipped += 1
                    status = (InviteStatus.SKIPPED if results.return_to_results(results_url)
                              else InviteStatus.STOP)
                if status is InviteStatus.STOP:
                    return False
                self.pause(8, 18)
                continue

            try:
                results.click_connect(target, target_label)

                if self._complete(target_label, name) is InviteStatus.STOP:
                    return False

                self.pause(8, 18)

            except ClickIntercepted:
                logger.warning(f"Connect control for {target_label} was intercepted")
                if not self.guard.check():
                    return False
                self.modal.dismiss_open_modal()

            except Exception as e:
                logger.error(f"Error processing {target_label}: {e}")
                if not self.guard.check():
                    return False
                try:
                    self.modal.dismiss_open_modal()
                except Exception:
                    pass

        return True

    # ------------------------------------------------------------------
    # The profile detour
    # ------------------------------------------------------------------

    def _invite_via_profile(self, control, label, name):
        """Invite someone whose result card offers nothing but Follow.

        The detour: open their profile, take Connect out of the More menu,
        run the usual note-and-Send ritual there, then step back into the
        results, where the scan resumes from the person just handled.
        """
        full_name = full_name_from_label(label) or label
        profile_url = self.results.profile_url_for(control)
        if not profile_url:
            logger.warning(f"No profile link on the card for {label}. Skipping.")
            self.skipped += 1
            return InviteStatus.SKIPPED

        results_url = self.results.results_url()

        logger.info(
            f"{full_name} can only be followed from the results — opening "
            f"{profile_url} to connect there instead")

        try:
            self.profile.open(profile_url)
        except Exception as e:
            logger.error(f"Could not open {profile_url}: {e}")
            self.skipped += 1
            status = InviteStatus.SKIPPED
        else:
            try:
                status = self._connect_on_profile(full_name, name)
            except Exception as e:
                logger.error(f"Error connecting from {profile_url}: {e}")
                try:
                    self.modal.dismiss_open_modal()
                except Exception:
                    pass
                self.skipped += 1
                status = InviteStatus.SKIPPED

        if not self.results.return_to_results(results_url):
            logger.error(
                "Lost the results page after the profile detour. Stopping "
                "rather than paging on from somewhere else.")
            return InviteStatus.STOP
        return status

    def _connect_on_profile(self, full_name, name):
        """Send the invitation from the person's own profile page."""
        if not self.profile.open_connect(full_name):
            self.skipped += 1
            return InviteStatus.SKIPPED
        status = self._complete(f"Invite {full_name} to connect", name)
        if status is InviteStatus.SENT:
            self.profile_invites_sent += 1
        return status

    # ------------------------------------------------------------------
    # The invite modal's outcome
    # ------------------------------------------------------------------

    def _complete(self, target_label, name):
        note = None if self.settings.no_message else self.templates.personalize
        result = self.modal.complete(target_label, name, note)
        name = result.name
        if result.status is InviteStatus.SENT:
            self.sent += 1
            # Recorded before anything else can fail, so an invite is never
            # counted in the log but missing from the ledger.
            self.ledger.record(full_name_from_label(target_label) or name or target_label)
            logger.info(
                f"Invitation sent to {name or target_label} "
                f"[sent={self.sent}, failed={self.failed}, skipped={self.skipped}]")
            if self.settings.max_invites and self.sent >= self.settings.max_invites:
                logger.info(f"Reached --max {self.settings.max_invites}. Stopping.")
                return InviteStatus.STOP
            return InviteStatus.SENT
        if result.status is InviteStatus.FAILED:
            self.failed += 1
            logger.warning(
                f"Invite to {target_label} did not register "
                f"[sent={self.sent}, failed={self.failed}, skipped={self.skipped}]")
            return InviteStatus.FAILED
        if result.status is InviteStatus.SKIPPED:
            self.skipped += 1
        return result.status

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _log_page_scanned(self, handled, tally=None):
        """Report what the finished page actually held."""
        if tally is None:
            tally = self.results.page_action_tally()
        if not tally:
            logger.info(f"Page scanned — {handled} person(s) handled")
            return

        breakdown = ", ".join(
            f"{tally[key]} {key}-only" for key in ("follow", "message")
            if tally.get(key))
        detail = f" ({breakdown})" if breakdown else ""
        logger.info(
            f"Page scanned — {tally['cards']} result(s), "
            f"{tally['connect']} connectable{detail}; "
            f"{handled} person(s) handled")

    def _log_summary(self, pages_processed):
        """Log the session and weekly totals. Safe to call from a finally block."""
        direction = "reverse" if self.settings.reverse else "forward"
        logger.info(f"Completed ({direction}) — {pages_processed} page(s) processed.")
        logger.info(
            f"Session summary — sent: {self.sent}"
            + (f" (of which {self.profile_invites_sent} via the profile detour)"
               if self.profile_invites_sent else "")
            + f" | failed: {self.failed}"
            + f" | skipped: {self.skipped}"
            + (f" (of which {self.non_tech_skipped} not tech recruiters)"
               if self.non_tech_skipped else ""))

        week = current_week_start()
        logger.info(
            f"Weekly total (week of {week}): "
            f"{self.ledger.count_for_week(week)} invitation(s) sent")
