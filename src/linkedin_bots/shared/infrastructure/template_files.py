"""Reading message templates from disk."""
import logging
import os

from linkedin_bots.shared.domain.messages import DEFAULT_MESSAGE, MessageTemplates

logger = logging.getLogger("linkedin_bot")


def load_templates(file_path, max_length=None, default=DEFAULT_MESSAGE):
    """Load a template file; a missing, empty or unreadable one yields ``default``."""
    if not file_path:
        return MessageTemplates([default], max_length)
    try:
        if not os.path.exists(file_path):
            logger.warning(f"Message file '{file_path}' not found. Using default.")
            return MessageTemplates([default], max_length)
        with open(file_path, encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        logger.error(f"Error loading message file: {e}. Using default.")
        return MessageTemplates([default], max_length)
    return MessageTemplates.from_text(raw, max_length=max_length, default=default,
                                      source=file_path)
