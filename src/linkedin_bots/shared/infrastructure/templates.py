"""Message templates: the user's own, then those shipped inside the package, one folder per context."""
import os
from importlib.resources import files
from pathlib import Path

from linkedin_bots.shared.infrastructure.paths import data_home


def template_dir(context):
    """``linkedin_bots/<context>/templates`` as a filesystem path."""
    return Path(str(files(f"linkedin_bots.{context}") / "templates"))


def user_template_dir(context):
    """``<data home>/<context>/templates``: the user's own templates, kept out of the repository."""
    return data_home() / context / "templates"


def resolve_template(value, context):
    """A bare filename is looked up in ``user_template_dir(context)``, then in
    ``template_dir(context)``; a path is used as-is."""
    if os.sep in value or "/" in value:
        return Path(value)
    own = user_template_dir(context) / value
    return own if own.is_file() else template_dir(context) / value
