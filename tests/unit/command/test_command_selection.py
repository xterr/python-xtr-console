from __future__ import annotations

import pytest

from xtr_console import CommandDescriptor
from xtr_console.command import CommandSelection


def command() -> int:
    return 0


CREATE = CommandDescriptor(target=command, name="user:create", aliases=("uc",))
DELETE = CommandDescriptor(target=command, name="user:delete")
WARM = CommandDescriptor(target=command, name="cache:warm")
LIST = CommandDescriptor(target=command, name="list")
DECLARED = (CREATE, DELETE, WARM, LIST)


@pytest.mark.parametrize("name", ["user:create", "uc"])
def test_a_command_line_naming_a_command_selects_only_it(name: str) -> None:
    selection = CommandSelection.of(DECLARED, [name, "ada@example.com"])

    assert selection == CommandSelection((CREATE,), (name, "ada@example.com"))


@pytest.mark.parametrize("tokens", [["user"], ["user", "--help"], ["user", "-h"]])
def test_a_command_line_naming_a_namespace_asks_for_its_commands(tokens: list[str]) -> None:
    selection = CommandSelection.of(DECLARED, tokens)

    assert selection == CommandSelection((CREATE, DELETE), ("--help",))


def test_a_namespace_followed_by_anything_else_selects_everything() -> None:
    selection = CommandSelection.of(DECLARED, ["user", "create"])

    assert selection == CommandSelection(DECLARED, ("user", "create"))


def test_a_command_named_like_a_namespace_wins() -> None:
    user = CommandDescriptor(target=command, name="user")

    selection = CommandSelection.of((*DECLARED, user), ["user"])

    assert selection.commands == (user,)


@pytest.mark.parametrize("tokens", [[], ["--help"], ["nope"]])
def test_anything_else_selects_every_command(tokens: list[str]) -> None:
    selection = CommandSelection.of(DECLARED, tokens)

    assert selection == CommandSelection(DECLARED, tuple(tokens))
