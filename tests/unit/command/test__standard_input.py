"""A bare ``-`` reaches a command as a value: standard input, by the usual convention.

Regression: the parser read a bare ``-`` as an unknown option, so a command documenting ``-``
for standard input could never be given it. Every case drives a real application; a command
line without a bare ``-``, and a ``-`` the command cannot take, are parsed as they always were.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest

from xtr_console import (
    Application,
    ApplicationTester,
    Argument,
    CommandsLocator,
    ConsoleStyle,
    ExitCode,
    Option,
    as_command,
)

pytestmark = pytest.mark.anyio

SEEN: list[object] = []
JUDGED: list[str] = []


@pytest.fixture(autouse=True)
def _forget() -> None:
    SEEN.clear()
    JUDGED.clear()


@pytest.fixture
def registry() -> CommandsLocator:
    registry = CommandsLocator()

    @as_command("read", registry=registry)
    def read(
        io: ConsoleStyle, source: str, target: str | None = None, *, upper: bool = False
    ) -> int:
        del io
        SEEN.extend([source, target, upper])
        return 0

    @as_command("open", registry=registry)
    def open_(io: ConsoleStyle, path: Path) -> int:
        del io
        SEEN.append(path)
        return 0

    @as_command("cat", registry=registry)
    def cat(io: ConsoleStyle, *sources: str) -> int:
        del io
        SEEN.append(sources)
        return 0

    @as_command("write", registry=registry)
    def write(io: ConsoleStyle, *, output: str = "out.txt") -> int:
        del io
        SEEN.append(output)
        return 0

    @as_command("checked", registry=registry)
    def checked(io: ConsoleStyle, source: Annotated[str, Argument(validator=_not_stdin)]) -> int:
        del io
        SEEN.append(source)
        return 0

    @as_command("judged", registry=registry)
    def judged(io: ConsoleStyle, source: Annotated[str, Argument(validator=_judge)]) -> int:
        del io
        SEEN.append(source)
        return 0

    @as_command("count", registry=registry)
    def count(io: ConsoleStyle, times: int) -> int:
        del io
        SEEN.append(times)
        return 0

    @as_command("nothing", registry=registry)
    def nothing(io: ConsoleStyle, *, loud: Annotated[bool, Option()] = False) -> int:
        del io
        SEEN.append(loud)
        return 0

    return registry


def _not_stdin(value: str) -> None:
    if value == "-":
        msg = "standard input is refused here"
        raise ValueError(msg)


def _judge(value: str) -> None:
    JUDGED.append(value)


@pytest.fixture
def tester(registry: CommandsLocator) -> ApplicationTester:
    return ApplicationTester(Application("acme", "1.2.0", commands=registry))


TAKEN: list[tuple[list[str], list[object]]] = [
    (["read", "-"], ["-", None, False]),
    (["read", "-", "-"], ["-", "-", False]),
    (["read", "-", "--upper"], ["-", None, True]),
    (["read", "--upper", "-"], ["-", None, True]),
    (["read", "file", "-"], ["file", "-", False]),
    (["read", "-", "file"], ["-", "file", False]),
    (["read", "--", "-"], ["-", None, False]),
    (["read", "-", "--", "-v"], ["-", "-v", False]),
    (["cat", "a", "-", "b"], [("a", "-", "b")]),
    (["cat", "-", "--", "--x"], [("-", "--x")]),
    (["write", "--output", "-"], ["-"]),
    (["write", "--output=-"], ["-"]),
]


@pytest.mark.parametrize(("argv", "seen"), TAKEN, ids=[" ".join(argv) for argv, _ in TAKEN])
async def test_a_bare_dash_reaches_the_command_as_a_value(
    tester: ApplicationTester, argv: list[str], seen: list[object]
) -> None:
    assert await tester.execute(argv) == ExitCode.SUCCESS, tester.error_display

    assert seen == SEEN


async def test_a_bare_dash_for_a_path_is_the_path_named_dash(tester: ApplicationTester) -> None:
    assert await tester.execute(["open", "-"]) == ExitCode.SUCCESS

    assert [Path("-")] == SEEN


async def test_an_arguments_own_validator_judges_the_bare_dash_itself(
    tester: ApplicationTester,
) -> None:
    assert await tester.execute(["judged", "-"]) == ExitCode.SUCCESS

    # Once to try the line, once to run it: never the marker the parser carried it as.
    assert set(JUDGED) == {"-"}
    assert SEEN == ["-"]


async def test_a_bare_dash_an_arguments_validator_refuses_fails_as_before(
    tester: ApplicationTester,
) -> None:
    assert await tester.execute(["checked", "-"]) == ExitCode.INVALID

    assert "Unknown option: -" in tester.error_display
    assert SEEN == []


@pytest.mark.parametrize(
    "argv",
    [["read", "--uper"], ["read", "-x"], ["read", "-", "--uper"], ["cat", "-", "--nope"]],
    ids=" ".join,
)
async def test_a_mistyped_option_is_still_an_unknown_option(
    tester: ApplicationTester, argv: list[str]
) -> None:
    assert await tester.execute(argv) == ExitCode.INVALID

    assert "Unknown option" in tester.error_display
    assert SEEN == []


@pytest.mark.parametrize(
    ("argv", "reported"),
    [(["count", "-"], "Unknown option: -"), (["nothing", "-"], "Unknown option: -")],
    ids=["count -", "nothing -"],
)
async def test_a_bare_dash_the_command_cannot_take_fails_as_before(
    tester: ApplicationTester, argv: list[str], reported: str
) -> None:
    assert await tester.execute(argv) == ExitCode.INVALID

    assert reported in tester.error_display
    assert "\x00" not in tester.error_display
    assert SEEN == []


async def test_a_command_line_without_a_bare_dash_is_parsed_as_written(
    tester: ApplicationTester,
) -> None:
    assert await tester.execute(["read", "file", "other", "--upper"]) == ExitCode.SUCCESS

    assert SEEN == ["file", "other", True]


async def test_help_is_still_help_beside_a_bare_dash(tester: ApplicationTester) -> None:
    assert await tester.execute(["read", "-", "--help"]) == ExitCode.SUCCESS

    assert "SOURCE" in tester.display
    assert SEEN == []
