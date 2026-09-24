"""Two commands claim the same name or alias."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["DuplicateCommandError"]


class DuplicateCommandError(ConsoleError):
    """Two commands claim the same name or alias."""

    name: str
    claimed_by: str

    def __init__(self, name: str, claimed_by: str) -> None:
        """Record the contested name and the command already holding it."""
        self.name = name
        self.claimed_by = claimed_by
        super().__init__(f"{name!r} is already claimed by command {claimed_by!r}")
