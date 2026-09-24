"""The registry command declarations accumulate in."""

from __future__ import annotations

from .commands_locator import CommandsLocator

__all__ = ["default_registry"]

_DEFAULT_REGISTRY = CommandsLocator()


def default_registry() -> CommandsLocator:
    """Return the registry ``@as_command`` fills when given no other.

    Import-time declaration needs somewhere to accumulate; this is it. Pass
    an explicit registry when you want isolation, as tests generally should.
    """
    return _DEFAULT_REGISTRY
