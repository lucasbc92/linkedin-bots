"""Questions asked on the terminal."""

YES_ANSWERS = ("y", "yes", "s", "sim")


def ask_yes_no(question):
    """Ask on stdin; True for an English or Portuguese yes."""
    return input(question).strip().lower() in YES_ANSWERS
