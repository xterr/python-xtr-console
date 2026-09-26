"""One way for every command to talk to the person at the terminal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar, final

from rich import box
from rich.console import Console
from rich.errors import MarkupError
from rich.padding import Padding
from rich.progress import Progress
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Column, Table
from rich.text import Text

from xtr_console.exception import InvalidDefaultError
from xtr_console.verbosity import Verbosity

from .decoration import is_decorated, redecorated
from .progress_columns import progress_columns

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from typing import TextIO

__all__ = ["ConsoleStyle", "block"]

T = TypeVar("T")

_BLOCK_PADDING: Final = (1, 2)


@final
class ConsoleStyle:
    """Titles, messages, tables, progress and questions, styled alike.

    A command asks for one by annotating a parameter with this class; the
    application supplies it. Messages are markup, so ``"[bold]x[/]"`` renders
    bold — escape anything from outside the program with
    :func:`~xtr_console.escape`. For anything the methods below do not draw,
    :attr:`console` and :attr:`error_console` are rich's own consoles.

    Output goes to ``output`` and ``errors`` — standard output and standard
    error when omitted, which are then looked up as they are written to, so a
    redirection is followed. ``width`` fixes the width output is laid out at
    (the terminal's when omitted); ``decorated`` forces ANSI colours and
    styles on or off (detected from the output when omitted).

    Questions read from ``input_stream`` (the terminal when omitted). When
    ``interactive`` is off, every question returns its default unasked, the
    way a script or a CI job needs.

    ``verbosity`` decides what is written: below :attr:`Verbosity.NORMAL`
    (``-q``) the output writes nothing, and at :attr:`Verbosity.SILENT`
    neither does the error output. The style owns its consoles' ``quiet`` flag.
    """

    __slots__ = ("_console", "_error_console", "_input_stream", "_interactive", "_verbosity")

    def __init__(  # noqa: PLR0913 — every setting optional, all by keyword but the streams.
        self,
        output: TextIO | None = None,
        errors: TextIO | None = None,
        *,
        width: int | None = None,
        decorated: bool | None = None,
        input_stream: TextIO | None = None,
        interactive: bool = True,
        verbosity: Verbosity = Verbosity.NORMAL,
    ) -> None:
        """Write to ``output``, and errors about the run to ``errors``."""
        self._console = _rendering_console(output, stderr=False, width=width, decorated=decorated)
        self._error_console = _rendering_console(
            errors, stderr=True, width=width, decorated=decorated
        )
        self._input_stream = input_stream
        self._interactive = interactive
        self._verbosity = verbosity
        self._quiet_consoles()

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

    @interactive.setter
    def interactive(self, interactive: bool) -> None:
        self._interactive = interactive

    @property
    def verbosity(self) -> Verbosity:
        """Return how much the command was told to say."""
        return self._verbosity

    @verbosity.setter
    def verbosity(self, verbosity: Verbosity) -> None:
        self._verbosity = verbosity
        self._quiet_consoles()

    @property
    def decorated(self) -> bool:
        """Report whether output carries ANSI colours and styles."""
        return is_decorated(self._console)

    @decorated.setter
    def decorated(self, decorated: bool) -> None:
        """Force ANSI colours and styles on or off, on both consoles."""
        self._console = redecorated(self._console, decorated)
        self._error_console = redecorated(self._error_console, decorated)

    def is_silent(self) -> bool:
        """Report whether ``--silent`` was asked for."""
        return self._verbosity is Verbosity.SILENT

    def is_quiet(self) -> bool:
        """Report whether ``-q`` was asked for — ``--silent`` is not quiet but silent."""
        return self._verbosity is Verbosity.QUIET

    def is_verbose(self) -> bool:
        """Report whether ``-v`` or more was asked for."""
        return self._verbosity >= Verbosity.VERBOSE

    def is_very_verbose(self) -> bool:
        """Report whether ``-vv`` or more was asked for."""
        return self._verbosity >= Verbosity.VERY_VERBOSE

    def is_debug(self) -> bool:
        """Report whether ``-vvv`` was asked for."""
        return self._verbosity >= Verbosity.DEBUG

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

    def text(self, message: str, *, verbosity: Verbosity = Verbosity.NORMAL) -> None:
        """Write a line of text, if the command runs at ``verbosity`` or above.

        ``Verbosity.VERBOSE`` writes only under ``-v``; ``Verbosity.QUIET``
        writes even under ``-q``, for output a script reads.
        """
        if self._verbosity < verbosity:
            return
        quiet, self._console.quiet = self._console.quiet, False
        try:
            self._console.print(_markup(message))
        finally:
            self._console.quiet = quiet

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
    ) -> Iterator[T]:
        """Yield every item of ``items`` while a progress bar tracks them.

        ``-v`` adds the count done, ``-vv`` the time elapsed; ``-q`` hides the bar.
        """
        columns = progress_columns(self._verbosity)
        hidden = self._verbosity <= Verbosity.QUIET
        with Progress(*columns, console=self._console, disable=hidden) as bar:
            yield from bar.track(items, total=total, description=description)

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

    def _quiet_consoles(self) -> None:
        """Silence output below normal verbosity, and errors too when silent."""
        self._console.quiet = self._verbosity < Verbosity.NORMAL
        self._error_console.quiet = self._verbosity < Verbosity.QUIET


def _rendering_console(
    stream: TextIO | None, *, stderr: bool, width: int | None, decorated: bool | None
) -> Console:
    """Build what renders to ``stream`` — standard output or error when ``None``.

    Left to itself (``decorated=None``) the console detects whether it writes
    to a terminal; forced on or off, it writes ANSI codes or never does.
    """
    if decorated is None:
        return Console(file=stream, stderr=stderr, width=width)
    return Console(
        file=stream,
        stderr=stderr,
        width=width,
        force_terminal=decorated,
        color_system="auto" if decorated else None,
        legacy_windows=False if stream is not None else None,
    )


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
