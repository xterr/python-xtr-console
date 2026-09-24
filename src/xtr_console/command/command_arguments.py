"""What a command is called with."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["CommandArguments"]


@dataclass(frozen=True, slots=True)
class CommandArguments:
    """The positional and keyword arguments a command is called with.

    Everything the command line and the console supply. Parameters a
    container fills are not here; the container adds them itself.
    """

    args: tuple[object, ...] = ()
    kwargs: Mapping[str, object] = field(default_factory=dict[str, object])
