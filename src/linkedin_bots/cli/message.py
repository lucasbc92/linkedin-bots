"""linkedin-bots message — send follow-ups to existing conversations."""
import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

from linkedin_bots.cli._common import (TemplateCompleter, add_log_level,
                                       require_template, start_logging)

EPILOG = """
examples:
  linkedin-bots message
  linkedin-bots message --dry-run
  linkedin-bots message --max 10
  linkedin-bots message --date-limit 2025/12/31
  linkedin-bots message --start-date 2025/07/30
  linkedin-bots message -m message_english.txt --max 5 --dry-run
  linkedin-bots message -r -m reconnect.txt --date-limit 2024/10/20
      # click an old conversation first, then walk upward (older→newer),
      # stopping once a conversation is newer than the date limit
  linkedin-bots message --last-message-regex "You:.*"
      # only message conversations where your last message matches the regex
  linkedin-bots message --last-message-regex ".*há 7.*" --last-message-regex-custom ".*for 7.*" message_english.txt
      # Portuguese previews get the -m template, English ones message_english.txt;
      # everything matching neither regex is skipped
  linkedin-bots message --by-title --dry-run
      # recruiters get message.txt, devs dev_message.txt, everyone else generic_message.txt

templates: your own in <data home>/messaging/templates/ win over the
shipped ones in src/linkedin_bots/messaging/templates/
"""


def add_parser(sub):
    mp = sub.add_parser(
        "message",
        help="Send follow-up messages to existing connections",
        description="Walk the LinkedIn Messaging inbox and send a personalized "
                    "follow-up to every conversation (skipping Sponsored, "
                    "InMail and LinkedIn Offer), newest first.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    m_message = mp.add_argument(
        "-m", "--message", default="message.txt", metavar="FILE",
        help="Template file in the messaging templates  (default: message.txt)")
    m_message.completer = TemplateCompleter("messaging")
    mp.add_argument(
        "--date-limit", metavar="YYYY/MM/DD",
        help="Stop when a conversation is older than this date "
             "(the list is newest-first, so this halts the whole run)")
    mp.add_argument(
        "--start-date", metavar="YYYY/MM/DD",
        help="Scroll down the list, click the first conversation dated on or "
             "before this date, and start sending from there (inclusive)")
    mp.add_argument(
        "-r", "--reverse", action="store_true",
        help="Walk the list upward (older→newer) instead of downward. "
             "Flips --date-limit to mean 'stop once newer than this date'")
    mp.add_argument(
        "--dry-run", action="store_true",
        help="Preview who would be messaged and with what text — nothing is sent")
    mp.add_argument(
        "--max", dest="max_messages", type=int, metavar="N",
        help="Stop after sending N messages (blast-radius limit)")
    mp.add_argument(
        "--last-message-regex", metavar="REGEX",
        help="Only message conversations whose last message preview matches "
             "this regular expression (they get the -m template)")
    mp.add_argument(
        "--last-message-regex-custom", action="append", nargs=2, default=[],
        metavar=("REGEX", "FILE"),
        help="Send FILE instead of the -m template to conversations whose "
             "last message matches REGEX. Repeatable; checked in order, "
             "before --last-message-regex")
    mp.add_argument(
        "--by-title", action="store_true",
        help="Read each contact's headline and send the recruiter (base), dev_ or "
             "generic_ variant of the template. Opens every conversation, also in "
             "--dry-run.")
    add_log_level(mp)
    mp.set_defaults(run=run)


def sibling_name(value, prefix):
    """``prefix`` + the file name of ``value``; a path keeps its folder."""
    if os.sep in value or "/" in value:
        path = Path(value)
        return str(path.with_name(prefix + path.name))
    return prefix + value


def load_family(value, base, logger):
    """The template at ``base`` and its ``dev_``/``generic_`` siblings, each
    looked up like ``value`` itself; a missing one falls back to ``base``."""
    from linkedin_bots.messaging.domain.headline_audience import TemplateFamily, Variant
    from linkedin_bots.shared.infrastructure.template_files import load_templates
    from linkedin_bots.shared.infrastructure.templates import resolve_template

    base_variant = Variant(load_templates(str(base)), base.name)
    siblings = {}
    for audience in ("dev", "generic"):
        path = resolve_template(sibling_name(value, f"{audience}_"), "messaging")
        if path.is_file():
            siblings[audience] = Variant(load_templates(str(path)), path.name)
        else:
            logger.warning(f"{path.name} not found; {audience} contacts get {base.name}")
            siblings[audience] = base_variant
    return TemplateFamily(base_variant, siblings["dev"], siblings["generic"])


