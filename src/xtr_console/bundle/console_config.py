"""Configuration for :class:`~xtr_console.bundle.ConsoleBundle`."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ConsoleConfig"]


@dataclass(frozen=True, slots=True)
class ConsoleConfig:
    """Values the :class:`Application` factory reads from the container.

    Attributes:
        name: The application's name. When ``None``, ``kernel.name`` is used.
        version: The version displayed in the help header and by
            ``--version``. ``None`` disables that option.
        description: One-line description shown in the help header.
        catch_exceptions: Report an exception escaping a command and exit
            :attr:`~xtr_console.ExitCode.FAILURE` instead of propagating.
    """

    name: str | None = None
    version: str | None = None
    description: str | None = None
    catch_exceptions: bool = True
