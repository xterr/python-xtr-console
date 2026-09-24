from __future__ import annotations

from typing import final

import pytest

from xtr_console import (
    Application,
    ApplicationTester,
    CommandArguments,
    CommandDescriptor,
    CommandSignature,
    CommandsLocator,
    ConsoleStyle,
    ExitCode,
    as_command,
    default_registry,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def registry() -> CommandsLocator:
    return CommandsLocator()


@pytest.fixture
def tester(registry: CommandsLocator) -> ApplicationTester:
    return ApplicationTester(Application("acme", "1.2.0", commands=registry))


def declare_create_user(registry: CommandsLocator) -> None:
    @as_command("user:create", aliases="uc", registry=registry)
    async def create_user(io: ConsoleStyle, email: str, *, admin: bool = False) -> ExitCode:
        """Create a user.

        Args:
            email: The e-mail address.
            admin: Grant admin rights.
        """
        io.text(f"created {email} admin={admin}")
        return ExitCode.SUCCESS


def test_it_reads_its_commands_from_the_registry_it_was_given(registry: CommandsLocator) -> None:
    assert Application("acme", commands=registry).commands is registry


def test_it_reads_the_process_wide_registry_by_default() -> None:
    assert Application("acme").commands is default_registry()


# ─── help and version ────────────────────────────────────────────


async def test_no_command_lists_the_commands_under_the_name_and_version(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute([]) == ExitCode.SUCCESS
    assert tester.display.startswith("acme 1.2.0")
    assert "user:create" in tester.display


async def test_commands_are_grouped_under_their_namespace(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    @as_command("cache-clear", registry=registry)
    def cache_clear() -> None: ...

    _ = await tester.execute(["--help"])

    lines = [line.strip() for line in tester.display.splitlines()]
    assert lines.index("user") > lines.index("Available commands")
    assert any(line.startswith("user:create") for line in lines[lines.index("user") :])


async def test_a_hidden_command_is_not_listed_but_runs(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("secret", hidden=True, registry=registry)
    def secret(io: ConsoleStyle) -> None:
        io.text("ran")

    _ = await tester.execute(["--help"])
    listed = tester.display
    code = await tester.execute(["secret"])

    assert ("secret" not in listed, code, tester.display.strip()) == (True, 0, "ran")


async def test_the_description_is_shown_under_the_usage(registry: CommandsLocator) -> None:
    application = Application("acme", commands=registry, description="Acme operations console")
    tester = ApplicationTester(application)

    _ = await tester.execute(["--help"])

    assert tester.display.index("Usage") < tester.display.index("Acme operations console")


async def test_version_prints_the_name_and_version(tester: ApplicationTester) -> None:
    assert await tester.execute(["--version"]) == ExitCode.SUCCESS
    assert tester.display.strip() == "acme 1.2.0"


async def test_without_a_version_there_is_no_version_flag(registry: CommandsLocator) -> None:
    tester = ApplicationTester(Application("acme", commands=registry))

    assert await tester.execute(["--version"]) == ExitCode.INVALID


async def test_command_help_describes_arguments_and_options_from_the_docstring(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    _ = await tester.execute(["user:create", "--help"])

    assert "The e-mail address." in tester.display
    assert "Grant admin rights." in tester.display


async def test_a_description_replaces_the_docstring_summary(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("sync", description="Synchronise everything", registry=registry)
    def synchronise() -> None:
        """Docstring summary."""

    _ = await tester.execute(["--help"])

    assert "Synchronise everything" in tester.display
    assert "Docstring summary." not in tester.display


# ─── running ─────────────────────────────────────────────────────


async def test_arguments_and_options_reach_the_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create", "ada@example.com", "--admin"]) == 0
    assert tester.display.strip() == "created ada@example.com admin=True"


async def test_an_alias_runs_the_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    _ = await tester.execute(["uc", "ada@example.com"])

    assert tester.display.strip() == "created ada@example.com admin=False"


async def test_a_flag_has_no_negative_form(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create", "ada@example.com", "--no-admin"]) == 2


@pytest.mark.parametrize(("returned", "expected"), [(None, 0), (ExitCode.FAILURE, 1), (7, 7)])
async def test_what_a_command_returns_is_the_exit_code(
    registry: CommandsLocator, tester: ApplicationTester, returned: int | None, expected: int
) -> None:
    @as_command("finish", registry=registry)
    async def finish() -> int | None:
        return returned

    assert await tester.execute(["finish"]) == expected


async def test_a_class_command_is_built_and_called(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("user:import", registry=registry)
    @final
    class ImportUsers:
        async def __call__(self, io: ConsoleStyle, path: str, *, dry_run: bool = False) -> int:
            io.text(f"{path} {dry_run}")
            return 3

    assert await tester.execute(["user:import", "users.csv", "--dry-run"]) == 3
    assert tester.display.strip() == "users.csv True"


async def test_a_missing_argument_is_reported_as_invalid(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_create_user(registry)

    assert await tester.execute(["user:create"]) == ExitCode.INVALID
    assert "[ERROR]" in tester.error_display


async def test_an_unknown_command_is_reported_as_invalid(tester: ApplicationTester) -> None:
    assert await tester.execute(["nope"]) == ExitCode.INVALID
    assert 'Unknown command "nope"' in tester.error_display


# ─── failures ────────────────────────────────────────────────────


async def test_an_exception_is_rendered_and_fails_the_run(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("boom", registry=registry)
    def boom() -> None:
        raise LookupError("no such user")

    assert await tester.execute(["boom"]) == ExitCode.FAILURE
    assert "no such user" in tester.error_display


async def test_an_exception_propagates_when_not_caught(registry: CommandsLocator) -> None:
    @as_command("boom", registry=registry)
    def boom() -> None:
        raise LookupError("no such user")

    tester = ApplicationTester(Application("acme", commands=registry, catch_exceptions=False))

    with pytest.raises(LookupError):
        _ = await tester.execute(["boom"])


# ─── lifecycle ───────────────────────────────────────────────────


async def test_hooks_run_around_the_command(registry: CommandsLocator) -> None:
    events: list[str] = []

    @as_command("work", registry=registry)
    async def work() -> None:
        events.append("command")

    async def opened() -> None:
        events.append("startup")

    application = Application("acme", commands=registry)
    application.on_startup(opened)
    application.on_shutdown(lambda: events.append("shutdown"))

    _ = await ApplicationTester(application).execute(["work"])

    assert events == ["startup", "command", "shutdown"]


async def test_shutdown_hooks_run_when_the_command_raises(registry: CommandsLocator) -> None:
    events: list[str] = []

    @as_command("boom", registry=registry)
    def boom() -> None:
        raise LookupError

    application = Application("acme", commands=registry)
    application.on_shutdown(lambda: events.append("shutdown"))

    _ = await ApplicationTester(application).execute(["boom"])

    assert events == ["shutdown"]


async def test_hooks_do_not_run_for_help(registry: CommandsLocator) -> None:
    events: list[str] = []
    application = Application("acme", commands=registry)
    application.on_startup(lambda: events.append("startup"))

    _ = await ApplicationTester(application).execute(["--help"])

    assert events == []


async def test_a_replacement_invoker_runs_the_commands(registry: CommandsLocator) -> None:
    calls: list[tuple[str, CommandArguments]] = []

    @final
    class RecordingInvoker:
        async def invoke(
            self,
            command: CommandDescriptor,
            signature: CommandSignature,
            arguments: CommandArguments,
        ) -> object:
            del signature
            calls.append((command.name, arguments))
            return 5

    @as_command("greet", registry=registry)
    def greet(name: str) -> None:
        del name

    application = Application("acme", commands=registry)
    application.use_invoker(RecordingInvoker())

    assert await ApplicationTester(application).execute(["greet", "ada"]) == 5
    assert calls == [("greet", CommandArguments((), {"name": "ada"}))]


def test_run_drives_its_own_event_loop(
    registry: CommandsLocator, capsys: pytest.CaptureFixture[str]
) -> None:
    @as_command("greet", registry=registry)
    async def greet(io: ConsoleStyle, name: str) -> int:
        io.text(f"hello {name}")
        return 4

    assert Application("acme", commands=registry).run(["greet", "ada"]) == 4
    assert capsys.readouterr().out.strip() == "hello ada"
