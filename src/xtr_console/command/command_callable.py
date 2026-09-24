"""What a command class's instances must be: callable, returning an exit code."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable

__all__ = ["CommandCallable"]


class CommandCallable(Protocol):
    """An object whose call returns an exit code, now or once awaited.

    ``*args: Any, **kwargs: Any`` is how a type checker spells "any
    signature": a ``__call__`` taking any parameters matches, and only the
    return type is held to ``int``.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> int | Awaitable[int]:
        """Run the command and return its exit code."""
        ...
