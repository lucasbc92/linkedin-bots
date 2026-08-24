"""Withdraw every sent invitation older than a cutoff, oldest first.

The pending-invitation list is capped, and months-old invitations that were
never accepted are what fills it. Withdrawal is irreversible, so a card is
only withdrawn when its own age proves it is past the cutoff.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from linkedin_bots.withdrawing.application.ports import (Confirm, Pause, SentInvitationsPage,
                                                         StaleListError)
from linkedin_bots.withdrawing.domain.invitation import targets_older_than
from linkedin_bots.withdrawing.domain.sent_age import oldest_label, reached_cutoff

logger = logging.getLogger("linkedin_bot")

# Pages a rolling run loads per top-up. Small on purpose: withdrawal resumes
# as soon as new invitations arrive, so the page never has to hold the list.
ROLLING_CHUNK_PAGES = 2
# Gap between withdrawals — these hit LinkedIn's API, so they pace slower.
WITHDRAW_PAUSE_RANGE = (1.5, 3.0)
# How long a fully withdrawn window gets to refill before it is counted.
REFILL_PAUSE_RANGE = (1.2, 2.4)


@dataclass(frozen=True)
class WithdrawSettings:
    """How a run behaves; see ``linkedin-bots withdraw --help`` for each flag."""

    until: date
    dry_run: bool = False
    max_cards: Optional[int] = None
    max_pages: Optional[int] = None
    auto_continue: bool = False
    use_js: bool = True
    stop_early: bool = False
    rolling: bool = False


class WithdrawOldInvitations:
    def __init__(self, page: SentInvitationsPage, confirm: Confirm, pause: Pause,
                 settings: WithdrawSettings):
        self.page = page
        self.confirm = confirm
        self.pause = pause
        self.settings = settings
        self.withdrawn = 0
        self.previewed = 0
        self.failed = 0
        # Invitations already acted on, by key. A failed withdrawal leaves its
        # card in the list, so without this a rolling run would find it again
        # on the next pass and retry it forever.
        self._processed = set()

    def run(self):
        """Withdraw every invitation past the cutoff; the tally is always logged."""
        try:
            if self.settings.rolling:
                self._run_rolling()
            else:
                self._run_expanded()
        finally:
            self._report()

    # ------------------------------------------------------------------
    # Expand, then withdraw
    # ------------------------------------------------------------------

    def _run_expanded(self):
        s = self.settings
        loaded = self.page.load(max_pages=s.max_pages, max_cards=s.max_cards,
                                stop_when=self._load_stop_condition(),
                                use_js=s.use_js).count
        if not loaded:
            return

        targets = targets_older_than(self.page.loaded_invitations(), s.until)
        if not targets:
            logger.info(
                f"Nothing to withdraw: none of the {loaded} loaded "
                f"invitation(s) is provably older than {s.until} "
                f"(oldest: {oldest_label(self.page.sent_labels()) or 'unknown'}).")
            if s.max_cards is not None and loaded >= s.max_cards:
                logger.info(
                    f"Only the {loaded} newest invitation(s) were loaded "
                    f"(--max {s.max_cards}) — raise it to reach further back.")
            return

        logger.info(
            f"{len(targets)} invitation(s) to withdraw, oldest first: "
            f"{targets[0].name} ({targets[0].age}) "
            f"→ {targets[-1].name} ({targets[-1].age}).")

        if not s.dry_run and not s.auto_continue:
            if not self.confirm(f"\nWithdraw {len(targets)} invitation(s)? "
                                f"This cannot be undone. [y/N] "):
                logger.info("Cancelled by user — nothing was withdrawn.")
                return

        self._withdraw_all(
            targets,
            rescan=lambda: targets_older_than(self.page.loaded_invitations(), s.until))

    def _load_stop_condition(self):
        """When to stop loading pages, or None to load to the end of the list.

        The list is only roughly sorted — old invitations can sit anywhere,
        even below hours-old ones — so by default every page is loaded and
        every card past the cutoff is withdrawn, wherever it sits.
        ``--stop-early`` gives that up deliberately: stop as soon as the last
        loaded card is past the cutoff.
        """
        if not self.settings.stop_early:
            return None
        until = self.settings.until
        return lambda labels: reached_cutoff(labels, until)

    # ------------------------------------------------------------------
    # Rolling: withdraw what is loaded, load a little more, repeat
    # ------------------------------------------------------------------

    def _run_rolling(self):
        """Withdraw down the list, loading more invitations as it goes.

        Withdrawn cards leave the DOM as new ones arrive, so the page stays
        about the size it started at. It starts from whatever is on screen,
        so scrolling by hand to the first invitation past the cutoff and then
        starting the bot does exactly what it looks like.
        """
        s = self.settings
        self.page.open()
        if not self.page.card_count():
            logger.warning(
                "No invitation cards found — is the Sent tab open and loaded?")
            return

        confirmed = s.dry_run or s.auto_continue
        exhausted = False
        while True:
            targets = self._rolling_targets()
            if targets:
                logger.info(
                    f"{len(targets)} loaded invitation(s) past {s.until}, "
                    f"oldest first: "
                    f"{targets[0].name} ({targets[0].age}) "
                    f"→ {targets[-1].name} ({targets[-1].age}).")
                if not confirmed:
                    if not self.confirm(
                            f"\nWithdraw these {len(targets)} and keep going "
                            f"down to the oldest? This cannot be undone. [y/N] "):
                        logger.info("Cancelled by user — nothing was withdrawn.")
                        return
                    confirmed = True
                self._withdraw_all(targets, rescan=self._rolling_targets)
            elif exhausted:
                break

            before = self.page.card_count()
            result = self._top_up()
            exhausted = result.exhausted
            if result.count > before:
                continue
            if exhausted:
                logger.info("End of the list — nothing older left to load.")
            else:
                logger.warning(
                    "The list stopped loading before the end; stopping here. "
                    "Re-run to pick up where this left off.")
            break

    def _rolling_targets(self):
        """Loaded invitations past the cutoff that this run has not acted on yet."""
        return [i for i in targets_older_than(self.page.loaded_invitations(),
                                              self.settings.until)
                if i.key not in self._processed]

    def _top_up(self):
        """Load another couple of pages.

        ``--max-pages`` sets the batch, since a rolling run has no single
        expansion for it to cap. The ``--max`` ceiling applies too, except
        when the page already sits at it: then one page is loaded anyway, or
        the run could never work its way down to the oldest.
        """
        s = self.settings
        before = self.page.card_count()
        if not before:
            # The whole loaded window was just withdrawn. The list refills
            # itself, but not instantly, and a count taken now would read as
            # an empty page and end the run one batch early.
            self.pause(*REFILL_PAUSE_RANGE)
            before = self.page.card_count()
        cap = s.max_cards
        pages = s.max_pages or ROLLING_CHUNK_PAGES
        if cap is not None and before >= cap:
            logger.debug(
                f"{before} card(s) loaded, already at the --max {cap} "
                f"ceiling; loading one page anyway to keep moving down.")
            cap, pages = None, 1
        return self.page.load(max_pages=pages, max_cards=cap, use_js=s.use_js)

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    def _withdraw_all(self, targets, rescan):
        """Withdraw every invitation in ``targets``, oldest first.

        Ones already acted on are skipped, so a failed withdrawal is never
        retried. ``rescan`` returns a fresh target list after the list
        re-rendered and every remaining element reference died with it.
        """
        s = self.settings
        while True:
            pending = [i for i in targets if i.key not in self._processed]
            if not pending:
                return

            stale = False
            for invitation in pending:
                if s.dry_run:
                    logger.info(f"[DRY RUN] Would withdraw: "
                                f"{invitation.name or '(unknown)'} — "
                                f"{invitation.age or 'unknown age'}")
                    ok = True
                else:
                    try:
                        ok = self.page.withdraw(invitation)
                    except StaleListError:
                        logger.debug("Card went stale mid-withdrawal; rescanning.")
                        stale = True
                        break

                self._processed.add(invitation.key)
                if not ok:
                    self.failed += 1
                elif s.dry_run:
                    self.previewed += 1
                else:
                    self.withdrawn += 1
                if not s.dry_run:
                    self.pause(*WITHDRAW_PAUSE_RANGE)

            if stale:
                targets = rescan()

    def _report(self):
        logger.info("=" * 60)
        if self.settings.dry_run:
            logger.info(
                f"Dry run — {self.previewed} invitation(s) would be withdrawn.")
        else:
            logger.info(f"Withdrawn: {self.withdrawn}")
        if self.failed:
            logger.info(f"Failed   : {self.failed}")
        logger.info("=" * 60)
