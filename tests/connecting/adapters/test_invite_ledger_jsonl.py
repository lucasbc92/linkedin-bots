"""The invitation ledger on disk."""
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from linkedin_bots.connecting.adapters import invite_ledger_jsonl as history
from linkedin_bots.shared.domain.weeks import BRT


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()) / "invites.jsonl"

    def test_counts_invites_recorded_in_a_week(self):
        for name in ("Ana", "Bruno", "Carla"):
            history.record_invite(
                name, path=self.tmp, now=datetime(2026, 7, 22, 10, tzinfo=BRT))
        self.assertEqual(history.count_invites_for_week("2026-07-19", self.tmp), 3)

    def test_week_boundary_is_sunday_2100_brt(self):
        history.record_invite(
            "Before", path=self.tmp, now=datetime(2026, 7, 19, 20, 59, tzinfo=BRT))
        history.record_invite(
            "After", path=self.tmp, now=datetime(2026, 7, 19, 21, 1, tzinfo=BRT))
        self.assertEqual(
            dict(history.weekly_counts(self.tmp)),
            {"2026-07-12": 1, "2026-07-19": 1})

    def test_truncated_final_line_does_not_break_counting(self):
        history.record_invite(
            "Ana", path=self.tmp, now=datetime(2026, 7, 22, 10, tzinfo=BRT))
        with open(self.tmp, "a", encoding="utf-8") as f:
            f.write('{"ts": "2026-07-2')          # killed mid-write
        self.assertEqual(history.count_invites_for_week("2026-07-19", self.tmp), 1)

    def test_missing_ledger_counts_zero_instead_of_raising(self):
        self.assertEqual(history.weekly_counts(self.tmp / "nope.jsonl"), {})

    def test_ledger_lives_in_the_data_directory(self):
        """The original bug class: a relative path resolved against the CWD."""
        home = Path(os.environ["LINKEDIN_BOTS_HOME"])
        cwd = os.getcwd()
        try:
            os.chdir(tempfile.mkdtemp())
            self.assertEqual(history.default_invite_file(),
                             home / "connecting" / "invites.jsonl")
        finally:
            os.chdir(cwd)

    def test_backfill_is_idempotent(self):
        log_dir = Path(tempfile.mkdtemp())
        (log_dir / "week-2026-07-19.log").write_text(
            "2026-07-20 03:37:31 [INFO ] Invitation sent to Anielle "
            "[sent=24, failed=0, skipped=0]\n"
            "2026-07-20 03:37:48 [INFO ] Invitation sent to Edson "
            "[sent=25, failed=0, skipped=0]\n"
            "2026-07-20 03:38:02 [WARN ] Invite to Invite X to connect "
            "did not register [sent=25, failed=1, skipped=0]\n",
            encoding="utf-8")

        self.assertEqual(history.backfill_from_logs(log_dir, self.tmp), 2)
        self.assertEqual(history.backfill_from_logs(log_dir, self.tmp), 0)
        self.assertEqual(history.count_invites_for_week("2026-07-19", self.tmp), 2)


class JsonlInviteLedgerTest(unittest.TestCase):
    def test_records_and_counts_through_the_port(self):
        path = Path(tempfile.mkdtemp()) / "invites.jsonl"
        ledger = history.JsonlInviteLedger(path)
        ledger.record("Ana Silva")
        ledger.record("Bruno Lima")
        self.assertEqual(ledger.count_for_week(), 2)
