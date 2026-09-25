from __future__ import annotations

import pytest

from xtr_console import (
    Application,
    CommandsLocator,
    CommandTester,
    ConsoleStyle,
    Verbosity,
    as_command,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def tester() -> CommandTester:
    registry = CommandsLocator()

    @as_command("user:create", registry=registry)
    def create_user(io: ConsoleStyle, email: str, *, admin: bool = False) -> int:
        role = io.ask("Role?", "user")
        io.text(f"{email} admin={admin} role={role}")
        io.error_console.print("created")
        return 0 if admin else 1

    return CommandTester(Application("acme", commands=registry), "user:create")


def test_there_is_no_status_code_before_the_first_run(tester: CommandTester) -> None:
    assert tester.status_code is None


async def test_the_arguments_follow_the_command_name(tester: CommandTester) -> None:
    code = await tester.execute(["ada@example.com", "--admin"], interactive=False)

    assert (code, tester.status_code) == (0, 0)
    assert tester.display.strip() == "ada@example.com admin=True role=user"


async def test_it_feeds_the_inputs_to_questions(tester: CommandTester) -> None:
    _ = await tester.execute(["ada@example.com"], inputs=["editor"])

    assert tester.display.splitlines()[-1] == "ada@example.com admin=False role=editor"


async def test_standard_error_is_captured_apart(tester: CommandTester) -> None:
    _ = await tester.execute(["ada@example.com"], interactive=False)

    assert tester.error_display.strip() == "created"


async def test_it_runs_the_command_at_the_verbosity_given() -> None:
    registry = CommandsLocator()

    @as_command("inspect", registry=registry)
    def inspect_run(io: ConsoleStyle) -> int:
        io.text(io.verbosity.name)
        return 0

    tester = CommandTester(Application("acme", commands=registry), "inspect")

    _ = await tester.execute(verbosity=Verbosity.VERY_VERBOSE)

    assert tester.display.strip() == "VERY_VERBOSE"