def run(args):
    logger, log_path = start_logging("messaging", args.log_level)

    message_file = require_template(args.message, "messaging", "-m/--message", logger)

    def parse_cli_date(value, flag):
        if not value:
            return None
        try:
            parts = value.replace("-", "/").split("/")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            logger.error(f"Invalid {flag} '{value}'. Use YYYY/MM/DD.")
            sys.exit(1)

    date_limit = parse_cli_date(args.date_limit, "--date-limit")
    start_date = parse_cli_date(args.start_date, "--start-date")

    def check_regex(pattern, flag):
        if pattern is None:
            return
        try:
            re.compile(pattern)
        except re.error as e:
            logger.error(f"Invalid regex for {flag}: {pattern!r} ({e})")
            sys.exit(1)

    check_regex(args.last_message_regex, "--last-message-regex")

    # (regex, filename as given, template path) — resolved and validated here
    # so a typo in a filename stops the run instead of silently sending the
    # fallback text.
    regex_templates = []
    for pattern, filename in args.last_message_regex_custom:
        check_regex(pattern, "--last-message-regex-custom")
        path = require_template(filename, "messaging",
                                "--last-message-regex-custom", logger)
        regex_templates.append((pattern, filename, path))

    logger.info("=" * 60)
    logger.info("LinkedIn Message Bot")
    logger.info(f"  Message    : {message_file}")
    logger.info(f"  Direction  : {'up (older→newer)' if args.reverse else 'down (newer→older)'}")
    logger.info(f"  Date limit : {date_limit or 'none (full list)'}")
    logger.info(f"  Start date : {start_date or 'none (top or clicked card)'}")
    logger.info(f"  Dry run    : {'yes' if args.dry_run else 'no'}")
    logger.info(f"  Max msgs   : {args.max_messages or 'unlimited'}")
    logger.info(f"  Last msg regex: {args.last_message_regex or 'none'}")
    for pattern, _, path in regex_templates:
        logger.info(f"  Custom rule: {pattern!r} -> {path}")
    logger.info(f"  By title   : {'yes' if args.by_title else 'no'}")
    logger.info(f"  Log level  : {args.log_level}")
    logger.info("=" * 60)

    # Imported here, not at module scope: they pull in Selenium.
    from linkedin_bots.messaging.adapters.selenium.conversation_list import (
        SeleniumConversationList)
    from linkedin_bots.messaging.adapters.selenium.thread_page import SeleniumThreadPage
    from linkedin_bots.messaging.adapters.sent_history_json import JsonSentHistory
    from linkedin_bots.messaging.application.send_follow_ups import (FollowUpSettings,
                                                                     SendFollowUps)
    from linkedin_bots.messaging.domain.routing import Routing, TemplateRoute
    from linkedin_bots.shared.infrastructure.browser import create_driver
    from linkedin_bots.shared.infrastructure.pacing import HumanPause
    from linkedin_bots.shared.infrastructure.sleep import allow_sleep, prevent_sleep
    from linkedin_bots.shared.infrastructure.template_files import load_templates

    # Templates are loaded up front so a bad file fails before the first thread.
    def load(value, path):
        return load_family(value, path, logger) if args.by_title else load_templates(str(path))

    routing = Routing(
        default=load(args.message, message_file),
        default_source=message_file.name,
        rules=tuple(TemplateRoute(re.compile(pattern), load(filename, path), path.name)
                    for pattern, filename, path in regex_templates),
        fallback=re.compile(args.last_message_regex) if args.last_message_regex else None)
    settings = FollowUpSettings(date_limit=date_limit, start_date=start_date,
                                dry_run=args.dry_run, max_messages=args.max_messages,
                                upward=args.reverse, by_title=args.by_title)

    driver, _ = create_driver(attach_to_existing=True)
    pause = HumanPause()
    use_case = SendFollowUps(SeleniumConversationList(driver, upward=args.reverse),
                             SeleniumThreadPage(driver, pause), JsonSentHistory(),
                             pause, routing, settings)
    prevent_sleep()
    try:
        use_case.run()
    except KeyboardInterrupt:
        logger.warning("Stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Stopped due to error: {e}")
    finally:
        allow_sleep()
        logger.info(f"Log file: {log_path}")
