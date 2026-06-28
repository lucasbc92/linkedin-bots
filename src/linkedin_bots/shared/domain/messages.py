"""Message templates: variations, the {name} placeholder, LinkedIn's length cap.

Pure: parsing a template's text and personalizing it. Reading the file is
the infrastructure's job (``shared/infrastructure/template_files.py``).
"""
import logging
import random
import re

logger = logging.getLogger("linkedin_bot")

_SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)
DEFAULT_MESSAGE = "Hello {name}! I'd like to connect with you."


def truncate_units(text, limit):
    """``text`` cut to at most ``limit`` UTF-16 code units, the way LinkedIn
    counts (an emoji is two), never splitting a character."""
    out, used = [], 0
    for ch in text:
        width = 2 if ord(ch) > 0xFFFF else 1
        if used + width > limit:
            break
        out.append(ch)
        used += width
    return "".join(out)


class MessageTemplates:
    """Variations of one message; a random one is personalized per send.

    Args:
        variations: The variation texts, already parsed.
        max_length: If set, a variation longer than this (in UTF-16 code
            units) has its ``{name}`` dropped, then is truncated. ``None``
            means no cap (direct messages have none).
    """

    def __init__(self, variations, max_length=None):
        self._templates = list(variations)
        self._max_length = max_length

    @classmethod
    def from_text(cls, raw, max_length=None, default=DEFAULT_MESSAGE, source=""):
        """Parse a template file's text: variations separated by a ``---`` line."""
        variations = [v.strip() for v in _SEPARATOR.split(raw or "")]
        variations = [v for v in variations if v]
        if not variations:
            logger.warning("Message file is empty. Using default.")
            return cls([default], max_length)

        if max_length is not None:
            cleaned = []
            for v in variations:
                # Only the text without {name} has to fit: personalize()
                # drops the name when it would not. Cutting the raw text
                # could split the placeholder itself.
                nameless = re.sub(r",?\s*\{name\}", "", v)
                if cls._char_len(nameless) > max_length:
                    v = truncate_units(nameless, max_length)
                    logger.warning(
                        "A message variation exceeded "
                        f"{max_length} chars and was truncated.")
                cleaned.append(v)
            variations = cleaned

        logger.info(f"Loaded {len(variations)} message variation(s) from '{source}'.")
        return cls(variations, max_length)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def personalize(self, name=None):
        """Return a random variation with ``{name}`` filled in.

        If substituting ``name`` would exceed ``max_length``, the name is
        omitted.  If the template is still too long, it is hard-truncated.
        Returns an empty string when no templates are loaded (no-message mode).
        """
        if not self._templates:
            return ""

        template = random.choice(self._templates)

        if name:
            personalized = template.replace("{name}", name)
            if self._max_length is None or self._char_len(personalized) <= self._max_length:
                return personalized
            logger.warning(
                f"Message would be {self._char_len(personalized)} chars with "
                f"'{name}' (limit {self._max_length}). Omitting name for this send.")

        return self._drop_name(template)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _char_len(text):
        """Count chars the way LinkedIn does: UTF-16 code units (emoji = 2)."""
        return len(text.encode("utf-16-le")) // 2

    def _drop_name(self, template):
        """Remove ``{name}`` and an adjacent comma/space so greeting reads cleanly."""
        result = re.sub(r",?\s*\{name\}", "", template)
        if self._max_length and self._char_len(result) > self._max_length:
            result = truncate_units(result, self._max_length)
        return result
