"""Reading LinkedIn's relative invitation ages.

Cards carry a relative age ("Sent 3 months ago"), never a date. LinkedIn
rounds those down, so "3 months ago" means *at least* three months — the
date derived from a label is therefore the newest the invitation can
possibly be. Withdrawal only ever fires when that newest-possible date is
already past the cutoff, so an invitation is never withdrawn on a guess.
"""

import logging
import re
from datetime import date, timedelta

logger = logging.getLogger("linkedin_bot")

# The "Sent 9 hours ago" line inside a card, in either UI language.
_SENT_LABEL_RE = re.compile(r"^(sent|enviad)", re.IGNORECASE)

# Relative-age units, English and Portuguese, mapped to a common key.
_AGE_UNITS = (
    ("minute", "minutes"), ("minutes", "minutes"),
    ("minuto", "minutes"), ("minutos", "minutes"),
    ("hour", "hours"), ("hours", "hours"),
    ("hora", "hours"), ("horas", "hours"),
    ("day", "days"), ("days", "days"), ("dia", "days"), ("dias", "days"),
    ("week", "weeks"), ("weeks", "weeks"),
    ("semana", "weeks"), ("semanas", "weeks"),
    ("month", "months"), ("months", "months"),
    ("mes", "months"), ("meses", "months"),
    ("year", "years"), ("years", "years"),
    ("ano", "years"), ("anos", "years"),
)
_AGE_UNIT_BY_WORD = dict(_AGE_UNITS)

# Shorthand accepted by --until: "2m", "3w", "10d", "1y". Minutes and hours
# are deliberately absent — a cutoff measured in minutes is never meant.
_SHORT_UNITS = {"d": "days", "w": "weeks", "m": "months", "y": "years"}

# "Sent today" / "Enviado ontem" — no number to read.
_TODAY_WORDS = ("today", "hoje", "now", "agora")
_YESTERDAY_WORDS = ("yesterday", "ontem")


def _subtract_months(anchor, months):
    """``anchor`` shifted back whole calendar months, clamped to month length."""
    total = anchor.year * 12 + (anchor.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    day = anchor.day
    while day > 1:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, 1)


def parse_sent_age(raw, today=None):
    """Parse a card's "Sent …" line into the newest date it can represent.

    LinkedIn rounds ages down — "Sent 3 months ago" covers everything from
    three to four months old — so the returned date is the *upper bound* of
    when the invitation was sent. Callers can therefore treat
    ``parsed <= cutoff`` as proof the invitation predates the cutoff.

    Handles both UI languages:
    - ``"Sent 40 minutes ago"`` / ``"Enviado há 40 minutos"``  → today
    - ``"Sent 9 hours ago"`` / ``"Enviado há 9 horas"``        → today (or
      the previous day once the hours pass a full day)
    - ``"Sent 3 days ago"`` / ``"Enviado há 3 dias"``          → today − 3d
    - ``"Sent 2 weeks ago"`` / ``"Enviado há 2 semanas"``      → today − 14d
    - ``"Sent 3 months ago"`` / ``"Enviado há 3 meses"``       → today − 3 months
    - ``"Sent 1 year ago"`` / ``"Enviado há 1 ano"``           → today − 12 months
    - Anything unrecognized                                    → ``None``,
      and the card is left untouched.
    """
    if today is None:
        today = date.today()
    if not raw:
        return None

    text = raw.strip().lower()
    # Strip accents on the few words that carry them ("há", "mês").
    text = text.replace("á", "a").replace("ê", "e").replace("ó", "o")

    words = re.findall(r"[a-z]+", text)
    if any(w in _TODAY_WORDS for w in words):
        return today
    if any(w in _YESTERDAY_WORDS for w in words):
        return today - timedelta(days=1)

    match = re.search(r"(\d+)\s*([a-z]+)", text)
    if match:
        amount, word = int(match.group(1)), match.group(2)
    else:
        # "Sent a month ago" / "Enviado há um mes" — implicit 1.
        word = next((w for w in words if w in _AGE_UNIT_BY_WORD), None)
        if word is None:
            logger.debug(f"Could not parse age '{raw}' — leaving the card alone.")
            return None
        amount = 1

    unit = _AGE_UNIT_BY_WORD.get(word)
    if unit is None:
        logger.debug(f"Could not parse age '{raw}' — leaving the card alone.")
        return None

    if unit == "minutes":
        return today
    if unit == "hours":
        return today - timedelta(days=amount // 24)
    if unit == "days":
        return today - timedelta(days=amount)
    if unit == "weeks":
        return today - timedelta(weeks=amount)
    if unit == "months":
        return _subtract_months(today, amount)
    if unit == "years":
        return _subtract_months(today, amount * 12)
    return None


def parse_until(value, today=None):
    """Resolve a ``--until`` argument into a cutoff ``date``.

    Two forms:
    - absolute — ``"2026/06/20"`` or ``"2026-06-20"``
    - relative — ``"2m"``, ``"3w"``, ``"10d"``, ``"1y"`` (also spelled out:
      ``"2 months"``, ``"2 meses"``), meaning "that far back from today"

    The relative form runs the same arithmetic as ``parse_sent_age``, so
    ``--until 2m`` lines up exactly with the cards labelled "Sent 2 months
    ago" — the boundary can't drift between how a card is read and how the
    cutoff is computed.

    Raises ``ValueError`` on anything unrecognized; the CLI turns that into
    an error message rather than a stack trace.
    """
    if today is None:
        today = date.today()
    text = (value or "").strip().lower()
    if not text:
        raise ValueError("no date given")

    absolute = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", text)
    if absolute:
        try:
            return date(*(int(part) for part in absolute.groups()))
        except ValueError as e:
            raise ValueError(f"'{value}' is not a real date ({e})") from None

    relative = re.match(r"^(\d+)\s*([a-z]+)$", text.replace("á", "a").replace("ê", "e"))
    if relative:
        amount = int(relative.group(1))
        word = relative.group(2)
        # Full words first ("months", "meses"), then the single-letter form.
        unit = _AGE_UNIT_BY_WORD.get(word) or _SHORT_UNITS.get(word[0])
        if unit == "days":
            return today - timedelta(days=amount)
        if unit == "weeks":
            return today - timedelta(weeks=amount)
        if unit == "months":
            return _subtract_months(today, amount)
        if unit == "years":
            return _subtract_months(today, amount * 12)

    raise ValueError(
        f"'{value}' is neither YYYY/MM/DD nor a relative age like 2m, 3w, "
        f"10d or 1y")


def reached_cutoff(labels, cutoff, today=None):
    """True once the loaded list stretches back to ``cutoff``.

    ``labels`` are the raw "Sent …" lines in list order (newest first), so
    the last parsable one is the oldest invitation loaded so far. Used as
    ``scroll_to_end``'s stop condition: there is no reason to keep loading
    pages past the point where withdrawal stops.
    """
    for raw in reversed(list(labels)):
        sent = parse_sent_age(raw, today=today)
        if sent is not None:
            return sent <= cutoff
    return False


def oldest_label(labels, today=None):
    """The "Sent …" line of the oldest invitation among ``labels``, or None.

    Picked by age, not position: the last card can be hours old while
    month-old invitations sit above it. Falls back to the last "Sent …" line
    when none of them can be parsed.
    """
    sent = [text for text in labels if _SENT_LABEL_RE.match(text)]
    dated = [(parse_sent_age(text, today=today), text) for text in sent]
    dated = [pair for pair in dated if pair[0] is not None]
    if dated:
        return min(dated, key=lambda pair: pair[0])[1]
    return sent[-1] if sent else None
