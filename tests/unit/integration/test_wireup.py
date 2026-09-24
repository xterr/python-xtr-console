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

from xtr_console import (
    Application,
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
) -> None:
    io.text(f"{email} admin={admin} open={db.open}")


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
    def __call__(self, io: ConsoleStyle, greeter: Injected[Greeter]) -> None:
        io.text(greeter.greet("sync"))


@as_command("broken", registry=COMMANDS)
async def broken(thing: Injected[Unknown]) -> None:
    del thing


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


# ─── functions ───────────────────────────────────────────────────


async def test_a_function_receives_what_the_container_provides(tester: ApplicationTester) -> None:
    _ = await tester.execute(["user:create", "ada@example.com", "--admin"])

    assert tester.display.strip() == "ada@example.com admin=True open=True"


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

        def __call__(self) -> None: ...

    with pytest.raises(WireupError):
        _ = container_for(Application("acme", commands=commands))


async def test_a_class_declared_after_the_container_is_refused() -> None:
    commands = CommandsLocator()
    container = container_for(Application("acme", commands=commands, catch_exceptions=False))

    @as_command("late", registry=commands)
    @final
    class Late:
        def __call__(self) -> None: ...

    tester = ApplicationTester(await container.get(Application))

    with pytest.raises(UnregisteredCommandError):
        _ = await tester.execute(["late"])


async def test_a_dependency_nothing_provides_is_refused(tester: ApplicationTester) -> None:
    with pytest.raises(WireupError):
        _ = await tester.execute(["broken"])


# ─── optional ────────────────────────────────────────────────────


def test_the_core_never_imports_wireup() -> None:
    code = "import sys, xtr_console; print('wireup' in sys.modules)"

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"
