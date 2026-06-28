import logging
import sys
from pathlib import Path

from linkedin_bots.shared.domain.weeks import current_week_start

_LOG_DIR = "logs"


def week_log_path(now=None, log_dir=_LOG_DIR):
    return Path(log_dir) / f"week-{current_week_start(now).isoformat()}.log"


def setup_logging(level=logging.DEBUG, log_file=None, log_dir=None):
    logging.addLevelName(logging.WARNING, "WARN")

    logger = logging.getLogger("linkedin_bot")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    path = Path(log_file) if log_file else week_log_path(log_dir=log_dir or _LOG_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(path, mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)
    logger.addHandler(console)

    return logger
