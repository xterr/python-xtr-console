from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, final

import pytest

from xtr_console import (
    CommandDescriptor,
    CommandSignatureError,
    DuplicateCommandError,
    InvalidCommandNameError,
)
from xtr_console.command import default_name_of
from xtr_console.command.command_descriptor import call_of, function_of

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


def create_user() -> None:
    """A function command."""


class ImportUsersCommand:
    def __call__(self) -> None:
        """A class command."""


class InheritedCommand(ImportUsersCommand):
    pass


class NotACommand:
    pass


def test_names_lists_the_name_before_the_aliases() -> None:
    command = CommandDescriptor(target=create_user, name="user:create", aliases=("uc", "add"))

    assert command.names == ("user:create", "uc", "add")


def test_the_namespace_is_what_precedes_the_first_colon() -> None:
    command = CommandDescriptor(target=create_user, name="cache:pool:clear")

    assert command.namespace == "cache"


def test_a_name_without_a_colon_has_no_namespace() -> None:
    command = CommandDescriptor(target=create_user, name="create-user")

    assert command.namespace is None


def test_a_class_without_call_is_refused() -> None:
    with pytest.raises(CommandSignatureError) as raised:
        _ = CommandDescriptor(target=NotACommand, name="nope")

    assert raised.value.command_name == "nope"


def test_a_function_is_named_in_kebab_case() -> None:
    assert default_name_of(create_user) == "create-user"


def test_a_class_is_named_in_kebab_case_without_its_command_suffix() -> None:
    assert default_name_of(ImportUsersCommand) == "import-users"


def test_an_acronym_in_a_class_name_stays_one_word() -> None:
    class HTTPServerCommand:
        def __call__(self) -> None: ...

    assert default_name_of(HTTPServerCommand) == "http-server"


def test_a_class_named_only_command_keeps_its_name() -> None:
    class Command:
        def __call__(self) -> None: ...

    assert default_name_of(Command) == "command"


def test_call_of_finds_an_inherited_call() -> None:
    assert call_of(InheritedCommand) is ImportUsersCommand.__dict__["__call__"]


def test_call_of_ignores_the_metaclass_call() -> None:
    assert call_of(NotACommand) is None


@pytest.mark.parametrize("name", ["", "user create", "tab\tname", "-x", "--help"])
def test_a_name_nobody_could_type_is_refused(name: str) -> None:
    with pytest.raises(InvalidCommandNameError) as raised:
        _ = CommandDescriptor(target=create_user, name=name)

    assert raised.value.name == name


def test_an_alias_nobody_could_type_is_refused() -> None:
    with pytest.raises(InvalidCommandNameError):
        _ = CommandDescriptor(target=create_user, name="user:create", aliases=("-u",))


@pytest.mark.parametrize("aliases", [("user:create",), ("uc", "uc")])
def test_a_command_repeating_one_of_its_names_is_refused(aliases: tuple[str, ...]) -> None:
    with pytest.raises(DuplicateCommandError) as raised:
        _ = CommandDescriptor(target=create_user, name="user:create", aliases=aliases)

    assert raised.value.claimed_by == "user:create"


def test_a_generator_is_refused() -> None:
    def lines() -> Iterator[str]:
        yield "never runs"

    with pytest.raises(CommandSignatureError, match="generator"):
        _ = CommandDescriptor(target=lines, name="lines")


def test_an_async_generator_is_refused() -> None:
    async def lines() -> AsyncIterator[str]:
        yield "never runs"

    with pytest.raises(CommandSignatureError, match="generator"):
        _ = CommandDescriptor(target=lines, name="lines")


def test_a_class_with_a_generator_call_is_refused() -> None:
    class Lines:
        def __call__(self) -> Iterator[str]:
            yield "never runs"

    with pytest.raises(CommandSignatureError, match="generator"):
        _ = CommandDescriptor(target=Lines, name="lines")


def test_function_of_unwraps_a_static_call() -> None:
    @final
    class Static:
        @staticmethod
        def __call__() -> None: ...

    assert inspect.isfunction(function_of(Static))


def test_function_of_a_callable_object_is_its_types_call() -> None:
    instance = ImportUsersCommand()

    assert function_of(instance) is ImportUsersCommand.__dict__["__call__"]
