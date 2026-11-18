"""A bare ``-`` on the command line: a value — standard input, by the usual convention.

The parser reads any token starting with ``-`` as an option, so a bare ``-`` — which names no
option — is refused as an unknown one. The console offers it to the command instead: before
the first ``--``, each bare ``-`` is handed to the parser as a marker the parser reads as text,
and every marker is turned back into ``-`` before the command is called. The parser parses
the marked line first, without calling anything; unless that succeeds with every marker
landing in text or a path, the line is parsed as written, so a ``-`` the command cannot take
fails exactly as before. A line without a bare ``-`` is never touched. A command's own
validator is handed ``-`` too, never the marker (see :func:`as_given`).
"""

from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING, Final, cast

from cyclopts.exceptions import CycloptsError

if TYPE_CHECKING:
    import inspect
    from collections.abc import Sequence

    from cyclopts import App

__all__ = ["STANDARD_INPUT", "as_given", "restored", "with_standard_input"]

STANDARD_INPUT: Final = "-"
"""The argument naming standard input."""

_END_OF_OPTIONS: Final = "--"

_MARKER: Final = "\x00xtr-console:standard-input"
"""What a bare ``-`` is handed to the parser as: text no command line can hold.

An argument reaches a process as a NUL-terminated string, so no token typed or passed to a
program contains ``\\x00``: the marker is never mistaken for a value someone wrote.
"""


def with_standard_input(app: App, tokens: Sequence[str]) -> Sequence[str]:
    """Return ``tokens`` with each bare ``-`` before ``--`` marked, when ``app`` can take them.

    ``tokens`` comes back as it was when it holds no bare ``-``, or when the marked line does
    not parse with every marker in text or a path: the parser then reports what it reported
    before, about the ``-`` as written.
    """
    marked = list(tokens)
    end = marked.index(_END_OF_OPTIONS) if _END_OF_OPTIONS in marked else len(marked)
    count = 0
    for index in range(end):
        if marked[index] == STANDARD_INPUT:
            marked[index] = _MARKER
            count += 1
    if not count:
        return tokens
    try:
        _, bound, _ = app.parse_args(marked, print_error=False, exit_on_error=False)
    except CycloptsError:
        return tokens
    return marked if _restorable(bound) == count else tokens


def restored(bound: inspect.BoundArguments) -> None:
    """Turn every marker in ``bound`` back into ``-``, in place."""
    arguments = cast("dict[str, object]", bound.arguments)
    for name, value in arguments.items():
        arguments[name] = as_given(value)


def as_given(value: object) -> object:
    """Return ``value`` as the command line gave it: each marker in it ``-`` again.

    Text and paths are turned back, alone or in a tuple or list; anything else is returned
    as it is.
    """
    if isinstance(value, str | PurePath):
        return type(value)(STANDARD_INPUT) if str(value) == _MARKER else value
    if isinstance(value, tuple):
        return tuple(as_given(item) for item in cast("tuple[object, ...]", value))
    if isinstance(value, list):
        return [as_given(item) for item in cast("list[object]", value)]
    return value


def _restorable(bound: inspect.BoundArguments) -> int:
    """Count the markers ``bound`` holds where :func:`restored` turns them back."""
    arguments = cast("dict[str, object]", bound.arguments)
    return sum(_markers_in(value) for value in arguments.values())


def _markers_in(value: object) -> int:
    if isinstance(value, str | PurePath):
        return 1 if str(value) == _MARKER else 0
    if isinstance(value, tuple | list):
        return sum(_markers_in(item) for item in cast("Sequence[object]", value))
    return 0
