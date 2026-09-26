"""Reader for :func:`~xtr_console.as_command` metadata, for a bundle's autoconfigure."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .command_descriptor import CommandDescriptor

__all__ = ["COMMANDS_ATTRIBUTE", "commands_declared_on"]

COMMANDS_ATTRIBUTE = "__xtr_console_commands__"
"""Where :func:`~xtr_console.as_command` records per-target descriptors."""


def commands_declared_on(obj: object) -> Iterable[CommandDescriptor]:
    """Yield every :func:`~xtr_console.as_command` descriptor stashed on ``obj``.

    A reader for
    :meth:`~xtr_dependency_injection.ContainerBuilder.register_attribute_for_autoconfiguration`:
    the console bundle uses it so a scanned function or class decorated with
    :func:`~xtr_console.as_command` registers into the kernel's per-instance
    :class:`~xtr_console.CommandsLocator`, and — for classes — becomes a
    container-built service.
    """
    from .command_descriptor import CommandDescriptor  # noqa: PLC0415

    declarations: object = getattr(obj, COMMANDS_ATTRIBUTE, ())
    if not isinstance(declarations, tuple):
        return ()
    typed = cast("tuple[object, ...]", declarations)
    return tuple(entry for entry in typed if isinstance(entry, CommandDescriptor))
