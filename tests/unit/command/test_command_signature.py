from __future__ import annotations

import inspect
import typing
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, cast, final

import pytest
from cyclopts import Parameter, validators
from wireup import Injected

from xtr_console import (
    Application,
    ApplicationTester,
    CommandDescriptor,
    CommandSignature,
    CommandSignatureError,
    CommandsLocator,
    ConsoleStyle,
    ExitCode,
    as_command,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@final
class Session:
    """Something a container would supply."""


# Module globals, so evaluating the deferred annotations below finds them.
InjectedSession = Injected[Session]


def signature_of(target: object) -> CommandSignature:
    assert callable(target)
    return CommandSignature.of(CommandDescriptor(target=target, name="test"))


async def mixed(
    email: str, db: InjectedSession, io: ConsoleStyle, count: int = 1, *, admin: bool = False
) -> int:
    del email, db, io, count, admin
    return 0


class ClassCommand:
    def __call__(self, path: str, *, dry_run: bool = False) -> int:
        del path, dry_run
        return 0


def test_the_command_line_sees_neither_the_style_nor_what_a_container_fills() -> None:
    signature = signature_of(mixed)

    assert list(signature.command_line.parameters) == ["email", "count", "admin"]


def test_what_precedes_the_star_is_an_argument_taken_by_position() -> None:
    parameters = signature_of(mixed).command_line.parameters

    assert parameters["email"].kind is inspect.Parameter.POSITIONAL_ONLY
    assert parameters["count"].kind is inspect.Parameter.POSITIONAL_ONLY


def test_what_follows_the_star_is_an_option() -> None:
    parameters = signature_of(mixed).command_line.parameters

    assert parameters["admin"].kind is inspect.Parameter.KEYWORD_ONLY


def test_parameters_are_sorted_by_who_supplies_them() -> None:
    signature = signature_of(mixed)

    assert (signature.styled, signature.injected) == (("io",), ("db",))


def test_deferred_annotations_are_evaluated() -> None:
    signature = signature_of(mixed)

    parameters = signature.command_line.parameters.items()
    annotations = {name: cast("object", p.annotation) for name, p in parameters}

    assert annotations == {"email": str, "count": int, "admin": bool}


def test_a_class_command_is_described_by_its_call_without_self() -> None:
    signature = signature_of(ClassCommand)

    assert list(signature.callable_signature.parameters) == ["path", "dry_run"]


def test_an_annotation_naming_nothing_is_refused() -> None:
    def command(value: str) -> int:
        del value
        return 0

    command.__annotations__ = {"value": "Undefined"}

    with pytest.raises(CommandSignatureError, match="cannot evaluate annotation"):
        _ = signature_of(command)


def test_a_positional_only_container_parameter_is_refused() -> None:
    def command(db: InjectedSession, /) -> int:
        del db
        return 0

    with pytest.raises(CommandSignatureError, match="passable by keyword"):
        _ = signature_of(command)


def test_a_container_parameter_before_star_args_is_refused() -> None:
    def command(db: InjectedSession, *names: str) -> int:
        del db, names
        return 0

    with pytest.raises(CommandSignatureError, match="passable by keyword"):
        _ = signature_of(command)


def test_a_keyword_only_container_parameter_after_star_args_is_accepted() -> None:
    def command(*names: str, db: InjectedSession) -> int:
        del names, db
        return 0

    assert signature_of(command).injected == ("db",)


def test_the_call_goes_by_keyword_so_a_container_parameter_can_sit_between_arguments() -> None:
    signature = signature_of(mixed)
    style = ConsoleStyle()
    bound = signature.command_line.bind("ada@example.com", 3, admin=True)

    arguments = signature.arguments(bound, style)

    assert arguments.args == ()
    assert arguments.kwargs == {"email": "ada@example.com", "io": style, "count": 3, "admin": True}


def test_defaults_are_filled_in_for_what_the_command_line_omitted() -> None:
    signature = signature_of(mixed)

    arguments = signature.arguments(signature.command_line.bind("ada@example.com"), ConsoleStyle())

    assert (arguments.kwargs["count"], arguments.kwargs["admin"]) == (1, False)


def test_star_args_keep_the_arguments_before_them_positional() -> None:
    def command(first: str, *rest: str, io: ConsoleStyle) -> int:
        del first, rest, io
        return 0

    signature = signature_of(command)
    style = ConsoleStyle()

    arguments = signature.arguments(signature.command_line.bind("a", "b", "c"), style)

    assert arguments.args == ("a", "b", "c")
    assert arguments.kwargs == {"io": style}


def test_a_static_call_keeps_its_first_parameter() -> None:
    @final
    class Static:
        @staticmethod
        def __call__(path: str, *, force: bool = False) -> int:
            del path, force
            return 0

    assert list(signature_of(Static).callable_signature.parameters) == ["path", "force"]


def test_a_class_call_drops_the_class() -> None:
    @final
    class ClassBound:
        @classmethod
        def __call__(cls, path: str) -> int:
            del cls, path
            return 0

    assert list(signature_of(ClassBound).callable_signature.parameters) == ["path"]


def test_an_optional_style_is_still_the_style() -> None:
    def command(name: str, io: ConsoleStyle | None = None) -> int:
        del name, io
        return 0

    signature = signature_of(command)

    assert (signature.styled, list(signature.command_line.parameters)) == (("io",), ["name"])


def test_a_typing_optional_style_is_still_the_style() -> None:
    def command(io: object = None) -> int:
        del io
        return 0

    # Optional[...] has its own origin before Python 3.14; spelled as a string
    # so the deprecated name is evaluated, not imported.
    command.__annotations__ = {"io": "typing.Optional[ConsoleStyle]", "return": "int"}
    signature = signature_of(command)

    annotation = cast("object", signature.callable_signature.parameters["io"].annotation)
    assert typing.get_origin(annotation) is not None
    assert signature.styled == ("io",)


def test_an_optional_container_parameter_is_still_the_containers() -> None:
    def command(name: str, db: InjectedSession | None = None) -> int:
        del name, db
        return 0

    signature = signature_of(command)

    assert (signature.injected, list(signature.command_line.parameters)) == (("db",), ["name"])


# ─── on the command line ─────────────────────────────────────────
#
# Every kind of argument and option, parsed by a real application: what each
# command receives is recorded, and the tests assert on the values.

PARSED = CommandsLocator()
received: dict[str, object] = {}


class Color(Enum):
    RED = "red"
    GREEN = "green"


@as_command("args", registry=PARSED)
def arguments_command(source: Path, target: Path | None = None, *, count: int = 1) -> int:
    received.update(source=source, target=target, count=count)
    return 0


@as_command("variadic", registry=PARSED)
def variadic_command(*files: Path) -> int:
    received.update(files=files)
    return 0


@as_command("options", registry=PARSED)
def options_command(  # noqa: PLR0913 — one of every kind of option, on purpose.
    *,
    name: str,
    ratio: float = 0.5,
    when: datetime | None = None,
    depth: Annotated[int, Parameter(alias="-d", count=True)] = 0,
    force: Annotated[bool, Parameter(alias="-f")] = False,
    cache: Annotated[bool, Parameter(negative="--no-cache")] = True,
    tags: list[str] | None = None,
    level: Literal["debug", "info"] = "info",
    color: Color = Color.RED,
    since: Annotated[str, Parameter(name="--from")] = "now",
    region: Annotated[str, Parameter(env_var="ACME_REGION")] = "",
    retries: Annotated[int, Parameter(validator=validators.Number(gte=1, lte=5))] = 3,
    note: Annotated[str, Parameter(help="A note, from Parameter.")] = "",
) -> int:
    received.update(
        name=name,
        ratio=ratio,
        when=when,
        depth=depth,
        force=force,
        cache=cache,
        tags=tags,
        level=level,
        color=color,
        since=since,
        region=region,
        retries=retries,
        note=note,
    )
    return 0


@as_command("class", registry=PARSED)
@final
class ClassOptionsCommand:
    def __call__(self, path: Path, *, size: Annotated[int, Parameter(alias="-s")] = 2) -> int:
        received.update(path=path, size=size)
        return 0


@pytest.fixture
def parser() -> ApplicationTester:
    received.clear()
    return ApplicationTester(Application("acme", commands=PARSED, catch_exceptions=False))


async def parse(parser: ApplicationTester, *argv: str) -> int:
    return await parser.execute(argv)


@pytest.mark.anyio
async def test_a_required_argument_is_taken_by_position(parser: ApplicationTester) -> None:
    _ = await parse(parser, "args", "a.txt")

    assert received == {"source": Path("a.txt"), "target": None, "count": 1}


@pytest.mark.anyio
async def test_an_optional_argument_follows_the_required_ones(parser: ApplicationTester) -> None:
    _ = await parse(parser, "args", "a.txt", "b.txt", "--count", "3")

    assert received == {"source": Path("a.txt"), "target": Path("b.txt"), "count": 3}


@pytest.mark.anyio
async def test_a_missing_argument_is_invalid(parser: ApplicationTester) -> None:
    assert await parse(parser, "args") == ExitCode.INVALID
    assert "SOURCE requires an argument" in parser.error_display


@pytest.mark.anyio
async def test_an_argument_is_not_an_option(parser: ApplicationTester) -> None:
    assert await parse(parser, "args", "--source", "a.txt") == ExitCode.INVALID


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("argv", "files"),
    [(("a", "b", "c"), (Path("a"), Path("b"), Path("c"))), ((), ())],
)
async def test_star_args_collect_every_remaining_argument(
    parser: ApplicationTester, argv: tuple[str, ...], files: tuple[Path, ...]
) -> None:
    _ = await parse(parser, "variadic", *argv)

    assert received == {"files": files}


