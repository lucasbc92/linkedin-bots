"""Message templates shipped inside the package, one folder per context."""
import os
from importlib.resources import files
from pathlib import Path


def template_dir(context):
    """``linkedin_bots/<context>/templates`` as a filesystem path."""
    return Path(str(files(f"linkedin_bots.{context}") / "templates"))


def resolve_template(value, context):
    """A bare filename is looked up in ``template_dir(context)``; a path is used as-is."""
    if os.sep in value or "/" in value:
        return Path(value)
    return template_dir(context) / value
