"""Unit tests for the built-in ``list`` command."""

from __future__ import annotations

import pytest

from xtr_console import (
    Application,
    ApplicationTester,
    CommandsLocator,
    ConsoleStyle,
    ExitCode,
    as_command,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def registry() -> CommandsLocator:
    return CommandsLocator()


@pytest.fixture
def tester(registry: CommandsLocator) -> ApplicationTester:
    return ApplicationTester(Application("acme", "1.2.0", commands=registry))


def declare_commands(registry: CommandsLocator) -> None:
    @as_command("user:create", aliases="uc", description="Create a user.", registry=registry)
    async def create_user(io: ConsoleStyle, email: str) -> ExitCode:
        del io, email
        return ExitCode.SUCCESS

    @as_command("user:delete", description="Delete a user.", registry=registry)
    async def delete_user(io: ConsoleStyle, email: str) -> ExitCode:
        del io, email
        return ExitCode.SUCCESS

    @as_command("cache:warm", description="Warm the cache.", registry=registry)
    async def warm_cache(io: ConsoleStyle) -> ExitCode:
        del io
        return ExitCode.SUCCESS

    @as_command("stat", description="Print statistics.", registry=registry)
    async def stat(io: ConsoleStyle) -> ExitCode:
        del io
        return ExitCode.SUCCESS


# ─── container-less list ────────────────────────────────────────


async def test_list_prints_the_name_version_and_every_command(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    code = await tester.execute(["list"])

    display = tester.display
    assert code == ExitCode.SUCCESS
    assert display.startswith("acme 1.2.0")
    assert "Available commands:" in display
    assert "user:create" in display
    assert "user:delete" in display
    assert "cache:warm" in display
    assert "stat" in display
    assert "Create a user." in display


async def test_list_shows_commands_grouped_and_sorted_by_namespace(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    _ = await tester.execute(["list"])
    lines = [line.strip() for line in tester.display.splitlines() if line.strip()]

    cache_at = lines.index("cache")
    user_at = lines.index("user")
    assert cache_at < user_at
    assert any(line.startswith("cache:warm") for line in lines[cache_at:user_at])
    assert any(line.startswith("user:create") for line in lines[user_at:])
    assert any(line.startswith("user:delete") for line in lines[user_at:])
    stat_at = next(index for index, line in enumerate(lines) if line.startswith("stat"))
    assert stat_at < cache_at


async def test_list_shows_aliases_in_parentheses(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    _ = await tester.execute(["list"])

    assert "user:create (uc)" in tester.display


async def test_list_hides_hidden_commands(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("secret", hidden=True, registry=registry)
    async def secret(io: ConsoleStyle) -> ExitCode:
        del io
        return ExitCode.SUCCESS

    _ = await tester.execute(["list"])

    assert "secret" not in tester.display


async def test_list_without_a_version_still_prints_the_name(registry: CommandsLocator) -> None:
    declare_commands(registry)
    tester = ApplicationTester(Application("acme", commands=registry))

    _ = await tester.execute(["list"])

    assert tester.display.startswith("acme")
    assert "1.2.0" not in tester.display


async def test_list_prints_the_description_under_the_header(registry: CommandsLocator) -> None:
    declare_commands(registry)
    tester = ApplicationTester(
        Application("acme", "1.2.0", description="Acme operations console", commands=registry)
    )

    _ = await tester.execute(["list"])

    assert "Acme operations console" in tester.display


# ─── namespace filter ────────────────────────────────────────────


async def test_list_namespace_shows_only_that_namespace(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    code = await tester.execute(["list", "user"])

    assert code == ExitCode.SUCCESS
    assert "user:create" in tester.display
    assert "user:delete" in tester.display
    assert "cache:warm" not in tester.display
    assert "stat" not in tester.display
    assert 'Available commands for the "user" namespace' in tester.display


# ─── unknown namespace ───────────────────────────────────────────


async def test_list_unknown_namespace_ends_the_run_with_invalid(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    code = await tester.execute(["list", "nope"])

    assert code == ExitCode.INVALID
    assert 'There are no commands defined in the "nope" namespace.' in tester.display


async def test_list_unknown_namespace_with_no_commands_errors_too(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    del registry

    code = await tester.execute(["list", "nope"])

    assert code == ExitCode.INVALID


# ─── user override ───────────────────────────────────────────────


async def test_a_user_declared_list_command_overrides_the_builtin(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    @as_command("list", registry=registry)
    async def my_list(io: ConsoleStyle) -> ExitCode:
        io.text("my list ran")
        return ExitCode.SUCCESS

    code = await tester.execute(["list"])

    assert code == ExitCode.SUCCESS
    assert tester.display.strip() == "my list ran"
    assert "Available commands:" not in tester.display


async def test_a_user_alias_named_list_overrides_the_builtin(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    @as_command("show", aliases="list", registry=registry)
    async def show(io: ConsoleStyle) -> ExitCode:
        io.text("show ran")
        return ExitCode.SUCCESS

    code = await tester.execute(["list"])

    assert code == ExitCode.SUCCESS
    assert tester.display.strip() == "show ran"


# ─── visible in help ─────────────────────────────────────────────


async def test_the_builtin_list_appears_in_the_help(
    registry: CommandsLocator, tester: ApplicationTester
) -> None:
    declare_commands(registry)

    _ = await tester.execute(["--help"])

    assert "list" in tester.display
    assert "List commands" in tester.display
