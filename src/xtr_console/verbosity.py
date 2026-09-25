"""How much a command says, from nothing at all to everything."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["SHELL_VERBOSITY", "Verbosity"]

SHELL_VERBOSITY: Final = "SHELL_VERBOSITY"
"""The environment variable carrying a verbosity, ``-2`` (silent) to ``3`` (debug)."""


class Verbosity(IntEnum):
    """How much a command was told to say: ``--silent``, ``-q``, nothing, ``-v`` to ``-vvv``.

    Ordered, so ``io.verbosity >= Verbosity.VERBOSE`` reads as it should. The
    values are xtr-logging's too, so converting between
    them is ``Other(verbosity.value)``.
    """

    SILENT = 8
    QUIET = 16
    NORMAL = 32
    VERBOSE = 64
    VERY_VERBOSE = 128
    DEBUG = 256

    @classmethod
    def from_shell(cls, value: str | None) -> Verbosity:
        """Read a ``SHELL_VERBOSITY`` value; anything but ``-2`` to ``3`` is normal."""
        try:
            level = int(value) if value is not None else 0
        except ValueError:
            return cls.NORMAL
        return _BY_SHELL_LEVEL.get(level, cls.NORMAL)

    @property
    def shell_level(self) -> int:
        """Return the ``SHELL_VERBOSITY`` value naming this verbosity."""
        return _SHELL_LEVELS[self]


_BY_SHELL_LEVEL: Final[Mapping[int, Verbosity]] = {
    -2: Verbosity.SILENT,
    -1: Verbosity.QUIET,
    0: Verbosity.NORMAL,
    1: Verbosity.VERBOSE,
    2: Verbosity.VERY_VERBOSE,
    3: Verbosity.DEBUG,
}
_SHELL_LEVELS: Final[Mapping[Verbosity, int]] = {
    verbosity: level for level, verbosity in _BY_SHELL_LEVEL.items()
}
