"""Which of a command's parameters the command line fills, and which it does not."""

from __future__ import annotations

import inspect
from collections import OrderedDict
from dataclasses import dataclass
from functools import cache
from types import UnionType
from typing import TYPE_CHECKING, Annotated, cast, get_args, get_origin

from cyclopts import Parameter

from xtr_console.exception import CommandSignatureError
from xtr_console.global_options import GLOBAL_FLAGS
from xtr_console.style import ConsoleStyle

from .command_arguments import CommandArguments
from .command_descriptor import call_of, function_of

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
    - a **container**: a parameter annotated for injection —
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
            CommandSignatureError: If an annotation cannot be evaluated, the
                command is not annotated to return an ``int``, a parameter
                would take ``--help`` over, or a parameter a container fills
                cannot be passed by keyword.
        """
        parameters, returned = _signature_of(command)
        if not _is_exit_code(returned):
            shown = "nothing" if returned is inspect.Signature.empty else repr(returned)
            reason = f"it must be annotated to return an int or an ExitCode, not {shown}"
            raise CommandSignatureError(command.name, reason)
        by_position = any(p.kind is _Parameter.VAR_POSITIONAL for p in parameters)
        styled = tuple(p.name for p in parameters if _is_style(_annotation_of(p)))
        injected = tuple(p.name for p in parameters if _supplied_by_container(_annotation_of(p)))
        for parameter in parameters:
            if parameter.name in injected and not _by_keyword(parameter, by_position):
                raise CommandSignatureError(
                    command.name,
                    f"container-supplied parameter {parameter.name!r} must be passable by keyword",
                )
            if parameter.name in {*styled, *injected}:
                continue
            if _takes_help_over(parameter):
                reason = (
                    "parameter 'help' would take --help over; rename it with Parameter(name=...)"
                )
                raise CommandSignatureError(command.name, reason)
            claimed = sorted(GLOBAL_FLAGS.intersection(_option_names(parameter)))
            if claimed:
                reason = (
                    f"parameter {parameter.name!r} would take the global option {claimed[0]} "
                    "over; rename it with Parameter(name=..., alias=...)"
                )
                raise CommandSignatureError(command.name, reason)
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


def _signature_of(command: CommandDescriptor) -> tuple[list[inspect.Parameter], object]:
    """Return the parameters ``command`` is called with, and what it returns.

    Annotations are evaluated.

    Raises:
        CommandSignatureError: If an annotation names something that cannot
            be resolved.
    """
    target = command.target
    call: Callable[..., object] | None = function_of(target) if isinstance(target, type) else target
    if call is None:
        raise CommandSignatureError(command.name, "a command class must define __call__")
    try:
        signature = inspect.signature(call, eval_str=True)
    except NameError as error:
        raise CommandSignatureError(command.name, f"cannot evaluate annotation: {error}") from error
    parameters = list(signature.parameters.values())
    returned = cast("object", signature.return_annotation)
    # A class's __call__ is bound to the instance — or to the class, as a
    # classmethod — unless it is a staticmethod, which has nothing to drop.
    bound = isinstance(target, type) and not isinstance(call_of(target), staticmethod)
    return (parameters[1:] if bound else parameters), returned


def _is_exit_code(annotation: object) -> bool:
    """Report whether ``annotation`` promises an exit code: an ``int``, not a ``bool``."""
    return isinstance(annotation, type) and issubclass(annotation, int) and annotation is not bool


def _takes_help_over(parameter: inspect.Parameter) -> bool:
    """Report whether ``parameter`` would become ``--help``, unless renamed."""
    if parameter.name != "help":
        return False
    return not any(settings.name for settings in _settings_of(parameter))


def _option_names(parameter: inspect.Parameter) -> set[str]:
    """Return every flag an option parameter answers to; none for an argument.

    Its name — ``--dry-run`` for ``dry_run`` unless ``Parameter(name=...)``
    says otherwise — its aliases and any negative form.
    """
    if parameter.kind is not _Parameter.KEYWORD_ONLY:
        return set()
    # cyclopts turns each of these into a tuple of strings, or None.
    settings = _settings_of(parameter)
    names = [name for entry in settings for name in entry.name or ()]
    if not names:
        names = [parameter.name.lower().replace("_", "-")]
    names.extend(alias for entry in settings for alias in entry.alias or ())
    names.extend(negative for entry in settings for negative in entry.negative or ())
    return {name if name.startswith("-") else f"--{name}" for name in names}


def _settings_of(parameter: inspect.Parameter) -> tuple[Parameter, ...]:
    """Return the cyclopts ``Parameter`` settings ``Annotated`` attaches to ``parameter``."""
    annotation = _annotation_of(parameter)
    metadata: tuple[object, ...] = (
        get_args(annotation)[1:] if get_origin(annotation) is Annotated else ()
    )
    return tuple(item for item in metadata if isinstance(item, Parameter))


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


def _members_of(annotation: object) -> tuple[object, ...]:
    """Return what ``annotation`` may be: its members if a union, else itself.

    ``X | None`` has the origin ``UnionType``; ``Optional[X]`` has
    ``typing.Union`` until Python 3.14 makes them one — compared by name, as
    naming it is deprecated.
    """
    origin = get_origin(annotation)
    if origin is UnionType or str(origin) == "typing.Union":
        members: tuple[object, ...] = get_args(annotation)
        return members
    return (annotation,)


def _is_style(annotation: object) -> bool:
    """Report whether ``annotation`` asks for the style, ``X | None`` included."""
    return any(
        isinstance(member, type) and issubclass(member, ConsoleStyle)
        for member in _members_of(annotation)
    )


def _supplied_by_container(annotation: object) -> bool:
    """Report whether a container fills a parameter annotated ``annotation``.

    Detected rather than required: with no container installed there is
    nothing to recognise, so this cannot change behaviour.
    """
    marker = _container_marker()
    if marker is None:
        return False
    return any(
        isinstance(item, marker)
        for member in _members_of(annotation)
        if get_origin(member) is Annotated
        for item in cast("tuple[object, ...]", get_args(member)[1:])
    )


@cache
def _container_marker() -> type | None:
    try:
        from xtr_dependency_injection import Autowire  # noqa: PLC0415
    except ImportError:
        return None
    return Autowire
