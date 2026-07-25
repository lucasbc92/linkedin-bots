# PYTHON_ARGCOMPLETE_OK
"""linkedin-bots — command-line entry point.

Usage
-----
  linkedin-bots connect [options]   Send connection requests
  linkedin-bots message [options]   Send follow-up messages

Shell tab-completion (one-time setup)
--------------------------------------
  Bash / Git Bash:
      eval "$(register-python-argcomplete linkedin-bots)"
      # Add that line to ~/.bashrc to make it permanent.

  Zsh:
      autoload -U bashcompinit && bashcompinit
      eval "$(register-python-argcomplete linkedin-bots)"

  PowerShell:
      Register-ArgumentCompleter -Native -CommandName linkedin-bots -ScriptBlock {
          param($wordToComplete, $commandAst, $cursorPosition)
          $env:_ARGCOMPLETE=1
          $env:COMP_LINE = $commandAst.ToString()
          $env:COMP_POINT = $cursorPosition
          linkedin-bots 2>&1 | ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
      }
"""

import argparse
import sys

import argcomplete

from linkedin_bots.cli import connect, message
from linkedin_bots.shared.infrastructure.paths import DataHomeError

COMMANDS = (connect, message)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="linkedin-bots",
        description="LinkedIn automation bots. Attach Chrome with "
                    "--remote-debugging-port=9222 before running.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    for command in COMMANDS:
        command.add_parser(sub)
    argcomplete.autocomplete(parser)
    return parser


def main(argv=None):
    """Entry point of the ``linkedin-bots`` command."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "run", None) is None:
        parser.print_help()
        sys.exit(1)
    try:
        args.run(args)
    except DataHomeError as e:
        parser.error(str(e))
