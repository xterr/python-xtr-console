"""A declared command: what runs, and what it is called."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, TypeAlias, cast

from xtr_console.exception import CommandSignatureError

__all__ = ["CommandDescriptor", "CommandTarget", "call_of", "default_name_of"]

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
        CommandSignatureError: If ``target`` is a class that defines no
            ``__call__``.
    """

    target: CommandTarget
    name: str
    aliases: tuple[str, ...] = ()
    description: str | None = None
    hidden: bool = False

    def __post_init__(self) -> None:
        """Refuse a class that has nothing to call."""
        if isinstance(self.target, type) and call_of(self.target) is None:
            raise CommandSignatureError(self.name, "a command class must define __call__")

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
