"""The options every command takes: how much to say, in colour or not, and whether to ask."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .exit_code import ExitCode
from .verbosity import Verbosity

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from cyclopts import App, Group

    from .style import ConsoleStyle

__all__ = ["GlobalOptions", "is_global_flag", "list_global_options"]

_END_OF_OPTIONS: Final = "--"
_SHORT_VERBOSE: Final = re.compile(r"-v+")
_LONG_VERBOSE: Final = "--verbose"
_JOINED_VERBOSE: Final = re.compile(r"--verbose=([0-9]+)")
_DIGITS: Final = re.compile(r"[0-9]+")
_VERBOSE_LEVELS: Final = (Verbosity.VERBOSE, Verbosity.VERY_VERBOSE, Verbosity.DEBUG)
_SILENT: Final = frozenset({"--silent"})
_QUIET: Final = frozenset({"-q", "--quiet"})
_NO_INTERACTION: Final = frozenset({"-n", "--no-interaction"})
_ANSI: Final = frozenset({"--ansi"})
_NO_ANSI: Final = frozenset({"--no-ansi"})
_SWITCHES: Final = _SILENT | _QUIET | _NO_INTERACTION | _ANSI | _NO_ANSI

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
    taken: tuple[str, ...] = ()
    """The tokens read as global options, in order — to explain an option left without a value."""

    @classmethod
    def parse(cls, tokens: Sequence[str]) -> GlobalOptions:
        """Take the global options out of ``tokens``.

        ``--silent`` wins over ``-q``, which wins over ``-v``; the most
        ``-v`` given wins among those, ``--ansi`` over ``--no-ansi``. A
        verbosity above the highest is that highest, however it is spelled:
        ``-vvvv``, ``--verbose=9`` and ``--verbose 9`` all debug.
        """
        seen: set[str] = set()
        level = 0
        remaining: list[str] = []
        taken: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == _END_OF_OPTIONS:
                remaining.extend(tokens[index:])
                break
            verbose = _verbose(tokens, index)
            if verbose is not None:
                asked, span = verbose
                level = max(level, asked)
                taken.extend(tokens[index : index + span])
                index += span
                continue
            index += 1
            if token in _SWITCHES:
                seen.add(token)
                taken.append(token)
            else:
                remaining.append(token)
        return cls(
            verbosity=_verbosity(seen, level),
            decorated=_decorated(seen),
            interactive=not _given(seen, _NO_INTERACTION),
            remaining=tuple(remaining),
            taken=tuple(taken),
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


def is_global_flag(name: str) -> bool:
    """Tell whether the application takes ``name`` for itself, as it reads a command line.

    Asks the same matcher the command line is read with, so no spelling it
    takes — ``-vvvv`` as much as ``-v`` — is missed.
    """
    return _verbose_level(name) is not None or name in _SWITCHES


def _listed_only() -> int:
    return ExitCode.SUCCESS


def _verbose(tokens: Sequence[str], index: int) -> tuple[int, int] | None:
    """Return the verbosity asked for at ``index``, and how many tokens it spans.

    ``None`` when the token asks for none. Only the long spelling takes a
    detached value — ``--verbose 2`` — so ``-v 2`` still leaves the ``2`` to
    the command, where a count would read as an argument.
    """
    token = tokens[index]
    joined = _verbose_level(token)
    if joined is None:
        return None
    if token != _LONG_VERBOSE or index + 1 >= len(tokens):
        return joined, 1
    detached = _level(tokens[index + 1])
    return (joined, 1) if detached is None else (detached, 2)


def _verbose_level(token: str) -> int | None:
    """Return how many ``-v`` ``token`` counts for on its own, or ``None`` if it is none."""
    if _SHORT_VERBOSE.fullmatch(token):
        return len(token) - 1
    if token == _LONG_VERBOSE:
        return 1
    joined = _JOINED_VERBOSE.fullmatch(token)
    return _level(joined[1]) if joined is not None else None


def _level(value: str) -> int | None:
    """Read a verbosity count; ``None`` when ``value`` is not one.

    Counting starts at one, as ``-v`` does: there is no spelling of ``-v``
    that asks for none, so ``0`` is not a value here.
    """
    if not _DIGITS.fullmatch(value):
        return None
    return int(value) or None


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
