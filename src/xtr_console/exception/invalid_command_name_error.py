"""A command's name or alias cannot be typed on a command line."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["InvalidCommandNameError"]


class InvalidCommandNameError(ConsoleError):
    """A command's name or alias cannot be typed on a command line."""

    name: str
    reason: str

    def __init__(self, name: str, reason: str) -> None:
        """Record the name and what is wrong with it."""
        self.name = name
        self.reason = reason
        super().__init__(f"{name!r} cannot name a command: {reason}")
