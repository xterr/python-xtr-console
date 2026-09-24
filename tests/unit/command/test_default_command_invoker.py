from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

import pytest
from wireup import Injected

from xtr_console import (
    CommandArguments,
    CommandDescriptor,
    CommandInvokerInterface,
    CommandSignature,
    DefaultCommandInvoker,
    MissingContainerError,
)

if TYPE_CHECKING:
    from xtr_console.command import CommandTarget

pytestmark = pytest.mark.anyio


@final
class Session:
    """Something a container would supply."""


InjectedSession = Injected[Session]


async def invoke(target: CommandTarget, arguments: CommandArguments | None = None) -> object:
    command = CommandDescriptor(target=target, name="test")
    return await DefaultCommandInvoker().invoke(
        command, CommandSignature.of(command), arguments or CommandArguments()
    )


def test_it_satisfies_its_interface() -> None:
    assert isinstance(DefaultCommandInvoker(), CommandInvokerInterface)


async def test_an_async_function_is_awaited_with_the_arguments() -> None:
    async def command(name: str, *, loud: bool) -> str:
        return f"{name}:{loud}"

    result = await invoke(command, CommandArguments(("ada",), {"loud": True}))

    assert result == "ada:True"


async def test_a_sync_function_is_called() -> None:
    def command(name: str) -> int:
        return len(name)

    assert await invoke(command, CommandArguments(("ada",))) == 3


async def test_a_class_is_built_bare_and_called() -> None:
    @final
    class Command:
        async def __call__(self, name: str) -> str:
            return name.upper()

    assert await invoke(Command, CommandArguments(("ada",))) == "ADA"


async def test_a_class_is_built_only_when_it_runs() -> None:
    @final
    class Command:
        built: ClassVar[int] = 0

        def __init__(self) -> None:
            Command.built += 1

        def __call__(self) -> None: ...

    command = CommandDescriptor(target=Command, name="test")
    signature = CommandSignature.of(command)
    built_before = Command.built

    _ = await DefaultCommandInvoker().invoke(command, signature, CommandArguments())

    assert (built_before, Command.built) == (0, 1)


async def test_a_constructor_needing_arguments_asks_for_a_container() -> None:
    @final
    class Command:
        def __init__(self, session: Session, retries: int = 3) -> None:
            del session, retries

        def __call__(self) -> None: ...

    with pytest.raises(MissingContainerError) as raised:
        _ = await invoke(Command)

    assert raised.value.parameters == ("session",)


async def test_a_container_parameter_asks_for_a_container() -> None:
    async def command(db: InjectedSession) -> None:
        del db

    with pytest.raises(MissingContainerError) as raised:
        _ = await invoke(command)

    assert raised.value.parameters == ("db",)
