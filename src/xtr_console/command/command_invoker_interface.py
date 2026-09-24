"""The contract for running a command once the command line is parsed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .command_arguments import CommandArguments
    from .command_descriptor import CommandDescriptor
    from .command_signature import CommandSignature

__all__ = ["CommandInvokerInterface"]


@runtime_checkable
class CommandInvokerInterface(Protocol):
    """Builds what a command needs and calls it.

    The seam a dependency-injection container plugs into: the application
    parses the command line, and the invoker decides how the command and its
    remaining parameters come to be.
    """

    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        """Run ``command`` with ``arguments`` and return what it returned."""
        ...
