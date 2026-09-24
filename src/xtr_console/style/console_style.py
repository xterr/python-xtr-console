"""One way for every command to talk to the person at the terminal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar, final

from rich import box
from rich.console import Console
from rich.errors import MarkupError
from rich.padding import Padding
from rich.progress import track
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Column, Table
from rich.text import Text

from xtr_console.exception import InvalidDefaultError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import TextIO

__all__ = ["ConsoleStyle", "block"]

T = TypeVar("T")

_BLOCK_PADDING: Final = (1, 2)


@final
class ConsoleStyle:
    """Titles, messages, tables, progress and questions, styled alike.

    A command asks for one by annotating a parameter with this class; the
    application supplies it. Messages are rich markup, so ``"[bold]x[/]"``
    renders bold — escape user data with :func:`rich.markup.escape`.

    Questions read from ``input_stream`` (the terminal when omitted). When
    ``interactive`` is off, every question returns its default unasked, the
    way a script or a CI job needs.
    """

    __slots__ = ("_console", "_error_console", "_input_stream", "_interactive")

    def __init__(
        self,
        console: Console | None = None,
        error_console: Console | None = None,
        *,
        input_stream: TextIO | None = None,
        interactive: bool = True,
    ) -> None:
        """Write to ``console``, and errors about the run to ``error_console``."""
        self._console = console if console is not None else Console()
        self._error_console = error_console if error_console is not None else Console(stderr=True)
        self._input_stream = input_stream
        self._interactive = interactive

    @property
    def console(self) -> Console:
        """Return the console output goes to, for anything rich can render."""
        return self._console

    @property
    def error_console(self) -> Console:
        """Return the console errors about the run itself go to."""
        return self._error_console

    @property
    def interactive(self) -> bool:
        """Report whether questions are asked or answered with their default."""
        return self._interactive

    # ─── structure ───────────────────────────────────────────────

    def title(self, message: str) -> None:
        """Open the output with a prominent, underlined heading."""
        self._console.print()
        self._console.print(_markup(message, "bold green"))
        self._console.print(Rule(style="green", characters="="), width=_width_of(message))
        self._console.print()

    def section(self, message: str) -> None:
        """Start a part of the output with a smaller heading."""
        self._console.print()
        self._console.print(_markup(message, "bold yellow"))
        self._console.print(Rule(style="yellow", characters="-"), width=_width_of(message))
        self._console.print()

    def text(self, message: str) -> None:
        """Write a line of text."""
        self._console.print(_markup(message))

    def listing(self, items: Iterable[str]) -> None:
        """Write an unordered list."""
        for item in items:
            self._console.print(Text(" * ") + _markup(item))
        self._console.print()

    def newline(self, count: int = 1) -> None:
        """Write ``count`` blank lines."""
        for _ in range(count):
            self._console.print()

    def table(self, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
        """Write rows under a header, in aligned columns."""
        columns = [Column(header=_markup(header)) for header in headers]
        table = Table(*columns, box=box.SQUARE, header_style="green")
        for row in rows:
            table.add_row(*(_markup(cell) for cell in row))
        self._console.print(table)

    # ─── outcomes ────────────────────────────────────────────────

    def success(self, message: str) -> None:
        """Report that the command did what it set out to do."""
        self._block("OK", message, "black on green")

    def error(self, message: str) -> None:
        """Report that the command failed."""
        self._block("ERROR", message, "white on red")

    def warning(self, message: str) -> None:
        """Report something that went wrong without stopping the command."""
        self._block("WARNING", message, "black on yellow")

    def caution(self, message: str) -> None:
        """Ask for attention before something with consequences."""
        self._block("CAUTION", message, "white on red")

    def note(self, message: str) -> None:
        """Point something out."""
        self._block("NOTE", message, "yellow")

    def info(self, message: str) -> None:
        """Report something worth knowing."""
        self._block("INFO", message, "green")

    # ─── progress ────────────────────────────────────────────────

    def progress(
        self, items: Iterable[T], *, total: int | None = None, description: str = "Working"
    ) -> Iterable[T]:
        """Yield every item of ``items`` while a progress bar tracks them."""
        return track(items, description=description, total=total, console=self._console)

    # ─── questions ───────────────────────────────────────────────

    def ask(self, question: str, default: str = "", *, choices: Sequence[str] = ()) -> str:
        """Ask for a line of text; ``choices`` restricts what is accepted.

        Raises:
            InvalidDefaultError: If ``choices`` are given and ``default`` is
                neither empty nor one of them.
        """
        if choices and default and default not in choices:
            raise InvalidDefaultError(question, default, tuple(choices))
        if not self._interactive:
            return default
        prompt = Prompt(_question(question), console=self._console, choices=list(choices) or None)
        try:
            if default:
                answer = prompt(default=default, stream=self._input_stream)
            else:
                answer = prompt(stream=self._input_stream)
        except EOFError:
            return self._out_of_input(default)
        self._end_scripted_answer()
        # rich compares a streamed line — newline and all — against "" to
        # detect an empty answer, so from a stream the default never applies.
        return answer or default

    def ask_hidden(self, question: str) -> str:
        """Ask for a secret; what is typed is not echoed."""
        if not self._interactive:
            return ""
        if self._input_stream is None:
            try:
                answer: str = Prompt.ask(_question(question), console=self._console, password=True)
            except EOFError:
                return self._out_of_input("")
            return answer
        # rich hands a stream to getpass as where to *write* the prompt, and
        # still reads the terminal; a scripted secret is read here instead.
        self._console.print(_question(question) + ": ", end="")
        answer = self._input_stream.readline().rstrip("\n")
        self._end_scripted_answer()
        return answer

    def confirm(self, question: str, *, default: bool = False) -> bool:
        """Ask a yes-or-no question; unanswered, it is a no."""
        if not self._interactive:
            return default
        try:
            answer: bool = Confirm.ask(
                _question(question),
                console=self._console,
                default=default,
                stream=self._input_stream,
            )
        except EOFError:
            return self._out_of_input(default)
        self._end_scripted_answer()
        return answer

    def _out_of_input(self, default: T) -> T:
        """Answer with ``default``: the input ended before the question was answered."""
        self._console.print()
        return default

    def _end_scripted_answer(self) -> None:
        """End the prompt's line, which a terminal would have ended on Enter."""
        if self._input_stream is not None:
            self._console.print()

    def _block(self, label: str, message: str, style: str) -> None:
        self._console.print(block(label, _markup(message), style))
        self._console.print()


def block(label: str, message: Text, style: str) -> Padding:
    """Return ``message`` behind a ``[label]``, on a full-width band of ``style``."""
    return Padding(Text(f"[{label}] ") + message, _BLOCK_PADDING, style=style, expand=True)


def _markup(message: str, style: str = "") -> Text:
    """Render ``message`` as rich markup, or as it is when it is not valid markup.

    A stray closing tag — ``"[/]"`` in a path, a log line — would otherwise
    raise, and a command would fail over the text it meant to print.
    """
    try:
        return Text.from_markup(message, style=style)
    except MarkupError:
        return Text(message, style=style)


def _question(question: str) -> Text:
    return Text(" ") + _markup(question, "green")


def _width_of(message: str) -> int:
    return max(_markup(message).cell_len, 1)
