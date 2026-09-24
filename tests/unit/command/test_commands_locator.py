from __future__ import annotations

import pytest

from xtr_console import (
    CommandDescriptor,
    CommandsLocator,
    CommandsLocatorInterface,
    DuplicateCommandError,
)


def command() -> None:
    """Does nothing."""


def test_it_satisfies_its_interface() -> None:
    assert isinstance(CommandsLocator(), CommandsLocatorInterface)


def test_register_returns_the_command() -> None:
    registry = CommandsLocator()
    declared = CommandDescriptor(target=command, name="a")

    assert registry.register(declared) is declared


def test_commands_come_back_in_the_order_declared() -> None:
    registry = CommandsLocator()
    first = registry.register(CommandDescriptor(target=command, name="b"))
    second = registry.register(CommandDescriptor(target=command, name="a"))

    assert registry.commands() == (first, second)


def test_a_taken_name_is_refused() -> None:
    registry = CommandsLocator()
    _ = registry.register(CommandDescriptor(target=command, name="a"))

    with pytest.raises(DuplicateCommandError) as raised:
        _ = registry.register(CommandDescriptor(target=command, name="a"))

    assert (raised.value.name, raised.value.claimed_by) == ("a", "a")


def test_an_alias_clashing_with_a_name_is_refused() -> None:
    registry = CommandsLocator()
    _ = registry.register(CommandDescriptor(target=command, name="user:create"))

    with pytest.raises(DuplicateCommandError) as raised:
        _ = registry.register(CommandDescriptor(target=command, name="b", aliases=("user:create",)))

    assert raised.value.claimed_by == "user:create"


def test_a_refused_command_leaves_the_registry_unchanged() -> None:
    registry = CommandsLocator()
    kept = registry.register(CommandDescriptor(target=command, name="a", aliases=("x",)))

    with pytest.raises(DuplicateCommandError):
        _ = registry.register(CommandDescriptor(target=command, name="b", aliases=("x",)))

    assert registry.commands() == (kept,)
