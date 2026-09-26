"""Async-native console applications: commands declared once, run on one event loop.

A command is a function, or a class whose instances are callable, declared
with :func:`as_command`. An :class:`Application` parses the command line,
supplies a :class:`ConsoleStyle` to any parameter asking for one, and runs
the command — with its dependencies from a container, when one is wired
through :mod:`xtr_console.bundle`.

The core has no dependency-injection container of its own, and imports none.
"""

from importlib.metadata import version

from .application import Application, Hook
from .attribute import Argument, Option
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
    CommandSignatureError,
    ConsoleError,
    DuplicateCommandError,
    EventLoopRunningError,
    InvalidCommandNameError,
    InvalidCommandResultError,
    InvalidDefaultError,
    MissingContainerError,
)
from .exit_code import ExitCode
from .style import ConsoleStyle, escape
from .tester import ApplicationTester, CommandTester
from .validator import Range, Validator
from .verbosity import SHELL_VERBOSITY, Verbosity

__version__ = version("xtr-console")

__all__ = [
    "SHELL_VERBOSITY",
    "Application",
    "ApplicationTester",
    "Argument",
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
    "Option",
    "Range",
    "Validator",
    "Verbosity",
    "__version__",
    "as_command",
    "default_registry",
    "escape",
]
