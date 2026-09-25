"""Async-native console applications: commands declared once, run on one event loop.

A command is a function, or a class whose instances are callable, declared
with :func:`as_command`. An :class:`Application` parses the command line,
supplies a :class:`ConsoleStyle` to any parameter asking for one, and runs
the command — with its dependencies from a container, when one is wired
through :mod:`xtr_console.integration.wireup`.

The core has no dependency-injection container of its own, and imports none.
"""

from importlib.metadata import version

from .application import Application, Hook
from .command import (
    CommandArguments,
    CommandCallable,
    CommandDescriptor,
    CommandInvokerInterface,
    CommandSignature,
    CommandsLocator,
    CommandsLocatorInterface,
    DefaultCommandInvoker,
    default_registry,
)
from .decorator import as_command
from .exception import (
    ApplicationAlreadyWiredError,
    CommandSignatureError,
    ConsoleError,
    DuplicateCommandError,
    EventLoopRunningError,
    InvalidCommandNameError,
    InvalidCommandResultError,
    InvalidDefaultError,
    MissingContainerError,
    UnregisteredCommandError,
)
from .exit_code import ExitCode
from .style import ConsoleStyle
from .tester import ApplicationTester, CommandTester
from .verbosity import SHELL_VERBOSITY, Verbosity

__version__ = version("xtr-console")

__all__ = [
    "SHELL_VERBOSITY",
    "Application",
    "ApplicationAlreadyWiredError",
    "ApplicationTester",
    "CommandArguments",
    "CommandCallable",
    "CommandDescriptor",
    "CommandInvokerInterface",
    "CommandSignature",
    "CommandSignatureError",
    "CommandTester",
    "CommandsLocator",
    "CommandsLocatorInterface",
    "ConsoleError",
    "ConsoleStyle",
    "DefaultCommandInvoker",
    "DuplicateCommandError",
    "EventLoopRunningError",
    "ExitCode",
    "Hook",
    "InvalidCommandNameError",
    "InvalidCommandResultError",
    "InvalidDefaultError",
    "MissingContainerError",
    "UnregisteredCommandError",
    "Verbosity",
    "__version__",
    "as_command",
    "default_registry",
]
