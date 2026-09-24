"""The exit codes a command returns."""

from __future__ import annotations

from enum import IntEnum

__all__ = ["ExitCode"]


class ExitCode(IntEnum):
    """What a command reports back to the shell.

    A command may return any ``int``; these name the three every tool agrees
    on. ``None`` counts as :attr:`SUCCESS`.
    """

    SUCCESS = 0
    FAILURE = 1
    INVALID = 2
