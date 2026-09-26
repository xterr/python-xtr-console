"""Fine-tuning a positional argument."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_console.validator import Validator

__all__ = ["Argument"]


@final
@dataclass(frozen=True, slots=True)
class Argument:
    """Settings for a parameter taken by position — one before a bare ``*``.

    Attributes:
        name: The name shown in the usage line and the help, instead of the parameter's.
        help: The description, instead of the docstring's ``Args:`` entry.
        env_var: A variable read when the argument is left out; the command line wins.
        validator: Called with the converted value; raising ``ValueError`` refuses it,
            and the run ends ``INVALID`` with the error's message.
    """

    name: str | None = None
    help: str | None = None
    env_var: str | None = None
    validator: Validator | None = None