@pytest.mark.anyio
async def test_an_option_without_a_default_is_required(parser: ApplicationTester) -> None:
    assert await parse(parser, "options") == ExitCode.INVALID
    assert "--name requires an argument" in parser.error_display


@pytest.mark.anyio
async def test_options_left_out_take_their_defaults(parser: ApplicationTester) -> None:
    _ = await parse(parser, "options", "--name", "x")

    assert received == {
        "name": "x",
        "ratio": 0.5,
        "when": None,
        "depth": 0,
        "force": False,
        "cache": True,
        "tags": None,
        "level": "info",
        "color": Color.RED,
        "since": "now",
        "region": "",
        "retries": 3,
        "note": "",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("argv", "field", "value"),
    [
        (("--ratio", "1.5"), "ratio", 1.5),
        (("--ratio=2.5",), "ratio", 2.5),
        (("--when", "2026-01-02T03:04:05"), "when", datetime(2026, 1, 2, 3, 4, 5)),  # noqa: DTZ001
        (("-ddd",), "depth", 3),
        (("--depth", "--depth"), "depth", 2),
        (("--force",), "force", True),
        (("-f",), "force", True),
        (("--no-cache",), "cache", False),
        (("--tags", "a", "--tags", "b"), "tags", ["a", "b"]),
        (("--level", "debug"), "level", "debug"),
        (("--color", "green"), "color", Color.GREEN),
        (("--from", "yesterday"), "since", "yesterday"),
        (("--retries", "5"), "retries", 5),
    ],
)
async def test_each_kind_of_option_is_converted(
    parser: ApplicationTester, argv: tuple[str, ...], field: str, value: object
) -> None:
    _ = await parse(parser, "options", "--name", "x", *argv)

    assert received[field] == value


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("argv", "complaint"),
    [
        (("--level", "trace"), 'Choose from: "debug", "info"'),
        (("--retries", "9"), "Must be <= 5"),
        (("--ratio", "abc"), 'unable to convert "abc" into float'),
        (("--since", "x"), "Unknown option"),
    ],
)
async def test_a_value_the_option_refuses_is_invalid(
    parser: ApplicationTester, argv: tuple[str, ...], complaint: str
) -> None:
    assert await parse(parser, "options", "--name", "x", *argv) == ExitCode.INVALID
    assert complaint in parser.error_display


