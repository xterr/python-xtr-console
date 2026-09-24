"""Which commands a command line needs parsed, and what is parsed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .command_descriptor import CommandDescriptor

__all__ = ["CommandSelection"]

_HELP_FLAGS: Final = frozenset({"--help", "-h"})


@dataclass(frozen=True, slots=True)
class CommandSelection:
    """The commands to hand the parser, and the tokens to parse.

    - A command line naming a command needs only that command: the parser's
      cost grows with every command it holds, faster than linearly.
    - A command line naming a *namespace* — ``acme user``, or ``acme user
      --help`` — lists the commands in it: they are selected, and the tokens
      become a request for help.
    - Anything else — no command, ``--help``, a name nothing answers to —
      needs them all, for the list or to suggest the nearest name.
    """

    commands: tuple[CommandDescriptor, ...]
    tokens: tuple[str, ...]

    @classmethod
    def of(cls, declared: Sequence[CommandDescriptor], tokens: Sequence[str]) -> CommandSelection:
        """Select from ``declared`` what ``tokens`` needs."""
        if not tokens:
            return cls(tuple(declared), ())
        first, rest = tokens[0], tokens[1:]
        named = tuple(command for command in declared if first in command.names)
        if named:
            return cls(named, tuple(tokens))
        spaced = tuple(command for command in declared if command.namespace == first)
        if spaced and set(rest) <= _HELP_FLAGS:
            return cls(spaced, ("--help",))
        return cls(tuple(declared), tuple(tokens))
