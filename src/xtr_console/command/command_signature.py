"""Which of a command's parameters the command line fills, and which it does not."""

from __future__ import annotations

import inspect
from collections import OrderedDict
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Annotated, cast, get_args, get_origin

from xtr_console.exception import CommandSignatureError
from xtr_console.style import ConsoleStyle

from .command_arguments import CommandArguments
from .command_descriptor import call_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from .command_descriptor import CommandDescriptor

__all__ = ["CommandSignature"]

_Parameter = inspect.Parameter


@dataclass(frozen=True, slots=True)
class CommandSignature:
    """A command's parameters, sorted by who supplies them.

    Three parties fill a command's parameters:

    - the **command line**: everything not claimed by the other two. A
      parameter before a bare ``*`` is an *argument*, taken by position; one
      after it is an *option*, taken as ``--name``.
    - the **console**: a parameter annotated :class:`ConsoleStyle` receives
      the style the application writes through.
    - a **container**: a parameter annotated for injection — wireup's
      ``Injected[T]`` — is left for the container, when one is wired.

    Annotations are evaluated here, against the module declaring the
    command, so ``from __future__ import annotations`` needs no special care.
    """

    callable_signature: inspect.Signature
    """Every parameter, annotations evaluated; ``self`` dropped for a class."""
    command_line: inspect.Signature
    """What the command line parses."""
    call: inspect.Signature
    """What the command is called with, before a container adds its share."""
    styled: tuple[str, ...]
    injected: tuple[str, ...]

    @classmethod
    def of(cls, command: CommandDescriptor) -> CommandSignature:
        """Sort the parameters of ``command``.

        Raises:
            CommandSignatureError: If an annotation cannot be evaluated, or a
                parameter a container fills cannot be passed by keyword.
        """
        parameters = _parameters_of(command)
        by_position = any(p.kind is _Parameter.VAR_POSITIONAL for p in parameters)
        styled = tuple(p.name for p in parameters if _is_style(_annotation_of(p)))
        injected = tuple(p.name for p in parameters if _supplied_by_container(_annotation_of(p)))
        for parameter in parameters:
            if parameter.name in injected and not _by_keyword(parameter, by_position):
                raise CommandSignatureError(
                    command.name,
                    f"container-supplied parameter {parameter.name!r} must be passable by keyword",
                )
        return cls(
            callable_signature=inspect.Signature(parameters),
            command_line=inspect.Signature(
                [_by_position(p) for p in parameters if p.name not in {*styled, *injected}]
            ),
            # With the container's parameters gone from the middle, whatever
            # could go by keyword must: the container adds its own by keyword,
            # and a positional argument after the gap would land in its slot.
            call=inspect.Signature(
                [_as_keyword(p, by_position) for p in parameters if p.name not in injected]
            ),
            styled=styled,
            injected=injected,
        )

    def arguments(self, bound: inspect.BoundArguments, style: ConsoleStyle) -> CommandArguments:
        """Build the call from what the command line bound, adding the style."""
        bound.apply_defaults()
        values: dict[str, object] = {**bound.arguments, **dict.fromkeys(self.styled, style)}
        call = inspect.BoundArguments(
            self.call, OrderedDict((name, values[name]) for name in self.call.parameters)
        )
        return CommandArguments(call.args, call.kwargs)


def _parameters_of(command: CommandDescriptor) -> list[inspect.Parameter]:
    """Return the parameters ``command`` is called with, annotations evaluated.

    Raises:
        CommandSignatureError: If an annotation names something that cannot
            be resolved.
    """
    target = command.target
    call: Callable[..., object] | None = call_of(target) if isinstance(target, type) else target
    if call is None:
        raise CommandSignatureError(command.name, "a command class must define __call__")
    try:
        parameters = list(inspect.signature(call, eval_str=True).parameters.values())
    except NameError as error:
        raise CommandSignatureError(command.name, f"cannot evaluate annotation: {error}") from error
    return parameters[1:] if isinstance(target, type) else parameters


def _by_keyword(parameter: inspect.Parameter, by_position: bool) -> bool:
    """Report whether ``parameter`` can be passed by keyword in this signature."""
    match parameter.kind:
        case _Parameter.KEYWORD_ONLY:
            return True
        case _Parameter.POSITIONAL_OR_KEYWORD:
            return not by_position
        case _Parameter.POSITIONAL_ONLY | _Parameter.VAR_POSITIONAL | _Parameter.VAR_KEYWORD:
            return False


def _by_position(parameter: inspect.Parameter) -> inspect.Parameter:
    """Make an argument positional only: before ``*`` means by position."""
    if parameter.kind is _Parameter.POSITIONAL_OR_KEYWORD:
        return parameter.replace(kind=_Parameter.POSITIONAL_ONLY)
    return parameter


def _as_keyword(parameter: inspect.Parameter, by_position: bool) -> inspect.Parameter:
    if parameter.kind is _Parameter.POSITIONAL_OR_KEYWORD and not by_position:
        return parameter.replace(kind=_Parameter.KEYWORD_ONLY)
    return parameter


def _annotation_of(parameter: inspect.Parameter) -> object:
    return cast("object", parameter.annotation)


def _is_style(annotation: object) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, ConsoleStyle)


def _supplied_by_container(annotation: object) -> bool:
    """Report whether a container fills a parameter annotated ``annotation``.

    Detected rather than required: with no container installed there is
    nothing to recognise, so this cannot change behaviour.
    """
    marker = _container_marker()
    if marker is None or get_origin(annotation) is not Annotated:
        return False
    metadata: tuple[object, ...] = get_args(annotation)[1:]
    return any(isinstance(item, marker) for item in metadata)


@cache
def _container_marker() -> type | None:
    try:
        from wireup.ioc.types import InjectableType  # noqa: PLC0415
    except ImportError:
        return None
    return InjectableType
