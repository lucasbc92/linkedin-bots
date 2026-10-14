"""Who a connect run is after: the headline scorer, and what to call a match."""
from typing import Callable, NamedTuple

from linkedin_bots.connecting.domain import java_dev, tech_recruiter


class Audience(NamedTuple):
    label: str
    score: Callable


TECH_RECRUITERS = Audience("tech recruiter", tech_recruiter.score_title)
JAVA_DEVS = Audience("senior Java dev", java_dev.score_title)
