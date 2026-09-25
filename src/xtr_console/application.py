"""A console application: every declared command behind one entry point."""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Final, Literal, TypeAlias, cast, final

from cyclopts import App, Group, Parameter
from cyclopts.exceptions import CycloptsError
from cyclopts.help import DefaultFormatter, PanelSpec, TableSpec
from rich import box
from rich.markup import escape
from rich.text import Text

from .command import CommandSelection, CommandSignature, DefaultCommandInvoker, default_registry
from .command.command_descriptor import function_of
from .exception import EventLoopRunningError, InvalidCommandResultError
from .exit_code import ExitCode
from .global_options import GlobalOptions, list_global_options
from .style import ConsoleStyle
from .style.console_style import block
from .style.exception_renderer import render_exception
from .verbosity import SHELL_VERBOSITY, Verbosity

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

    Every command takes the global options — ``-v``/``-vv``/``-vvv``, ``-q``,
    ``--silent``, ``-n``, ``--ansi``/``--no-ansi`` — anywhere on its command
    line; they set the :class:`ConsoleStyle` it writes through.

    With ``catch_exceptions`` on, an exception escaping a command is reported
    — its message, or with ``-v`` its traceback — and the run ends with
    :attr:`ExitCode.FAILURE`; off, it propagates, as a test usually wants.
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
    def name(self) -> str:
        """Return the name the application is invoked by."""
        return self._name

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

    @property
    def invoker(self) -> CommandInvokerInterface:
        """Return what builds and calls the commands."""
        return self._invoker

    def use_invoker(self, invoker: CommandInvokerInterface) -> None:
        """Have ``invoker`` build and call commands — a container, typically."""
        self._invoker = invoker

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Run the command ``argv`` names on a fresh event loop; return its exit code.

        ``argv`` defaults to ``sys.argv[1:]``. Hand the result to the shell::

            raise SystemExit(application.run())

        The verbosity starts from ``SHELL_VERBOSITY``, and what the run settles
        on is written back to it, for the processes the command starts.

        Raises:
            EventLoopRunningError: If called from async code; await
                :meth:`run_async` there.
        """
        if _loop_running():
            raise EventLoopRunningError
        style = _terminal_style()
        selection = self._configure(argv, style)
        os.environ[SHELL_VERBOSITY] = str(style.verbosity.shell_level)
        app = self._build(style, selection.commands)
        try:
            code = cast("int", app(selection.tokens, exit_on_error=False))
        except CycloptsError:
            return ExitCode.INVALID
        except SystemExit as stop:
            return _exit_code_of(stop, style)
        return code

    async def run_async(
        self, argv: Sequence[str] | None = None, *, style: ConsoleStyle | None = None
    ) -> int:
        """Run the command ``argv`` names on the running loop; return its exit code.

        Output goes through ``style``, a fresh :class:`ConsoleStyle` on the
        terminal when omitted — its verbosity read from ``SHELL_VERBOSITY``. A
        style given keeps its own until a global option changes it. A command
        that exits — ``sys.exit(3)``, or Ctrl-C, which exits ``130`` — ends the
        run with that code rather than leaving the process.
        """
        style = style if style is not None else _terminal_style()
        selection = self._configure(argv, style)
        app = self._build(style, selection.commands)
        try:
            code = cast("int", await app.run_async(selection.tokens, exit_on_error=False))
        except CycloptsError:
            return ExitCode.INVALID
        except SystemExit as stop:
            return _exit_code_of(stop, style)
        return code

    def _configure(self, argv: Sequence[str] | None, style: ConsoleStyle) -> CommandSelection:
        """Apply the global options in ``argv`` to ``style``; select from what is left."""
        options = GlobalOptions.parse(list(argv) if argv is not None else sys.argv[1:])
        options.apply(style)
        return CommandSelection.of(self._commands.commands(), options.remaining)

    def _build(self, style: ConsoleStyle, commands: Sequence[CommandDescriptor]) -> App:
        """Build the parser for ``commands``."""
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
        list_global_options(app, options)
        namespaces: dict[str, Group] = {}
        for command in commands:
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
        documented = function_of(target) if isinstance(target, type) else target
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
        """Run the startup hooks, the command, then the shutdown hooks.

        Every shutdown hook runs, in the order added, once startup has begun —
        whether a startup hook, the command or another shutdown hook raised.
        Whatever raised is one failure, each error chained to the one before.
        """
        try:
            async with AsyncExitStack() as shutdown:
                for hook in reversed(self._shutdown):
                    _ = shutdown.push_async_callback(_call, hook)
                for hook in self._startup:
                    await _call(hook)
                return _exit_code(
                    command, await self._invoker.invoke(command, signature, arguments)
                )
        except Exception as error:
            if not self._catch_exceptions:
                raise
            render_exception(error, style)
            return ExitCode.FAILURE

    def _header(self) -> str:
        name = f"[green]{escape(self._name)}[/green]"
        return name if self._version is None else f"{name} [yellow]{escape(self._version)}[/yellow]"


def _terminal_style() -> ConsoleStyle:
    """Return a style on the terminal, as verbose as ``SHELL_VERBOSITY`` says."""
    return ConsoleStyle(verbosity=Verbosity.from_shell(os.environ.get(SHELL_VERBOSITY)))


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


def _exit_code(command: CommandDescriptor, result: object) -> int:
    """Return ``result`` as the exit code it must be.

    Raises:
        InvalidCommandResultError: If it is not an ``int`` — or is a ``bool``.
    """
    if not isinstance(result, int) or isinstance(result, bool):
        raise InvalidCommandResultError(command.name, type(result).__qualname__)
    return result


def _loop_running() -> bool:
    try:
        _ = asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _exit_code_of(stop: SystemExit, style: ConsoleStyle) -> int:
    """Read the exit code the way Python does when a process exits.

    ``None`` is success and an ``int`` is the code; anything else is a
    message, printed to standard error, and a failure.
    """
    match stop.code:
        case None:
            return ExitCode.SUCCESS
        case int():
            return stop.code
        case message:
            style.error_console.print(str(message), markup=False, highlight=False)
            return ExitCode.FAILURE
