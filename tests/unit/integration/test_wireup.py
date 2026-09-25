"""Every way wireup can hand a command what it needs.

Each test builds its own application and container, so every singleton — a
command class among them — starts fresh, and no run leaks into another test.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator
from typing import ClassVar, final

import pytest
import wireup
from wireup import AsyncContainer, Injected, injectable
from wireup.errors import WireupError
from xtr_logging import LoggerInterface, LoggingConfig
from xtr_logging.config import ConsoleHandlerSpec
from xtr_logging.integration.wireup import injectables as logging_injectables
from xtr_logging.processor.processor_registry import ProcessorRegistry

from xtr_console import (
    Application,
    ApplicationAlreadyWiredError,
    ApplicationTester,
    CommandsLocator,
    ConsoleStyle,
    UnregisteredCommandError,
    as_command,
)
from xtr_console.integration.wireup import injectables

pytestmark = pytest.mark.anyio

COMMANDS = CommandsLocator()

# ─── what the container knows about ──────────────────────────────


@final
class Session:
    def __init__(self) -> None:
        self.open = True


sessions: list[Session] = []


@injectable(lifetime="scoped")
async def session() -> AsyncIterator[Session]:
    """One per run, closed when the command returns."""
    made = Session()
    sessions.append(made)
    try:
        yield made
    finally:
        made.open = False


@injectable
@final
class Greeter:
    def greet(self, name: str) -> str:
        return f"hello {name}"


@final
class Unknown:
    """Nothing provides this."""


# ─── commands ────────────────────────────────────────────────────


@as_command("user:create", registry=COMMANDS)
async def create_user(
    email: str, db: Injected[Session], io: ConsoleStyle, *, admin: bool = False
) -> int:
    io.text(f"{email} admin={admin} open={db.open}")
    return 0


@as_command("user:import", registry=COMMANDS)
@final
class ImportUsers:
    built: ClassVar[list[ImportUsers]] = []

    def __init__(self, greeter: Greeter) -> None:
        self.greeter = greeter
        ImportUsers.built.append(self)

    async def __call__(self, io: ConsoleStyle, path: str, db: Injected[Session]) -> int:
        io.text(f"{self.greeter.greet(path)} open={db.open}")
        return 3


@as_command("user:count", registry=COMMANDS)
@final
class CountUsers:
    def __call__(self, io: ConsoleStyle, greeter: Injected[Greeter]) -> int:
        io.text(greeter.greet("sync"))
        return 0


@as_command("broken", registry=COMMANDS)
async def broken(thing: Injected[Unknown]) -> int:
    del thing
    return 0


def container_for(application: Application) -> AsyncContainer:
    return wireup.create_async_container(injectables=[session, Greeter, *injectables(application)])


@pytest.fixture
async def container() -> AsyncIterator[AsyncContainer]:
    sessions.clear()
    ImportUsers.built.clear()
    made = container_for(Application("acme", commands=COMMANDS, catch_exceptions=False))
    yield made
    await made.close()


@pytest.fixture
async def tester(container: AsyncContainer) -> ApplicationTester:
    return ApplicationTester(await container.get(Application))


# ─── the application ─────────────────────────────────────────────


async def test_the_container_provides_the_application_it_was_given() -> None:
    application = Application("acme", commands=COMMANDS)

    provided = await container_for(application).get(Application)

    assert provided is application


async def test_one_application_cannot_be_wired_to_two_containers() -> None:
    application = Application("acme", commands=COMMANDS)
    _ = await container_for(application).get(Application)

    with pytest.raises(ApplicationAlreadyWiredError):
        _ = await container_for(application).get(Application)


async def test_the_same_container_provides_the_application_every_time() -> None:
    container = container_for(Application("acme", commands=COMMANDS))

    assert await container.get(Application) is await container.get(Application)


# ─── functions ───────────────────────────────────────────────────


async def test_a_function_receives_what_the_container_provides(tester: ApplicationTester) -> None:
    _ = await tester.execute(["user:create", "ada@example.com", "--admin"])

    assert tester.display.strip() == "ada@example.com admin=True open=True"


async def test_global_options_leave_what_the_container_provides_in_place(
    tester: ApplicationTester,
) -> None:
    _ = await tester.execute(["-vvv", "user:import", "users.csv", "-n"])

    assert tester.display.strip() == "hello users.csv open=True"


async def test_a_quiet_run_through_the_container_still_releases_its_scope(
    tester: ApplicationTester,
) -> None:
    assert await tester.execute(["user:create", "ada@example.com", "-q"]) == 0
    assert (tester.display, [made.open for made in sessions]) == ("", [False])


async def test_a_scoped_dependency_is_closed_when_the_command_returns(
    tester: ApplicationTester,
) -> None:
    _ = await tester.execute(["user:create", "ada@example.com"])

    assert [made.open for made in sessions] == [False]


async def test_every_run_gets_a_scope_of_its_own(tester: ApplicationTester) -> None:
    _ = await tester.execute(["user:create", "a@example.com"])
    _ = await tester.execute(["user:create", "b@example.com"])

    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]


async def test_container_parameters_stay_off_the_command_line(tester: ApplicationTester) -> None:
    _ = await tester.execute(["user:create", "--help"])

    assert "db" not in tester.display.lower().split()


# ─── classes ─────────────────────────────────────────────────────


async def test_a_class_is_built_by_the_container_and_its_call_filled_per_run(
    tester: ApplicationTester,
) -> None:
    assert await tester.execute(["user:import", "users.csv"]) == 3
    assert tester.display.strip() == "hello users.csv open=True"


async def test_a_class_is_built_only_when_it_first_runs(tester: ApplicationTester) -> None:
    built_before = len(ImportUsers.built)

    _ = await tester.execute(["user:import", "users.csv"])

    assert (built_before, len(ImportUsers.built)) == (0, 1)


async def test_a_class_is_one_instance_for_every_run(tester: ApplicationTester) -> None:
    _ = await tester.execute(["user:import", "a.csv"])
    _ = await tester.execute(["user:import", "b.csv"])

    assert len(ImportUsers.built) == 1
    assert len(sessions) == 2


async def test_a_class_with_a_sync_call_is_filled_too(tester: ApplicationTester) -> None:
    _ = await tester.execute(["user:count"])

    assert tester.display.strip() == "hello sync"


def test_a_constructor_asking_for_a_scoped_dependency_is_refused() -> None:
    commands = CommandsLocator()

    @as_command("per-run", registry=commands)
    @final
    class PerRun:
        def __init__(self, db: Session) -> None:
            self.db = db

        def __call__(self) -> int:
            return 0

    with pytest.raises(WireupError):
        _ = container_for(Application("acme", commands=commands))


async def test_a_class_declared_after_the_container_is_refused() -> None:
    commands = CommandsLocator()
    container = container_for(Application("acme", commands=commands, catch_exceptions=False))

    @as_command("late", registry=commands)
    @final
    class Late:
        def __call__(self) -> int:
            return 0

    tester = ApplicationTester(await container.get(Application))

    with pytest.raises(UnregisteredCommandError):
        _ = await tester.execute(["late"])


async def test_a_dependency_nothing_provides_is_refused_naming_the_command(
    tester: ApplicationTester,
) -> None:
    with pytest.raises(WireupError, match="function broken"):
        _ = await tester.execute(["broken"])


# ─── optional ────────────────────────────────────────────────────


# ─── xtr-logging ─────────────────────────────────────────────────

LOGGED = CommandsLocator()


@as_command("audit", registry=LOGGED)
async def audit(logger: Injected[LoggerInterface]) -> int:
    for level in ("debug", "info", "notice", "warning", "error"):
        message = f"at {level}"
        logger.log(level, message)
    return 0


@pytest.fixture
async def logged() -> AsyncIterator[ApplicationTester]:
    config = LoggingConfig(handlers={"console": ConsoleHandlerSpec()})
    made = wireup.create_async_container(
        injectables=[
            *logging_injectables(config, registry=ProcessorRegistry()),
            *injectables(Application("acme", commands=LOGGED, catch_exceptions=False)),
        ],
    )
    yield ApplicationTester(await made.get(Application))
    await made.close()


@pytest.mark.parametrize(
    ("argv", "printed"),
    [
        ([], ["warning", "error"]),
        (["-q"], ["error"]),
        (["-v"], ["notice", "warning", "error"]),
        (["-vvv"], ["debug", "info", "notice", "warning", "error"]),
        (["--silent"], []),
    ],
)
async def test_the_containers_console_logs_follow_each_command(
    logged: ApplicationTester, argv: list[str], printed: list[str]
) -> None:
    _ = await logged.execute(["audit", *argv])

    levels = ["debug", "info", "notice", "warning", "error"]
    assert [level for level in levels if f"at {level}" in logged.error_display] == printed


async def test_each_run_logs_to_its_own_error_output(logged: ApplicationTester) -> None:
    _ = await logged.execute(["audit", "-vvv"])
    _ = await logged.execute(["audit"])

    assert "at debug" not in logged.error_display


def test_the_core_never_imports_wireup() -> None:
    code = "import sys, xtr_console; print('wireup' in sys.modules)"

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"
