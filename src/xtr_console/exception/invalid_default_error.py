"""A question's default is not one of the answers it accepts."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["InvalidDefaultError"]


class InvalidDefaultError(ConsoleError):
    """A question's default is not one of the answers it accepts."""

    question: str
    default: str
    choices: tuple[str, ...]

    def __init__(self, question: str, default: str, choices: tuple[str, ...]) -> None:
        """Record the question, its default and the answers it accepts."""
        self.question = question
        self.default = default
        self.choices = choices
        accepted = ", ".join(choices)
        super().__init__(f"{question!r} defaults to {default!r}, which is not one of: {accepted}")
