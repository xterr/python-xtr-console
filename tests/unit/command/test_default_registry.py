from __future__ import annotations

from xtr_console import CommandsLocator, default_registry


def test_it_is_one_registry_for_the_whole_process() -> None:
    assert default_registry() is default_registry()


def test_it_is_a_commands_locator() -> None:
    assert isinstance(default_registry(), CommandsLocator)
