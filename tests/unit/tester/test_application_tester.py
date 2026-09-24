from __future__ import annotations

import pytest

from xtr_console import Application, ApplicationTester, CommandsLocator, ConsoleStyle, as_command

pytestmark = pytest.mark.anyio


@pytest.fixture
def application() -> Application:
    registry = CommandsLocator()

    @as_command("greet", registry=registry)
    def greet(io: ConsoleStyle) -> int:
        io.text(f"hello {io.ask('Name?', 'nobody')}")
        io.error_console.print("to stderr")
        return 3

    return Application("acme", commands=registry)


def test_there_is_no_status_code_before_the_first_run(application: Application) -> None:
    assert ApplicationTester(application).status_code is None


async def test_it_returns_and_records_the_exit_code(application: Application) -> None:
    tester = ApplicationTester(application)

    assert (await tester.execute(["greet"], inputs=["ada"]), tester.status_code) == (3, 3)


async def test_it_feeds_the_inputs_to_questions(application: Application) -> None:
    tester = ApplicationTester(application)

    _ = await tester.execute(["greet"], inputs=["ada"])

    assert tester.display.splitlines()[-1] == "hello ada"


async def test_a_run_that_is_not_interactive_answers_with_defaults(
    application: Application,
) -> None:
    tester = ApplicationTester(application)

    _ = await tester.execute(["greet"], interactive=False)

    assert tester.display.strip() == "hello nobody"


async def test_standard_error_is_captured_apart(application: Application) -> None:
    tester = ApplicationTester(application)

    _ = await tester.execute(["greet"], interactive=False)

    assert (tester.error_display.strip(), "to stderr" in tester.display) == ("to stderr", False)


async def test_output_is_plain_text(application: Application) -> None:
    tester = ApplicationTester(application)

    _ = await tester.execute(["--help"])

    assert "\x1b[" not in tester.display
