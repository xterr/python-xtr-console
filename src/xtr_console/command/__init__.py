"""Declaring commands, and turning a parsed command line into a call."""

from .command_arguments import CommandArguments
from .command_callable import CommandCallable
from .command_descriptor import CommandDescriptor, CommandTarget, default_name_of
from .command_invoker_interface import CommandInvokerInterface
from .command_selection import CommandSelection
from .command_signature import CommandSignature
from .commands_locator import CommandsLocator
from .commands_locator_interface import CommandsLocatorInterface
from .default_command_invoker import DefaultCommandInvoker
from .default_registry import default_registry

__all__ = [
    "CommandArguments",
    "CommandCallable",
    "CommandDescriptor",
    "CommandInvokerInterface",
    "CommandSelection",
    "CommandSignature",
    "CommandTarget",
    "CommandsLocator",
    "CommandsLocatorInterface",
    "DefaultCommandInvoker",
    "default_name_of",
    "default_registry",
]
