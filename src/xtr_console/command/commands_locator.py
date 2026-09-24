"""The registry commands are declared into."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_console.exception import DuplicateCommandError

from .commands_locator_interface import CommandsLocatorInterface

if TYPE_CHECKING:
    from .command_descriptor import CommandDescriptor

__all__ = ["CommandsLocator"]


@final
class CommandsLocator(CommandsLocatorInterface):
    """Holds every declared command, keyed by each name it answers to."""

    __slots__ = ("_by_name", "_commands")

    def __init__(self) -> None:
        """Start empty."""
        self._commands: list[CommandDescriptor] = []
        self._by_name: dict[str, CommandDescriptor] = {}

    @override
    def register(self, command: CommandDescriptor) -> CommandDescriptor:
        """Add ``command`` and return it.

        Raises:
            DuplicateCommandError: If its name or an alias is already taken.
        """
        for name in command.names:
            claimed = self._by_name.get(name)
            if claimed is not None:
                raise DuplicateCommandError(name, claimed.name)
        self._commands.append(command)
        self._by_name.update(dict.fromkeys(command.names, command))
        return command

    @override
    def commands(self) -> tuple[CommandDescriptor, ...]:
        """Return every command, in the order declared."""
        return tuple(self._commands)
