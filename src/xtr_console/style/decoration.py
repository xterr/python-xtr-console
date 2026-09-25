"""Forcing a console's ANSI output on or off: what ``--ansi`` and ``--no-ansi`` do."""

from __future__ import annotations

import sys

from rich.console import Console

__all__ = ["is_decorated", "redecorated"]


def is_decorated(console: Console) -> bool:
    """Report whether ``console`` writes ANSI colours and styles."""
    return console.is_terminal and console.color_system is not None


def redecorated(console: Console, decorated: bool) -> Console:
    """Return a console writing where ``console`` does, ANSI codes forced on or off.

    rich settles whether a console is a terminal as it is built, so the
    choice takes a new console. It keeps the stream — standard output or
    error still resolved as it writes, so a redirection is followed — and
    whether it is quiet. A terminal keeps following its size; anything else
    keeps the width it has.
    """
    standard = sys.stderr if console.stderr else sys.stdout
    return Console(
        file=None if console.file is standard else console.file,
        stderr=console.stderr,
        width=None if console.is_terminal and decorated else console.width,
        force_terminal=decorated,
        color_system="auto" if decorated else None,
        quiet=console.quiet,
        legacy_windows=console.legacy_windows,
    )
