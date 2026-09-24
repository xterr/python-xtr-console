"""A command class was declared after the container was built."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["UnregisteredCommandError"]


class UnregisteredCommandError(ConsoleError):
    """A command class was declared after the container was built."""

    command_name: str

    def __init__(self, command_name: str) -> None:
        """Record the command the container knows nothing about."""
        self.command_name = command_name
        remedy = "import the module declaring it before building the container"
        super().__init__(
            f"Command {command_name!r} was declared after injectables() was called; {remedy}"
        )
