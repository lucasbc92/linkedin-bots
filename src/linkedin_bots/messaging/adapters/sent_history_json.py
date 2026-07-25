"""The send history, as a JSON file in the user data directory.

Keyed by name, each value lists the sends to people with that name:
``[{"ts": ..., "photo": ..., "thread": ...}]``. Older entries are a bare
timestamp string (name only); they load as a one-send list.

A file that exists but cannot be read is never treated as empty — that
would make every contact in it look new — and never overwritten. Writes go
to a temporary file that is flushed to disk and then swapped in, so a crash
mid-write cannot truncate it; a swap blocked by another program holding the
file is retried, and a send that still cannot be recorded raises
HistoryUnwritable so the run stops instead of messaging people it will not
remember.
"""
import json
import logging
import os
import time
from datetime import datetime

from linkedin_bots.messaging.application.ports import HistoryUnreadable, HistoryUnwritable
from linkedin_bots.messaging.domain.past_sends import PastSend
from linkedin_bots.shared.infrastructure.paths import context_dir

logger = logging.getLogger("linkedin_bot")

# A swap that fails because another program holds the file is retried.
REPLACE_ATTEMPTS = 5
REPLACE_RETRY_SECONDS = 0.2


def default_history_file():
    return context_dir("messaging") / "sent_history.json"


class JsonSentHistory:
    def __init__(self, path=None):
        self.path = path or default_history_file()

    def load(self):
        try:
            data = self._read()
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            raise HistoryUnreadable(
                f"Send history at {self.path} is unreadable ({e}).") from e
        return {name: [PastSend(sent_at=datetime.fromisoformat(s["ts"]),
                                photo=s.get("photo"), thread=s.get("thread"))
                       for s in sends]
                for name, sends in data.items()}

    def record(self, name, photo=None, thread=None):
        try:
            data = self._read()
        except FileNotFoundError:
            data = {}
        except (OSError, ValueError) as e:
            raise HistoryUnwritable(
                f"Send history at {self.path} is unreadable ({e}); not recording "
                f"{name} rather than overwrite it.") from e

        send = {"ts": datetime.now().isoformat(timespec="seconds")}
        if photo:
            send["photo"] = photo
        if thread:
            send["thread"] = thread
        data.setdefault(name, []).append(send)

        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with open(temporary, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            self._swap_in(temporary)
        except OSError as e:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise HistoryUnwritable(
                f"Could not write send history at {self.path} ({e}).") from e

    def _swap_in(self, temporary):
        """Replace the history with ``temporary``, retrying while it is locked."""
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(temporary, self.path)
                return
            except PermissionError:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(REPLACE_RETRY_SECONDS)

    def _read(self):
        """The file as ``{name: [send dict, …]}``; raises ValueError when malformed."""
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)  # json.JSONDecodeError is a ValueError
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
        return {name: ([{"ts": sends}] if isinstance(sends, str) else sends)
                for name, sends in data.items()}
