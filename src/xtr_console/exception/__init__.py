"""Every error this library raises.

All of them derive from :class:`ConsoleError`, so one ``except`` catches
anything the console can go wrong with, and a narrower one handles a single
cause. Each carries the data a caller needs as typed attributes rather than
forcing a message to be parsed.
"""

from .command_signature_error import CommandSignatureError
from .console_error import ConsoleError
from .duplicate_command_error import DuplicateCommandError
from .event_loop_running_error import EventLoopRunningError
from .invalid_command_name_error import InvalidCommandNameError
from .invalid_command_result_error import InvalidCommandResultError
from .invalid_default_error import InvalidDefaultError
from .missing_container_error import MissingContainerError

__all__ = [
    "CommandSignatureError",
    "ConsoleError",
    "DuplicateCommandError",
    "EventLoopRunningError",
    "InvalidCommandNameError",
    "InvalidCommandResultError",
    "InvalidDefaultError",
    "MissingContainerError",
]
