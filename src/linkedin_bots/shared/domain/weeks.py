"""The logging week: Sunday 21:00 to Sunday 21:00, São Paulo time."""
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

BRT = ZoneInfo("America/Sao_Paulo")

# A logging week runs Sunday to Sunday, starting at Sunday 21:00 BRT; runs
# are appended to that week's file.
_WEEK_START_HOUR = 21
_WEEK_START_WEEKDAY = 6  # Sunday (Monday=0 … Sunday=6, per date.weekday())


def current_week_start(now=None):
    """Return the Sunday date that identifies the current logging week."""
    now = (now or datetime.now(BRT)).astimezone(BRT)
    days_since_start = (now.weekday() - _WEEK_START_WEEKDAY) % 7
    sunday = (now - timedelta(days=days_since_start)).date()
    boundary = datetime.combine(sunday, dtime(_WEEK_START_HOUR, 0), tzinfo=BRT)
    if now < boundary:
        sunday -= timedelta(days=7)
    return sunday
