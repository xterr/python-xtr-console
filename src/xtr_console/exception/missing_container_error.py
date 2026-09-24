"""A command needs a dependency-injection container, and none is wired."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["MissingContainerError"]


class MissingContainerError(ConsoleError):
    """A command needs a dependency-injection container, and none is wired."""

    command_name: str
    parameters: tuple[str, ...]

    def __init__(self, command_name: str, parameters: tuple[str, ...]) -> None:
        """Record the command and the parameters only a container can fill."""
        self.command_name = command_name
        self.parameters = parameters
        needed = ", ".join(parameters)
        remedy = "run the application a container provides, via xtr_console.integration.wireup"
        super().__init__(f"Command {command_name!r} needs {needed} from a container; {remedy}")
