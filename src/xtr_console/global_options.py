"""The options every command takes: how much to say, in colour or not, and whether to ask."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .exit_code import ExitCode
from .verbosity import Verbosity

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from cyclopts import App, Group

    from .style import ConsoleStyle

__all__ = ["GLOBAL_FLAGS", "GlobalOptions", "list_global_options"]

_END_OF_OPTIONS: Final = "--"
_SHORT_VERBOSE: Final = re.compile(r"-v+")
_LONG_VERBOSE: Final[Mapping[str, int]] = {
    "--verbose": 1,
    "--verbose=1": 1,
    "--verbose=2": 2,
    "--verbose=3": 3,
}
_VERBOSE_LEVELS: Final = (Verbosity.VERBOSE, Verbosity.VERY_VERBOSE, Verbosity.DEBUG)
_SILENT: Final = frozenset({"--silent"})
_QUIET: Final = frozenset({"-q", "--quiet"})
_NO_INTERACTION: Final = frozenset({"-n", "--no-interaction"})
_ANSI: Final = frozenset({"--ansi"})
_NO_ANSI: Final = frozenset({"--no-ansi"})
_SWITCHES: Final = _SILENT | _QUIET | _NO_INTERACTION | _ANSI | _NO_ANSI

GLOBAL_FLAGS: Final = _SWITCHES | {"-v", "-vv", "-vvv", "--verbose"}
"""Every flag the application reads for itself, whatever the command."""

_HELP: Final = (
    ("--silent", (), "Do not output any message."),
    ("--quiet", ("-q",), "Only errors are displayed. All other output is suppressed."),
    ("--ansi", ("--no-ansi",), "Force (or disable with --no-ansi) ANSI output."),
    ("--no-interaction", ("-n",), "Do not ask any interactive question."),
    (
        "--verbose",
        ("-v",),
        "Increase the verbosity of messages: -v for more, -vv for even more, -vvv to debug.",
    ),
)


@dataclass(frozen=True, slots=True)
class GlobalOptions:
    """What the global options on a command line asked for, and the tokens left.

    They are read wherever they stand — before the command's name or after
    it — up to a bare ``--``, after which every token is the command's.
    """

    verbosity: Verbosity | None
    """``None`` when no option named one."""
    decorated: bool | None
    """``True`` for ``--ansi``, ``False`` for ``--no-ansi``, ``None`` for neither."""
    interactive: bool
    """``False`` for ``-n``."""
    remaining: tuple[str, ...]
    """The command line without them."""

    @classmethod
    def parse(cls, tokens: Sequence[str]) -> GlobalOptions:
        """Take the global options out of ``tokens``.

        ``--silent`` wins over ``-q``, which wins over ``-v``; the most
        ``-v`` given wins among those, ``--ansi`` over ``--no-ansi``.
        """
        seen: set[str] = set()
        level = 0
        remaining: list[str] = []
        for index, token in enumerate(tokens):
            if token == _END_OF_OPTIONS:
                remaining.extend(tokens[index:])
                break
            verbose = _verbose_level(token)
            if verbose is not None:
                level = max(level, verbose)
            elif token in _SWITCHES:
                seen.add(token)
            else:
                remaining.append(token)
        return cls(
            verbosity=_verbosity(seen, level),
            decorated=_decorated(seen),
            interactive=not _given(seen, _NO_INTERACTION),
            remaining=tuple(remaining),
        )

    def apply(self, style: ConsoleStyle) -> None:
        """Set ``style`` as asked; running quiet, or ``-n``, asks no questions."""
        if self.verbosity is not None:
            style.verbosity = self.verbosity
        if self.decorated is not None:
            style.decorated = self.decorated
        if not self.interactive or style.verbosity <= Verbosity.QUIET:
            style.interactive = False


def list_global_options(app: App, group: Group) -> None:
    """Show the global options in ``app``'s help, in ``group``.

    Listed only: they are taken out of the command line before it is parsed,
    so what is registered here never runs.
    """
    for name, aliases, description in _HELP:
        _ = app.command(_listed_only, name=name, alias=aliases, group=group, help=description)


def _listed_only() -> int:
    return ExitCode.SUCCESS


def _verbose_level(token: str) -> int | None:
    """Return how many ``-v`` ``token`` counts for, or ``None`` if it is none."""
    if _SHORT_VERBOSE.fullmatch(token):
        return len(token) - 1
    return _LONG_VERBOSE.get(token)


def _verbosity(seen: Collection[str], level: int) -> Verbosity | None:
    if _given(seen, _SILENT):
        return Verbosity.SILENT
    if _given(seen, _QUIET):
        return Verbosity.QUIET
    if level:
        return _VERBOSE_LEVELS[min(level, len(_VERBOSE_LEVELS)) - 1]
    return None


def _decorated(seen: Collection[str]) -> bool | None:
    if _given(seen, _ANSI):
        return True
    if _given(seen, _NO_ANSI):
        return False
    return None


def _given(seen: Collection[str], flags: frozenset[str]) -> bool:
    return not flags.isdisjoint(seen)
