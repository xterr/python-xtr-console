"""A declared command: what runs, and what it is called."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, TypeAlias, cast

from xtr_console.exception import (
    CommandSignatureError,
    DuplicateCommandError,
    InvalidCommandNameError,
)

__all__ = ["CommandDescriptor", "CommandTarget", "call_of", "default_name_of", "function_of"]

CommandTarget: TypeAlias = Callable[..., object] | type
"""A command function, or a class whose instances are the command."""

_NAMESPACE_SEPARATOR: Final = ":"
_WORD_BOUNDARY: Final = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_CLASS_SUFFIX: Final = "Command"


@dataclass(frozen=True, slots=True)
class CommandDescriptor:
    """A declared command.

    ``target`` is what was declared: a function, or a class whose instances
    are callable — built only when its command runs. ``name`` is what the
    command is invoked by; a ``namespace:`` prefix groups it with its
    siblings in the command list. ``description`` replaces the summary the
    docstring would otherwise supply.

    Raises:
        InvalidCommandNameError: If the name or an alias is empty, holds
            whitespace, or starts with ``-``.
        DuplicateCommandError: If the command repeats one of its own names.
        CommandSignatureError: If ``target`` is a class that defines no
            ``__call__``, or is a generator — calling one runs nothing.
    """

    target: CommandTarget
    name: str
    aliases: tuple[str, ...] = ()
    description: str | None = None
    hidden: bool = False

    def __post_init__(self) -> None:
        """Refuse what the command line could not call, or could not type."""
        for name in self.names:
            _check_name(name)
        for position, name in enumerate(self.names):
            if name in self.names[:position]:
                raise DuplicateCommandError(name, self.name)
        called = function_of(self.target)
        if called is None:
            raise CommandSignatureError(self.name, "a command class must define __call__")
        if inspect.isgeneratorfunction(called) or inspect.isasyncgenfunction(called):
            raise CommandSignatureError(self.name, "a command cannot be a generator")

    @property
    def names(self) -> tuple[str, ...]:
        """Return the name, then every alias."""
        return (self.name, *self.aliases)

    @property
    def namespace(self) -> str | None:
        """Return what precedes the first ``:`` in the name, if anything does."""
        namespace, separator, _ = self.name.partition(_NAMESPACE_SEPARATOR)
        return namespace if separator else None


def default_name_of(target: CommandTarget) -> str:
    """Name a command after what declares it.

    A function ``create_user`` becomes ``create-user``; a class
    ``ImportUsersCommand`` becomes ``import-users``.
    """
    name = cast("str", getattr(target, "__name__", type(target).__name__))
    if isinstance(target, type):
        name = name.removesuffix(_CLASS_SUFFIX) or name
        name = _WORD_BOUNDARY.sub("_", name)
    return name.strip("_").lower().replace("_", "-")


def call_of(command_type: type) -> Callable[..., object] | None:
    """Return the ``__call__`` ``command_type`` defines, if any.

    Not ``getattr``: every class inherits ``type.__call__`` from its
    metaclass — the thing that makes ``Thing()`` build one — so asking a class
    for its ``__call__`` always finds something.
    """
    for ancestor in command_type.__mro__[:-1]:
        found: Callable[..., object] | None = ancestor.__dict__.get("__call__")
        if found is not None:
            return found
    return None


def function_of(target: CommandTarget) -> Callable[..., object] | None:
    """Return the function that runs when ``target``'s command runs.

    For a class, its ``__call__`` — unwrapped when it is a ``staticmethod``
    or a ``classmethod``; for a callable object, its type's ``__call__``.
    """
    if not isinstance(target, type):
        return target if inspect.isroutine(target) else call_of(type(target))
    called = call_of(target)
    if isinstance(called, (staticmethod, classmethod)):
        unwrapped: Callable[..., object] = called.__func__
        return unwrapped
    return called


def _check_name(name: str) -> None:
    """Refuse a name nobody could type as a command.

    Raises:
        InvalidCommandNameError: If it is empty, holds whitespace, or
            starts with ``-`` — the command line would read it as an option.
    """
    if not name:
        raise InvalidCommandNameError(name, "it is empty")
    if any(character.isspace() for character in name):
        raise InvalidCommandNameError(name, "it holds whitespace")
    if name.startswith("-"):
        raise InvalidCommandNameError(name, "it starts with '-', like an option")
