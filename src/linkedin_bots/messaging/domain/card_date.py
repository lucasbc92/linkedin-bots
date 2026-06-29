"""Reading the date LinkedIn prints on a conversation card."""
import logging
import re
from datetime import date, timedelta

logger = logging.getLogger("linkedin_bot")

# LinkedIn timestamp weekday abbreviations
_WEEKDAYS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_card_timestamp(raw, today=None):
    """Parse a LinkedIn conversation-card timestamp into a ``date``.

    LinkedIn uses several relative and absolute formats:
    - ``"10:01 PM"`` / ``"9:12 AM"``         → today
    - ``"Mon"`` / ``"Tue"`` etc.              → most recent past occurrence
    - ``"Jun 27"``                            → that day, current or previous year
    - ``"Jun 27, 2024"`` / ``"Mar 2024"``    → explicit year
    - Anything else                           → ``None`` (within range, don't stop)
    """
    if today is None:
        today = date.today()
    text = raw.strip()

    # "10:01 PM" / "9:12 AM" — time-only → today
    if re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)$", text, re.IGNORECASE):
        return today

    # Weekday abbreviation → most recent past occurrence within last 7 days
    key = text[:3].lower()
    if key in _WEEKDAYS and len(text) <= 4:
        target_dow = _WEEKDAYS[key]
        days_back = (today.weekday() - target_dow) % 7
        if days_back == 0:
            days_back = 7  # same weekday → last week
        return today - timedelta(days=days_back)

    # "Jun 27, 2024" — month + day + explicit year
    m = re.match(
        r"^([A-Za-z]{3})\s+(\d{1,2}),\s*(\d{4})$", text)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    # "Mar 2024" — month + year only (use the 1st of the month)
    m = re.match(r"^([A-Za-z]{3})\s+(\d{4})$", text)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            try:
                return date(int(m.group(2)), month, 1)
            except ValueError:
                pass

    # "Jun 27" — month + day, no year
    m = re.match(r"^([A-Za-z]{3})\s+(\d{1,2})$", text)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            try:
                d = date(today.year, month, int(m.group(2)))
                if d > today:
                    d = date(today.year - 1, month, int(m.group(2)))
                return d
            except ValueError:
                pass

    logger.warning(f"Could not parse timestamp '{text}' — treating as within range.")
    return None


def first_card_on_or_before(timestamps, target, today=None):
    """Index of the first card whose date is on or before ``target``.

    ``timestamps`` is an iterable of ``(card_index, raw_text)`` pairs in list
    order (newest first). Returns ``None`` when every parsable date is still
    newer than ``target``.
    """
    for idx, raw in timestamps:
        card_date = parse_card_timestamp(raw, today=today)
        if card_date and card_date <= target:
            return idx
    return None
