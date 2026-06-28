"""Where runtime data lives: logs, the invitation ledger, the send history.

Personal data (names of real contacts) and run logs stay out of the source
tree, in the per-user data directory installed CLIs use —
``%LOCALAPPDATA%/linkedin-bots`` on Windows. ``LINKEDIN_BOTS_HOME`` points it
somewhere else, which is also how the tests keep away from real data.
"""

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "linkedin-bots"
HOME_ENV = "LINKEDIN_BOTS_HOME"


class DataHomeError(ValueError):
    """``LINKEDIN_BOTS_HOME`` does not name a fixed folder."""


def data_home():
    """The root of every bot's data, honouring ``LINKEDIN_BOTS_HOME``.

    The override must be absolute (``~`` is expanded): a relative one would
    resolve against the current folder and give each folder its own empty
    send history — after which the messaging bot re-messages everyone.
    """
    override = os.environ.get(HOME_ENV)
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise DataHomeError(
                f"{HOME_ENV} must be an absolute path, got {override!r}")
        return path
    return Path(user_data_dir(APP_NAME, appauthor=False))


def context_dir(context):
    """``<data home>/<context>``, created on first use."""
    path = data_home() / context
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir(context):
    """Where one context's weekly log files go, created on first use."""
    path = context_dir(context) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
