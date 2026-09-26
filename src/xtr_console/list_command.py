"""The built-in ``list`` command: name/version, then every command by namespace.

``app list`` prints the application's name and version line, then every
registered command with its description, grouped by namespace prefix (the
part before ``:``), sorted; ``app list <namespace>`` shows only that
namespace; an unknown namespace ends the run with
:attr:`~xtr_console.ExitCode.INVALID`.

A user command named ``list`` (or answering to it as an alias) overrides the
built-in.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final

from rich.markup import escape
from rich.text import Text

from .command.command_descriptor import CommandDescriptor, function_of
from .exit_code import ExitCode
from .style import ConsoleStyle  # noqa: TC001 — evaluated at runtime by CommandSignature.of.

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

__all__ = ["BUILTIN_LIST_NAME", "with_builtin_list"]

BUILTIN_LIST_NAME: Final = "list"
"""The name the built-in command answers to."""

_BUILTIN_LIST_DESCRIPTION: Final = "List commands"
_GAP: Final = 2


def with_builtin_list(
    declared: Sequence[CommandDescriptor],
    name: str,
    version: str | None,
    description: str | None,
) -> tuple[CommandDescriptor, ...]:
    """Return ``declared`` plus a built-in ``list`` command; a user's ``list`` wins.

    A user command whose name or one of its aliases is ``list`` overrides:
    the built-in is not added, so the user's command answers ``app list``.

    The built-in reflects ``declared`` at call time — what a container-driven
    :class:`~xtr_console.CommandsLocator` currently holds, or what the
    process-wide default registry does — so environment filtering carries
    through unchanged.
    """
    if any(BUILTIN_LIST_NAME in command.names for command in declared):
        return tuple(declared)
    listing: list[CommandDescriptor] = list(declared)
    descriptor = CommandDescriptor(
        target=_make_list_command(name, version, description, listing),
        name=BUILTIN_LIST_NAME,
        description=_BUILTIN_LIST_DESCRIPTION,
    )
    listing.append(descriptor)
    return tuple(listing)


def _make_list_command(
    name: str,
    version: str | None,
    description: str | None,
    listing: Sequence[CommandDescriptor],
) -> Callable[..., Awaitable[int]]:
    """Return the coroutine the ``list`` descriptor calls, closing over the listing."""

    async def list_commands(  # noqa: D417 — ``io`` is framework-supplied, not part of the CLI.
        io: ConsoleStyle, namespace: str | None = None
    ) -> int:
        """List commands, grouped by namespace.

        Args:
            namespace: Only list commands whose name is prefixed by
                ``<namespace>:``. Unknown ends the run with
                :attr:`~xtr_console.ExitCode.INVALID`.
        """
        visible = tuple(command for command in listing if not command.hidden)
        if namespace is not None:
            selected = tuple(command for command in visible if command.namespace == namespace)
            if not selected:
                io.error(f'There are no commands defined in the "{namespace}" namespace.')
                return ExitCode.INVALID
            _print_header(io, name, version, description)
            io.console.print(
                Text.from_markup(
                    f'[bold yellow]Available commands for the "{escape(namespace)}" namespace:[/]'
                )
            )
            _print_group(io, sorted(selected, key=_by_name))
            return ExitCode.SUCCESS
        _print_header(io, name, version, description)
        io.console.print(Text.from_markup("[bold yellow]Available commands:[/]"))
        without = tuple(command for command in visible if command.namespace is None)
        if without:
            _print_group(io, sorted(without, key=_by_name))
        spaced = sorted({c.namespace for c in visible if c.namespace is not None})
        for group in spaced:
            io.console.print(Text.from_markup(f" [yellow]{escape(group)}[/yellow]"))
            _print_group(io, sorted((c for c in visible if c.namespace == group), key=_by_name))
        return ExitCode.SUCCESS

    return list_commands


def _print_header(
    io: ConsoleStyle, name: str, version: str | None, description: str | None
) -> None:
    """Print the application's name and version line, then any description."""
    header = f"[green]{escape(name)}[/green]"
    if version is not None:
        header = f"{header} [yellow]{escape(version)}[/yellow]"
    io.console.print(Text.from_markup(header))
    if description is not None:
        io.newline()
        io.console.print(escape(description))
    io.newline()


def _print_group(io: ConsoleStyle, commands: Sequence[CommandDescriptor]) -> None:
    """Print ``commands`` as two columns: name (with aliases) and description."""
    width = max((len(_label(command)) for command in commands), default=0)
    for command in commands:
        label = _label(command)
        padding = " " * (width - len(label) + _GAP)
        line = Text("  ")
        _ = line.append(label, style="green")
        _ = line.append(padding)
        _ = line.append(_summary(command))
        io.console.print(line)


def _summary(command: CommandDescriptor) -> str:
    """Return what a listing says of ``command``, as its ``--help`` page does.

    Its ``description`` when one was given; else the first line of the docstring of the
    function that runs — a class's ``__call__`` — or failing that of the class.
    """
    if command.description:
        return command.description
    target = command.target
    documented = function_of(target) if isinstance(target, type) else target
    docstring = inspect.getdoc(documented) or inspect.getdoc(target) or ""
    return docstring.strip().split("\n", 1)[0]


def _label(command: CommandDescriptor) -> str:
    """Return the name a listing line begins with, aliases in parentheses when any."""
    if command.aliases:
        return f"{command.name} ({', '.join(command.aliases)})"
    return command.name


def _by_name(command: CommandDescriptor) -> str:
    return command.name
