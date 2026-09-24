"""A command is declared in a shape the console cannot call."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["CommandSignatureError"]


class CommandSignatureError(ConsoleError):
    """A command is declared in a shape the console cannot call."""

    command_name: str
    reason: str

    def __init__(self, command_name: str, reason: str) -> None:
        """Record the command and what is wrong with its declaration."""
        self.command_name = command_name
        self.reason = reason
        super().__init__(f"Command {command_name!r} cannot be called: {reason}")
