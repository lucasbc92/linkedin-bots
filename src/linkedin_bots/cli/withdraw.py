"""linkedin-bots withdraw — withdraw sent invitations older than a cutoff."""
import argparse
import sys

from linkedin_bots.cli._common import add_log_level, start_logging
from linkedin_bots.withdrawing.domain.sent_age import oldest_label, parse_until

EPILOG = """
examples:
  linkedin-bots withdraw --until 2m --dry-run
      # everything sent 2+ months ago, listed but not clicked
  linkedin-bots withdraw --until 2026/05/01 --dry-run
      # same, with an absolute cutoff date
  linkedin-bots withdraw --until 2026/05/01
      # withdraw every invitation sent on or before that date, oldest first
  linkedin-bots withdraw --until 1m --max 200 -y
      # load only the 200 newest invitations, withdraw the 1-month-old ones
      # among them, and skip the confirmation prompt
  linkedin-bots withdraw --until 1m --rolling --max 200
      # start from what is on screen, withdraw everything past 1 month,
      # load a couple more pages, repeat — down to the oldest invitation
  linkedin-bots withdraw
      # same as --until 1m: load to the oldest invitation, then withdraw
      # every one sent 1 month ago or earlier
  linkedin-bots withdraw --probe
      # print which tab, selectors and buttons the bot can see, then exit

by default the list loads all the way to the oldest invitation, then every
loaded invitation past --until is withdrawn, oldest first — wherever it sits,
since LinkedIn doesn't keep the list strictly sorted; --max bounds the loading
instead, so only that many cards are ever in the page and withdrawal picks its
targets from those

--rolling turns that around: it withdraws whatever is already loaded and past
the cutoff, loads two more pages, and repeats until the list ends — so the
page never holds more than a few pages at a time. Scroll down to the first
invitation past the cutoff by hand and it picks up from there

cards show relative ages ("Sent 3 months ago"), which LinkedIn rounds down,
so an invitation is withdrawn only when its *newest possible* date is already
past --until; ambiguous cards are left alone
"""


def add_parser(sub):
    wp = sub.add_parser(
        "withdraw",
        help="Withdraw sent invitations older than a given date",
        description="Load the sent-invitation manager back to a cutoff date "
                    "and withdraw every invitation older than it, oldest "
                    "first.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    wp.add_argument(
        "--until", metavar="DATE|AGE", default="1m",
        help="Withdraw invitations sent on or before this date (2026/06/20) "
             "or this far back from today (2m, 3w, 10d, 1y). Default: 1m")
    wp.add_argument(
        "--max", dest="max_cards", type=int, metavar="N",
        help="Load at most N invitations, then withdraw the ones among them "
             "older than --until. Caps the loading phase so the page stays "
             "light; --max-pages bounds it in page loads instead. With "
             "--rolling it is the ceiling the page is topped back up to")
    wp.add_argument(
        "--rolling", action="store_true",
        help="Withdraw as the list loads: start from what is on screen, "
             "withdraw everything past --until, load two more pages, repeat "
             "down to the oldest — instead of expanding the list first")
    wp.add_argument(
        "--dry-run", action="store_true",
        help="Preview what would be withdrawn — nothing is clicked")
    wp.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip the confirmation prompt before the first withdrawal")
    wp.add_argument(
        "--max-pages", "--max-clicks", dest="max_pages", type=int, metavar="N",
        help="Cap the pages loaded, with or without --until (default: "
             "unlimited). A page counts whether it came from clicking 'Load "
             "more' or from the list paging on scroll. With --rolling, where "
             "there is no single expansion to cap, it sets the pages loaded "
             "per top-up (default: 2)")
    wp.add_argument(
        "--no-js", action="store_true",
        help="Skip the in-page load loop; drive every page with trusted clicks")
    wp.add_argument(
        "--stop-early", action="store_true",
        help="Stop loading once --until is in view instead of expanding to "
             "the true end of the list (cheaper, but the oldest never load)")
    wp.add_argument(
        "--probe", action="store_true",
        help="Report what the page exposes (tabs, selectors, buttons) and exit")
    add_log_level(wp)
    wp.set_defaults(run=run)


def run(args):
    logger, log_path = start_logging("withdrawing", args.log_level)

    cutoff = None
    if args.until:
        try:
            cutoff = parse_until(args.until)
        except ValueError as e:
            logger.error(f"Invalid --until: {e}")
            sys.exit(1)
    elif args.rolling:
        logger.error(
            "--rolling needs --until: it withdraws while it loads, so there "
            "has to be a cutoff for each card to be measured against.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("LinkedIn Withdraw Bot")
    logger.info(f"  Until      : "
                f"{f'{cutoff}  (--until {args.until})' if cutoff else 'none (load only, no withdrawals)'}")
    logger.info(f"  Dry run    : {'yes' if args.dry_run else 'no'}")
    logger.info(f"  Page loader: {'trusted clicks' if args.no_js else 'in-page loop'}")
    logger.info(f"  Max pages  : {args.max_pages or 'unlimited'}")
    if args.rolling:
        depth = (f"as needed, {args.max_pages or 2} page(s) at a time  "
                 f"(--rolling)")
        if args.max_cards:
            depth += f", keeping ~{args.max_cards} in the page"
    elif args.max_cards:
        depth = f"at most {args.max_cards} invitation(s)  (--max)"
    elif args.stop_early:
        depth = "to the cutoff  (--stop-early)"
    else:
        depth = "to the end of the list"
    logger.info(f"  Load depth : {depth}")
    logger.info(f"  Log level  : {args.log_level}")
    logger.info("=" * 60)

    if args.rolling and args.stop_early:
        logger.warning(
            "--stop-early does nothing with --rolling: there is no up-front "
            "expansion for it to cut short.")

    # Imported here, not at module scope: they pull in Selenium.
    from linkedin_bots.shared.infrastructure.browser import create_driver
    from linkedin_bots.shared.infrastructure.console import ask_yes_no
    from linkedin_bots.shared.infrastructure.pacing import HumanPause
    from linkedin_bots.shared.infrastructure.sleep import allow_sleep, prevent_sleep
    from linkedin_bots.withdrawing.adapters.selenium.sent_invitations_page import (
        SeleniumSentInvitationsPage)
    from linkedin_bots.withdrawing.application.withdraw_old_invitations import (
        WithdrawOldInvitations, WithdrawSettings)

    driver, _ = create_driver(attach_to_existing=True)
    page = SeleniumSentInvitationsPage(driver)
    # A full run over ~1000 invitations takes an hour; keep Windows awake.
    prevent_sleep()
    try:
        if args.probe:
            page.probe()
        elif cutoff is None:
            result = page.load(max_pages=args.max_pages, max_cards=args.max_cards,
                               use_js=not args.no_js)
            print(f"\n{result.count} invitation(s) loaded. "
                  f"Oldest: {oldest_label(page.sent_labels()) or 'unknown'}")
        else:
            settings = WithdrawSettings(
                until=cutoff,
                dry_run=args.dry_run,
                max_cards=args.max_cards,
                max_pages=args.max_pages,
                auto_continue=args.yes,
                use_js=not args.no_js,
                stop_early=args.stop_early,
                rolling=args.rolling,
            )
            WithdrawOldInvitations(page, ask_yes_no, HumanPause(), settings).run()
    except KeyboardInterrupt:
        logger.warning("Stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Stopped due to error: {e}")
    finally:
        allow_sleep()
        logger.info(f"Log file: {log_path}")
