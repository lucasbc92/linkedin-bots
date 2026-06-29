"""Choosing which template a conversation gets from its last-message preview."""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TemplateRoute:
    """A ``--last-message-regex-custom`` rule: matching previews get ``templates``."""

    pattern: re.Pattern
    templates: object
    source: str


@dataclass(frozen=True)
class Routing:
    """All the routing rules of a run.

    Custom rules are checked first, in order; ``fallback``
    (``--last-message-regex``) last, carrying the default template. With no
    rule at all, every card gets the default.
    """

    default: object
    default_source: str
    rules: tuple = ()
    fallback: Optional[re.Pattern] = None

    def choose(self, last_message):
        """``(templates, source, pattern)`` for this preview, or ``(None, None, None)``."""
        if not self.rules and self.fallback is None:
            return self.default, self.default_source, None
        if last_message is None:
            return None, None, None
        for route in self.rules:
            if route.pattern.search(last_message):
                return route.templates, route.source, route.pattern.pattern
        if self.fallback is not None and self.fallback.search(last_message):
            return self.default, self.default_source, self.fallback.pattern
        return None, None, None

    def patterns(self):
        """Every configured pattern, in evaluation order."""
        patterns = [route.pattern.pattern for route in self.rules]
        if self.fallback is not None:
            patterns.append(self.fallback.pattern)
        return patterns
