"""Helpers every command shares: log set-up and template resolution."""
import logging
import sys

from argcomplete.completers import BaseCompleter

from linkedin_bots.shared.infrastructure.logging_setup import setup_logging, week_log_path
from linkedin_bots.shared.infrastructure.paths import log_dir
from linkedin_bots.shared.infrastructure.templates import resolve_template, template_dir

LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]


def add_log_level(parser):
    parser.add_argument(
        "-l", "--log-level", default="INFO", choices=LOG_LEVELS,
        help="Log verbosity (default: INFO)")


def start_logging(context, level_name):
    """Log to this context's weekly file and the console.

    Returns ``(logger, log file path)``; the path is logged now and again
    when the run ends, since the file lives outside the repository.
    """
    level = (logging.WARNING if level_name == "WARN"
             else getattr(logging, level_name, logging.INFO))
    path = week_log_path(log_dir=log_dir(context))
    logger = setup_logging(level=level, log_file=path)
    logger.info(f"Log file: {path}")
    return logger, path


class TemplateCompleter(BaseCompleter):
    """Complete ``-m`` with the .txt templates shipped for one context."""

    def __init__(self, context):
        self._context = context

    def __call__(self, prefix, **kwargs):
        try:
            return [p.name for p in template_dir(self._context).iterdir()
                    if p.suffix == ".txt" and p.name.startswith(prefix)]
        except OSError:
            return []


def require_template(value, context, flag, logger):
    """Resolve a ``-m``-style value and exit unless the file exists.

    MessageTemplates falls back to a generic "Hello {name}!" when a file is
    missing, so without this a typo in a filename sends that text to real
    contacts instead of stopping the run.
    """
    path = resolve_template(value, context)
    if not path.is_file():
        logger.error(f"Template '{path}' ({flag}) not found.")
        sys.exit(1)
    return path
