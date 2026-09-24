"""Async-native console applications: commands declared once, run on one event loop.

A command is a function, or a class whose instances are callable, declared
with :func:`as_command`. An :class:`Application` parses the command line,
supplies a :class:`ConsoleStyle` to any parameter asking for one, and runs
the command — with its dependencies from a container, when one is wired
through :mod:`xtr_console.integration.wireup`.

The core has no dependency-injection container of its own, and imports none.
"""

from .application import Application, Hook
from .command import (
    CommandArguments,
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
    CommandSignatureError,
    ConsoleError,
    DuplicateCommandError,
    MissingContainerError,
    UnregisteredCommandError,
)
from .exit_code import ExitCode
from .style import ConsoleStyle
from .tester import ApplicationTester, CommandTester

__version__ = "0.1.0"

__all__ = [
    "Application",
    "ApplicationTester",
    "CommandArguments",
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
    "ExitCode",
    "Hook",
    "MissingContainerError",
    "UnregisteredCommandError",
    "__version__",
    "as_command",
    "default_registry",
]
