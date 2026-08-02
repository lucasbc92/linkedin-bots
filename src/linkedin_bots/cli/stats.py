"""linkedin-bots stats — invitations sent per week, from the connecting ledger."""
import argparse

from linkedin_bots.shared.infrastructure.paths import log_dir

EPILOG = """
examples:
  linkedin-bots stats                # invitations sent per week
  linkedin-bots stats --weeks 4      # only the last 4 weeks
  linkedin-bots stats --backfill     # import past invites from the connecting logs

a logging week starts Sunday 21:00 (America/Sao_Paulo)
"""


def add_parser(sub):
    sp = sub.add_parser(
        "stats",
        help="Show how many invitations were sent per week",
        description="Report invitations sent per week from the Connect bot's "
                    "ledger (invites.jsonl in the data directory).",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sp.add_argument(
        "--weeks", type=int, metavar="N",
        help="Show only the last N weeks (default: all)")
    sp.add_argument(
        "--backfill", action="store_true",
        help="Import invitations from the connecting logs into the ledger first "
             "(safe to repeat — already-known entries are skipped)")
    sp.set_defaults(run=run)


def run(args):
    from linkedin_bots.connecting.adapters.invite_ledger_jsonl import (backfill_from_logs,
                                                  default_invite_file, weekly_counts)
    from linkedin_bots.shared.domain.weeks import current_week_start

    if args.backfill:
        added = backfill_from_logs()
        print(f"Backfilled {added} invitation(s) from {log_dir('connecting')}\n")

    counts = weekly_counts()
    if not counts:
        print(f"No invitations recorded yet in {default_invite_file()}.")
        print("Run 'linkedin-bots stats --backfill' to import past runs "
              f"from {log_dir('connecting')}.")
        return

    weeks = list(counts.items())
    if args.weeks:
        weeks = weeks[-args.weeks:]

    this_week = current_week_start().isoformat()

    print("Invitations sent per week (week starts Sunday 21:00 BRT)\n")
    for week, count in weeks:
        marker = "  ← current" if week == this_week else ""
        print(f"  week of {week}   {count:>4}{marker}")
    print(f"  {'-' * 26}")
    print(f"  total{' ' * 15}{sum(c for _, c in weeks):>4}")
