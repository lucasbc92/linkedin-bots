"""Humanizing pauses between actions."""

import logging
import random
import time

logger = logging.getLogger("linkedin_bot")

# Fast mode (--fast) keeps the jitter of the humanizing pauses but shrinks the
# window to this fraction, never dropping below MIN_FAST_PAUSE seconds — some
# gap is still needed for LinkedIn's UI to settle between actions.
FAST_PAUSE_FACTOR = 0.1
MIN_FAST_PAUSE = 0.5


class HumanPause:
    """Sleep a randomized interval so the rhythm doesn't read as a script."""

    def __init__(self, fast=False):
        self.fast = fast

    def seconds(self, low, high):
        """How long the next pause should last, in seconds."""
        delay = random.uniform(low, high)
        if self.fast:
            delay = max(delay * FAST_PAUSE_FACTOR, MIN_FAST_PAUSE)
        return delay

    def __call__(self, low, high):
        delay = self.seconds(low, high)
        logger.debug(f"Pausing {delay:.1f}s{' (fast)' if self.fast else ''}")
        time.sleep(delay)
