"""Running a command with no container: functions as they are, classes built bare."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_console.exception import CommandSignatureError, MissingContainerError

from .command_invoker_interface import CommandInvokerInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from .command_arguments import CommandArguments
    from .command_descriptor import CommandDescriptor
    from .command_signature import CommandSignature

__all__ = ["DefaultCommandInvoker"]


@final
class DefaultCommandInvoker(CommandInvokerInterface):
    """Calls a function command directly, and builds a command class bare.

    A class is built only when its command runs, so declaring many costs
    nothing. Sync and async commands both work; a sync one runs on the event
    loop, so it should not block for long.
    """

    __slots__ = ()

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        """Run ``command`` and return what it returned.

        Raises:
            MissingContainerError: If the command, or its class's constructor,
                needs parameters only a container can supply.
        """
        if signature.injected:
            raise MissingContainerError(command.name, signature.injected)
        target = command.target
        call: Callable[..., object] = (
            _built(command, target) if isinstance(target, type) else target
        )
        result = call(*arguments.args, **arguments.kwargs)
        return await result if inspect.isawaitable(result) else result


def _built(command: CommandDescriptor, command_type: type) -> Callable[..., object]:
    """Build ``command_type`` with no arguments.

    Raises:
        MissingContainerError: If its constructor requires any.
    """
    required = tuple(
        parameter.name
        for parameter in inspect.signature(command_type).parameters.values()
        if _is_required(parameter)
    )
    if required:
        raise MissingContainerError(command.name, required)
    built = cast("object", command_type())
    if not callable(built):
        raise CommandSignatureError(command.name, "a command class must define __call__")
    return built


def _is_required(parameter: inspect.Parameter) -> bool:
    default = cast("object", parameter.default)
    variadic = parameter.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    return default is inspect.Parameter.empty and not variadic
