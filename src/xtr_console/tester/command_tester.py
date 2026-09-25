"""Running one command in a test, and reading what it printed."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_console.verbosity import Verbosity

from .application_tester import ApplicationTester

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_console.application import Application

__all__ = ["CommandTester"]


@final
class CommandTester:
    """Runs one command of an application, capturing everything it prints.

    The command line after the command's name is all a test supplies::

        tester = CommandTester(application, "user:create")
        assert await tester.execute(["ada@example.com", "--admin"]) == ExitCode.SUCCESS
    """

    __slots__ = ("_name", "_tester")

    def __init__(self, application: Application, name: str, *, width: int = 100) -> None:
        """Test the command ``application`` knows as ``name``."""
        self._name = name
        self._tester = ApplicationTester(application, width=width)

    async def execute(
        self,
        args: Sequence[str] = (),
        *,
        inputs: Sequence[str] = (),
        interactive: bool = True,
        verbosity: Verbosity = Verbosity.NORMAL,
    ) -> int:
        """Run the command with ``args`` and return its exit code."""
        return await self._tester.execute(
            [self._name, *args], inputs=inputs, interactive=interactive, verbosity=verbosity
        )

    @property
    def display(self) -> str:
        """Return what the last run printed to standard output."""
        return self._tester.display

    @property
    def error_display(self) -> str:
        """Return what the last run printed to standard error."""
        return self._tester.error_display

    @property
    def status_code(self) -> int | None:
        """Return the last run's exit code, or ``None`` before the first."""
        return self._tester.status_code
