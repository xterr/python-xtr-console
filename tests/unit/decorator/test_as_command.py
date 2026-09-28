from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_console import CommandSignatureError, CommandsLocator, as_command, default_registry
from xtr_console.command.commands_declared_on import commands_declared_on

if TYPE_CHECKING:
    from xtr_console import CommandCallable


def test_a_bare_decoration_returns_the_function_unchanged() -> None:
    async def create_user() -> int:
        return 0

    assert as_command(create_user) is create_user


def test_a_bare_decoration_names_the_command_after_the_function() -> None:
    before = len(default_registry().commands())

    @as_command
    async def test_as_command_bare_default_registry() -> int:
        return 0

    declared = default_registry().commands()[before:]
    assert [command.name for command in declared] == ["test-as-command-bare-default-registry"]


def test_a_declaration_registers_into_the_given_registry() -> None:
    registry = CommandsLocator()

    @as_command("user:create", registry=registry)
    async def create_user() -> int:
        return 0

    assert [command.target for command in registry.commands()] == [create_user]


def test_a_declaration_returns_what_it_decorates() -> None:
    registry = CommandsLocator()

    async def create_user() -> int:
        return 0

    assert as_command("user:create", registry=registry)(create_user) is create_user


def test_empty_parentheses_name_the_command_after_what_it_decorates() -> None:
    registry = CommandsLocator()

    @as_command(registry=registry)
    class ImportUsersCommand:
        def __call__(self) -> int:
            return 0

    assert registry.commands()[0].name == "import-users"


def test_every_property_is_recorded() -> None:
    registry = CommandsLocator()

    @as_command(
        "user:create", aliases=("uc", "add"), description="Add one", hidden=True, registry=registry
    )
    async def create_user() -> int:
        return 0

    command = registry.commands()[0]
    assert (command.aliases, command.description, command.hidden) == (
        ("uc", "add"),
        "Add one",
        True,
    )


def test_a_single_alias_may_be_a_string() -> None:
    registry = CommandsLocator()

    @as_command("user:create", aliases="uc", registry=registry)
    async def create_user() -> int:
        return 0

    assert registry.commands()[0].aliases == ("uc",)


def test_a_class_without_call_is_refused() -> None:
    registry = CommandsLocator()

    class NotACommand:
        pass

    # A type checker already refuses this; the runtime check is under test.
    declared = cast("type[CommandCallable]", cast("object", NotACommand))

    with pytest.raises(CommandSignatureError):
        _ = as_command("nope", registry=registry)(declared)


def test_a_decorated_subclass_declares_only_its_own_command() -> None:
    registry = CommandsLocator()

    @as_command("base", registry=registry)
    class Base:
        async def __call__(self) -> int:
            return 0

    @as_command("child", registry=registry)
    class Child(Base):
        pass

    assert [entry.name for entry in commands_declared_on(Base)] == ["base"]
    assert [entry.name for entry in commands_declared_on(Child)] == ["child"]
