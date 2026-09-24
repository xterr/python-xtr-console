"""A command returned something that is not an exit code."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["InvalidCommandResultError"]


class InvalidCommandResultError(ConsoleError):
    """A command returned something that is not an exit code."""

    command_name: str
    result_type: str

    def __init__(self, command_name: str, result_type: str) -> None:
        """Record the command and the type of what it returned."""
        self.command_name = command_name
        self.result_type = result_type
        expected = "a command returns an int or an ExitCode"
        super().__init__(f"Command {command_name!r} returned {result_type}; {expected}")