@pytest.mark.anyio
async def test_an_environment_variable_fills_an_option_left_out(
    parser: ApplicationTester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ACME_REGION", "from-env")

    _ = await parse(parser, "options", "--name", "x")

    assert received["region"] == "from-env"


@pytest.mark.anyio
async def test_the_command_line_beats_the_environment(
    parser: ApplicationTester, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ACME_REGION", "from-env")

    _ = await parse(parser, "options", "--name", "x", "--region", "given")

    assert received["region"] == "given"


@pytest.mark.anyio
async def test_a_class_command_takes_arguments_and_options_on_call(
    parser: ApplicationTester,
) -> None:
    _ = await parse(parser, "class", "users.csv", "-s", "7")

    assert received == {"path": Path("users.csv"), "size": 7}


@pytest.mark.anyio
async def test_help_lists_the_arguments_apart_from_the_options(parser: ApplicationTester) -> None:
    _ = await parse(parser, "args", "--help")

    help_body = parser.display.partition("Arguments")[2]
    arguments, _, options = help_body.partition("Options")
    assert ("SOURCE" in arguments, "TARGET" in arguments, "--count" in options) == (
        True,
        True,
        True,
    )
    assert "--count" not in arguments


@pytest.mark.anyio
@pytest.mark.parametrize(
    "shown",
    [
        "--name STR",
        "[required]",
        "--from STR",
        "[choices: debug, info]",
        "[choices: red, green]",
        "[env var: ACME_REGION]",
        "[default: 0.5]",
        "--cache --no-cache",
        "A note, from Parameter.",
    ],
)
async def test_help_describes_every_option(parser: ApplicationTester, shown: str) -> None:
    _ = await parse(parser, "options", "--help")

    assert shown in parser.display


# ─── what a command returns ──────────────────────────────────────


@pytest.mark.parametrize("returned", ["", "-> None", "-> str", "-> bool", "-> int | None"])
def test_a_command_not_annotated_to_return_an_int_is_refused(returned: str) -> None:
    namespace: dict[str, object] = {}
    exec(f"def command(){returned}:\n    return 0", namespace)  # noqa: S102 — each annotation under test.

    with pytest.raises(CommandSignatureError, match="must be annotated to return an int"):
        _ = signature_of(namespace["command"])


def test_a_command_annotated_to_return_an_exit_code_is_accepted() -> None:
    async def command() -> ExitCode:
        return ExitCode.SUCCESS

    assert signature_of(command).injected == ()


def test_a_class_whose_call_returns_nothing_is_refused() -> None:
    @final
    class Command:
        def __call__(self) -> None: ...

    with pytest.raises(CommandSignatureError, match="must be annotated to return an int"):
        _ = signature_of(Command)


# ─── --help ──────────────────────────────────────────────────────


def test_a_parameter_named_help_is_refused() -> None:
    def command(*, help: str = "") -> int:  # noqa: A002 — the name under test.
        del help
        return 0

    with pytest.raises(CommandSignatureError, match="would take --help over"):
        _ = signature_of(command)


def test_a_parameter_named_help_but_renamed_is_accepted() -> None:
    def command(*, help: Annotated[str, Parameter(name="--topic")] = "") -> int:  # noqa: A002
        del help
        return 0

    assert list(signature_of(command).command_line.parameters) == ["help"]


# ─── global options ──────────────────────────────────────────────


def quiet_by_name(*, quiet: bool = False) -> int:
    del quiet
    return 0


def verbose_by_alias(*, depth: Annotated[int, Parameter(alias="-v", count=True)] = 0) -> int:
    del depth
    return 0


def silent_by_rename(*, mute: Annotated[bool, Parameter(name="silent")] = False) -> int:
    del mute
    return 0


def ansi_by_negative(*, color: Annotated[bool, Parameter(negative="--no-ansi")] = True) -> int:
    del color
    return 0


@pytest.mark.parametrize(
    ("command", "flag"),
    [
        (quiet_by_name, "--quiet"),
        (verbose_by_alias, "-v"),
        (silent_by_rename, "--silent"),
        (ansi_by_negative, "--no-ansi"),
    ],
)
def test_an_option_claiming_a_global_option_is_refused(
    command: Callable[..., int], flag: str
) -> None:
    with pytest.raises(CommandSignatureError, match=f"global option {flag} over"):
        _ = signature_of(command)


def test_an_argument_may_share_a_global_options_name() -> None:
    def command(quiet: str) -> int:
        del quiet
        return 0

    assert list(signature_of(command).command_line.parameters) == ["quiet"]
