"""Running an application in a test, and reading what it printed."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING, final

from rich.console import Console

from xtr_console.style import ConsoleStyle
from xtr_console.verbosity import Verbosity

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_console.application import Application

__all__ = ["ApplicationTester"]

_DEFAULT_WIDTH = 100


@final
class ApplicationTester:
    """Runs an application the way a shell would, capturing everything it prints.

    Output is captured as plain text — no colour, a fixed width — so a test
    can assert on it. Answers to questions are fed from ``inputs``, one per
    line, in the order asked::

        tester = ApplicationTester(application)
        assert await tester.execute(["user:create", "ada@example.com"]) == ExitCode.SUCCESS
        assert "created" in tester.display
    """

    __slots__ = ("_application", "_display", "_error_display", "_status_code", "_width")

    def __init__(self, application: Application, *, width: int = _DEFAULT_WIDTH) -> None:
        """Test ``application``, rendering output ``width`` columns wide."""
        self._application = application
        self._width = width
        self._display = ""
        self._error_display = ""
        self._status_code: int | None = None

    async def execute(
        self,
        argv: Sequence[str] = (),
        *,
        inputs: Sequence[str] = (),
        interactive: bool = True,
        verbosity: Verbosity = Verbosity.NORMAL,
    ) -> int:
        """Run ``argv`` on the running event loop and return the exit code.

        ``verbosity`` is where the run starts; a global option in ``argv``,
        such as ``-vvv``, still changes it. ``SHELL_VERBOSITY`` is not read.
        """
        output, errors = StringIO(), StringIO()
        style = ConsoleStyle(
            self._console(output),
            self._console(errors),
            input_stream=StringIO("".join(f"{line}\n" for line in inputs)),
            interactive=interactive,
            verbosity=verbosity,
        )
        try:
            self._status_code = await self._application.run_async(argv, style=style)
        finally:
            self._display = output.getvalue()
            self._error_display = errors.getvalue()
        return self._status_code

    @property
    def display(self) -> str:
        """Return what the last run printed to standard output."""
        return self._display

    @property
    def error_display(self) -> str:
        """Return what the last run printed to standard error."""
        return self._error_display

    @property
    def status_code(self) -> int | None:
        """Return the last run's exit code, or ``None`` before the first."""
        return self._status_code

    def _console(self, file: StringIO) -> Console:
        return Console(
            file=file,
            width=self._width,
            force_terminal=False,
            color_system=None,
            highlight=False,
            legacy_windows=False,
        )
