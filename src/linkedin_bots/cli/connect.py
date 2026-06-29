"""linkedin-bots connect — send connection requests from people-search results."""
import argparse

from linkedin_bots.cli._common import (TemplateCompleter, add_log_level,
                                       require_template, start_logging)
from linkedin_bots.connecting.domain.tech_recruiter import DEFAULT_MIN_SCORE
from linkedin_bots.shared.infrastructure.templates import resolve_template

EPILOG = """
examples:
  linkedin-bots connect
  linkedin-bots connect -m message_english.txt
  linkedin-bots connect -n                         # no note
  linkedin-bots connect -y -l INFO                 # auto-continue, less verbose
  linkedin-bots connect -r                         # navigate in reverse (Previous)
  linkedin-bots connect --max 80                   # stop after 80 invitations sent
  linkedin-bots connect --any-title                # invite every recruiter, not just tech
  linkedin-bots connect --title-score 0.9          # stricter tech-recruiter filter
  linkedin-bots connect -f                         # fast: minimal pauses between invites

by default only headlines that read as a *tech* recruiter are invited
(scored by linkedin_bots/connecting/domain/tech_recruiter.py); templates live in:
src/linkedin_bots/connecting/templates/
"""


def add_parser(sub):
    cp = sub.add_parser(
        "connect",
        help="Send connection requests with personalized notes",
        description="Walk LinkedIn people-search results and send "
                    "personalised connection invitations.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cp.add_argument(
        "-y", "--yes", action="store_true",
        help="Auto-continue past the weekly close-to-limit warning")
    m_connect = cp.add_argument(
        "-m", "--message", default="message.txt", metavar="FILE",
        help="Template file in the connecting templates  (default: message.txt)")
    m_connect.completer = TemplateCompleter("connecting")
    cp.add_argument(
        "-r", "--reverse", action="store_true",
        help="Navigate in reverse order (click Previous instead of Next)")
    cp.add_argument(
        "-n", "--no-message", action="store_true",
        help="Send invitations without an accompanying note")
    cp.add_argument(
        "--max", dest="max_invites", type=int, metavar="N",
        help="Stop after sending N invitations (blast-radius limit)")
    cp.add_argument(
        "--any-title", action="store_true",
        help="Invite every recruiter, skipping the tech-recruiter headline filter")
    cp.add_argument(
        "--title-score", type=float, default=DEFAULT_MIN_SCORE, metavar="S",
        help=f"Minimum tech-recruiter similarity score, 0.0-1.0 "
             f"(default: {DEFAULT_MIN_SCORE})")
    cp.add_argument(
        "-f", "--fast", action="store_true",
        help="Shrink the randomized pauses between invitations and pages to a "
             "minimum (faster, but a more obviously automated pattern)")
    add_log_level(cp)
    cp.set_defaults(run=run)


def run(args):
    logger, log_path = start_logging("connecting", args.log_level)

    message_file = resolve_template(args.message, "connecting")
    if not args.no_message:
        message_file = require_template(args.message, "connecting",
                                        "-m/--message", logger)

    logger.info("=" * 60)
    logger.info("LinkedIn Connect Bot")
    logger.info(f"  Mode       : {'no note (-n)' if args.no_message else 'personalized note'}")
    if not args.no_message:
        logger.info(f"  Message    : {message_file}")
    logger.info(f"  Navigation : {'reverse (Previous)' if args.reverse else 'forward (Next)'}")
    logger.info(f"  Auto-cont  : {'on (-y)' if args.yes else 'off'}")
    logger.info(f"  Max invites: {args.max_invites or 'unlimited'}")
    logger.info(f"  Titles     : {'any recruiter (--any-title)' if args.any_title else f'tech recruiters only (score >= {args.title_score:.2f})'}")
    logger.info(f"  Pacing     : {'fast (-f)' if args.fast else 'humanized'}")
    logger.info(f"  Log level  : {args.log_level}")
    logger.info("=" * 60)

    # Imported here, not at module scope: they pull in Selenium.
    from linkedin_bots.connecting.adapters.invite_ledger_jsonl import JsonlInviteLedger
    from linkedin_bots.connecting.adapters.selenium.invite_modal import SeleniumInviteModal
    from linkedin_bots.connecting.adapters.selenium.limit_guard import SeleniumLimitGuard
    from linkedin_bots.connecting.adapters.selenium.profile_page import SeleniumProfilePage
    from linkedin_bots.connecting.adapters.selenium.search_results_page import (
        SeleniumSearchResults)
    from linkedin_bots.connecting.application.send_invitations import (InviteSettings,
                                                                       SendInvitations)
    from linkedin_bots.shared.infrastructure.browser import create_driver
    from linkedin_bots.shared.infrastructure.console import ask_yes_no
    from linkedin_bots.shared.infrastructure.pacing import HumanPause
    from linkedin_bots.shared.infrastructure.sleep import allow_sleep, prevent_sleep
    from linkedin_bots.shared.infrastructure.template_files import load_templates

    driver, perf_logging = create_driver(attach_to_existing=True)
    templates = None if args.no_message else load_templates(str(message_file), max_length=300)
    pause = HumanPause(fast=args.fast)
    guard = SeleniumLimitGuard(driver, perf_logging, ask_yes_no, auto_continue=args.yes)
    use_case = SendInvitations(
        SeleniumSearchResults(driver, guard, pause, reverse=args.reverse),
        SeleniumProfilePage(driver, pause),
        SeleniumInviteModal(driver, guard, pause),
        guard, JsonlInviteLedger(), pause, templates,
        InviteSettings(no_message=args.no_message, max_invites=args.max_invites,
                       tech_only=not args.any_title, min_title_score=args.title_score,
                       reverse=args.reverse))
    prevent_sleep()
    try:
        use_case.run(max_pages=100)
    except KeyboardInterrupt:
        logger.warning("Stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Stopped due to error: {e}")
    finally:
        allow_sleep()
        logger.info(f"Log file: {log_path}")
