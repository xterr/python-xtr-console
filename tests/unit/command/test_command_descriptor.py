from __future__ import annotations

import pytest

from xtr_console import CommandDescriptor, CommandSignatureError
from xtr_console.command import default_name_of
from xtr_console.command.command_descriptor import call_of


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
