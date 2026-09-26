"""Fine-tuning an option."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_console.validator import Validator

__all__ = ["Option"]


@final
@dataclass(frozen=True, slots=True)
class Option:
    """Settings for a parameter taken as ``--name`` — one after a bare ``*``.

    Attributes:
        name: The option's name on the command line (``"--from"`` or ``"from"``), when
            the parameter's own cannot be it.
        alias: Other names it answers to, such as ``"-f"``.
        help: The description, instead of the docstring's ``Args:`` entry.
        env_var: A variable read when the option is left out; the command line wins.
        negative: The name that switches a flag off, such as ``"--no-cache"``. A flag has
            none unless one is given.
        count: On an ``int``: each repetition adds one — ``-ddd`` is ``3``.
        validator: Called with the converted value; raising ``ValueError`` refuses it,
            and the run ends ``INVALID`` with the error's message.
    """

    name: str | None = None
    alias: str | tuple[str, ...] = ()
    help: str | None = None
    env_var: str | None = None
    negative: str | None = None
    count: bool = False
    validator: Validator | None = None

    @property
    def aliases(self) -> tuple[str, ...]:
        """:attr:`alias` as a tuple, however it was given."""
        return (self.alias,) if isinstance(self.alias, str) else self.alias
