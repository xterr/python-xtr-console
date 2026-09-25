"""Reporting an exception that escaped a command, in the detail the run asked for."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

import cyclopts
from rich.text import Text
from rich.traceback import Traceback

from .console_style import block

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

    from .console_style import ConsoleStyle

__all__ = ["render_exception"]

_FRAMEWORK: Final[tuple[str | ModuleType, ...]] = (str(Path(__file__).parents[1]), cyclopts)


def render_exception(error: BaseException, style: ConsoleStyle) -> None:
    """Report ``error`` on the style's error console.

    - Normally, each error in the chain — the cause first — as an
      ``[ERROR]`` block holding its message.
    - With ``-v``, a traceback, this library's and the parser's frames
      folded away.
    - With ``-vvv``, the whole traceback and every frame's local variables.
    - With ``--silent``, nothing.
    """
    console = style.error_console
    if style.is_verbose():
        debug = style.is_debug()
        traceback = Traceback.from_exception(
            type(error),
            error,
            error.__traceback__,
            show_locals=debug,
            suppress=() if debug else _FRAMEWORK,
        )
        console.print(traceback)
        return
    for link in reversed(list(_chain(error))):
        console.print(block("ERROR", Text(str(link) or type(link).__name__), "white on red"))
        console.print()


def _chain(error: BaseException) -> Iterator[BaseException]:
    """Yield ``error``, then what caused it, then what caused that."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
