"""Declaring a function or a class as a console command.

A command module imports nothing but this decorator — and whatever its
command needs. Declaring and running are separate steps: the declaration
fills a registry, and an :class:`~xtr_console.Application` reads it when it
runs::

    @as_command("user:create", description="Create a user")
    async def create_user(email: str, *, admin: bool = False) -> ExitCode: ...


    @as_command("user:import")
    class ImportUsers:
        async def __call__(self, io: ConsoleStyle, path: Path, *, dry_run: bool = False) -> int: ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, overload

from xtr_console.command.command_descriptor import CommandDescriptor, default_name_of
from xtr_console.command.default_registry import default_registry

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_console.command.commands_locator_interface import CommandsLocatorInterface

__all__ = ["as_command"]

CommandT = TypeVar("CommandT", bound="Callable[..., object] | type")


@overload
def as_command(target: CommandT, /) -> CommandT: ...


@overload
def as_command(
    name: str | None = ...,
    /,
    *,
    aliases: str | Sequence[str] = ...,
    description: str | None = ...,
    hidden: bool = ...,
    registry: CommandsLocatorInterface | None = ...,
) -> Callable[[CommandT], CommandT]: ...


def as_command(
    target_or_name: CommandT | str | None = None,
    /,
    *,
    aliases: str | Sequence[str] = (),
    description: str | None = None,
    hidden: bool = False,
    registry: CommandsLocatorInterface | None = None,
) -> CommandT | Callable[[CommandT], CommandT]:
    """Declare a function, or a class whose instances are callable, as a command.

    Every property is optional, and so are the parentheses::

        @as_command                                  # named after the function
        @as_command("user:create")                   # named explicitly
        @as_command("user:create", aliases="uc")     # also answers to "uc"
        @as_command("cache:warm", hidden=True)       # runs, but is not listed

    A name like ``create_user`` becomes ``create-user``, and a class
    ``ImportUsersCommand`` becomes ``import-users``. A ``namespace:`` prefix
    groups commands in the list. ``description`` replaces the summary the
    docstring would otherwise supply — for a class, the docstring of
    ``__call__``, or failing that of the class.

    A class is built only when its command runs: with no arguments, or by a
    container when one is wired.

    Raises:
        DuplicateCommandError: If the name or an alias is already taken.
        CommandSignatureError: If a class defines no ``__call__``.
    """
    locator = registry if registry is not None else default_registry()
    alias_names = (aliases,) if isinstance(aliases, str) else tuple(aliases)

    def declare(target: CommandT) -> CommandT:
        name = target_or_name if isinstance(target_or_name, str) else default_name_of(target)
        _ = locator.register(
            CommandDescriptor(
                target=target,
                name=name,
                aliases=alias_names,
                description=description,
                hidden=hidden,
            )
        )
        return target

    if target_or_name is None or isinstance(target_or_name, str):
        return declare
    return declare(target_or_name)
