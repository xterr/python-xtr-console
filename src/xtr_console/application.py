"""A console application: every declared command behind one entry point."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, Literal, TypeAlias, cast, final

from cyclopts import App, Group, Parameter
from cyclopts.exceptions import CycloptsError
from cyclopts.help import DefaultFormatter, PanelSpec, TableSpec
from rich import box
from rich.markup import escape
from rich.text import Text

from .command import CommandSignature, DefaultCommandInvoker, default_registry
from .command.command_descriptor import call_of
from .exit_code import ExitCode
from .style import ConsoleStyle
from .style.console_style import block

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from cyclopts.help.protocols import HelpFormatter
    from rich.padding import Padding

    from .command import (
        CommandArguments,
        CommandDescriptor,
        CommandInvokerInterface,
        CommandsLocatorInterface,
    )

__all__ = ["Application", "Hook"]

Hook: TypeAlias = "Callable[[], Awaitable[None] | None]"
"""Run before or after a command; sync or async."""

_THEME: Final = {
    "cyclopts.border": "yellow",
    "cyclopts.name": "green",
    "cyclopts.default": "yellow",
    "cyclopts.choices": "yellow",
    "cyclopts.env_var": "yellow",
}


@final
class Application:
    """Every declared command, parsed and run on one event loop.

    Commands come from the registry ``@as_command`` fills — import the
    modules declaring them first. The startup hooks, the command and the
    shutdown hooks run on the same loop, so a resource opened on startup is
    usable by the command and closed on shutdown.

    With ``catch_exceptions`` on, an exception escaping a command is rendered
    and the run ends with :attr:`ExitCode.FAILURE`; off, it propagates, as a
    test usually wants.
    """

    __slots__ = (
        "_backend",
        "_catch_exceptions",
        "_commands",
        "_description",
        "_help_formatter",
        "_invoker",
        "_name",
        "_shutdown",
        "_startup",
        "_version",
    )

    def __init__(  # noqa: PLR0913 — settings, all optional, all by keyword but the name.
        self,
        name: str = "console",
        version: str | None = None,
        *,
        description: str | None = None,
        commands: CommandsLocatorInterface | None = None,
        help_formatter: HelpFormatter | None = None,
        catch_exceptions: bool = True,
        backend: Literal["asyncio", "trio"] = "asyncio",
    ) -> None:
        """Configure the application; nothing is parsed or built until it runs."""
        self._name = name
        self._version = version
        self._description = description
        self._commands = commands if commands is not None else default_registry()
        self._help_formatter = help_formatter if help_formatter is not None else _help_formatter()
        self._catch_exceptions = catch_exceptions
        self._backend: Literal["asyncio", "trio"] = backend
        self._invoker: CommandInvokerInterface = DefaultCommandInvoker()
        self._startup: list[Hook] = []
        self._shutdown: list[Hook] = []

    @property
    def commands(self) -> CommandsLocatorInterface:
        """Return the registry the commands are read from."""
        return self._commands

    def on_startup(self, hook: Hook) -> None:
        """Run ``hook`` before the command, on the command's event loop."""
        self._startup.append(hook)

    def on_shutdown(self, hook: Hook) -> None:
        """Run ``hook`` after the command, even if it raised."""
        self._shutdown.append(hook)

    def use_invoker(self, invoker: CommandInvokerInterface) -> None:
        """Have ``invoker`` build and call commands — a container, typically."""
        self._invoker = invoker

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Run the command ``argv`` names on a fresh event loop; return its exit code.

        ``argv`` defaults to ``sys.argv[1:]``. Hand the result to the shell::

            raise SystemExit(application.run())
        """
        app = self._build(ConsoleStyle())
        try:
            code = cast("int", app(argv, exit_on_error=False))
        except CycloptsError:
            return ExitCode.INVALID
        return code

    async def run_async(
        self, argv: Sequence[str] | None = None, *, style: ConsoleStyle | None = None
    ) -> int:
        """Run the command ``argv`` names on the running loop; return its exit code.

        Output goes through ``style``, a fresh :class:`ConsoleStyle` on the
        terminal when omitted.
        """
        app = self._build(style if style is not None else ConsoleStyle())
        try:
            code = cast("int", await app.run_async(argv, exit_on_error=False))
        except CycloptsError:
            return ExitCode.INVALID
        return code

    def _build(self, style: ConsoleStyle) -> App:
        """Build the parser for every command declared so far."""
        header = self._header()
        app = App(
            name=self._name,
            help=self._description,
            help_format="rich",
            help_prologue=header,
            help_formatter=self._help_formatter,
            help_flags=("--help", "-h"),
            version=header if self._version is not None else None,
            version_format="rich",
            version_flags=("--version", "-V") if self._version is not None else (),
            error_formatter=_error_block,
            default_parameter=Parameter(negative=()),
            group_commands=Group("Available commands", sort_key=1, theme=_THEME),
            group_arguments=Group("Arguments", sort_key=1, theme=_THEME),
            group_parameters=Group("Options", sort_key=2, theme=_THEME),
            result_action="return_int_as_exit_code_else_zero",
            backend=self._backend,
            console=style.console,
            error_console=style.error_console,
        )
        options = Group("Options", sort_key=0, theme=_THEME)
        for flag in ("--help", "--version") if self._version is not None else ("--help",):
            app[flag].group = (options,)
        namespaces: dict[str, Group] = {}
        for command in self._commands.commands():
            namespace = command.namespace
            group = (
                namespaces.setdefault(namespace, Group(namespace, sort_key=3, theme=_THEME))
                if namespace is not None
                else app.group_commands
            )
            _ = app.command(
                self._entry_point(command, CommandSignature.of(command), style),
                name=command.name,
                alias=command.aliases,
                group=group,
                show=not command.hidden,
                help=command.description,
            )
        return app

    def _entry_point(
        self, command: CommandDescriptor, signature: CommandSignature, style: ConsoleStyle
    ) -> Callable[..., Awaitable[object]]:
        """Return what the parser calls: the command line in, the command run.

        It presents the parameters the command line fills, and nothing else;
        the style and anything a container supplies are added on the way in.
        What the command returns goes back to the parser, which reads the
        exit code from it.
        """

        async def entry(*args: object, **kwargs: object) -> object:
            bound = signature.command_line.bind(*args, **kwargs)
            return await self._execute(command, signature.arguments(bound, style), signature, style)

        target = command.target
        documented = call_of(target) if isinstance(target, type) else target
        entry.__name__ = command.name
        entry.__doc__ = inspect.getdoc(documented) or inspect.getdoc(target)
        entry.__dict__["__signature__"] = signature.command_line
        return entry

    async def _execute(
        self,
        command: CommandDescriptor,
        arguments: CommandArguments,
        signature: CommandSignature,
        style: ConsoleStyle,
    ) -> object:
        """Run the startup hooks, the command, then the shutdown hooks."""
        for hook in self._startup:
            await _call(hook)
        try:
            result = await self._invoker.invoke(command, signature, arguments)
        except Exception:
            if not self._catch_exceptions:
                raise
            style.error_console.print_exception()
            return ExitCode.FAILURE
        finally:
            for hook in self._shutdown:
                await _call(hook)
        return result

    def _header(self) -> str:
        name = f"[green]{escape(self._name)}[/green]"
        return name if self._version is None else f"{name} [yellow]{escape(self._version)}[/yellow]"


def _help_formatter() -> DefaultFormatter:
    """Lay help out as open sections, without the boxes."""
    return DefaultFormatter(
        panel_spec=PanelSpec(box=box.SIMPLE, padding=(0, 0)),
        table_spec=TableSpec(show_header=False, box=None, padding=(0, 2)),
    )


def _error_block(error: CycloptsError) -> Padding:
    return block("ERROR", Text(str(error)), "white on red")


async def _call(hook: Hook) -> None:
    result = hook()
    if inspect.isawaitable(result):
        await result
