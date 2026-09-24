"""The contract for the registry commands are declared into."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .command_descriptor import CommandDescriptor

__all__ = ["CommandsLocatorInterface"]


@runtime_checkable
class CommandsLocatorInterface(Protocol):
    """Holds every declared command.

    Declaring a command writes to it and building an application reads from
    it; they are the same registry, so the contract covers both.
    """

    def register(self, command: CommandDescriptor) -> CommandDescriptor:
        """Add ``command`` and return it."""
        ...

    def commands(self) -> tuple[CommandDescriptor, ...]:
        """Return every command, in the order declared."""
        ...
