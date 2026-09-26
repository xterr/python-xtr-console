from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Injected, Target, as_service

from xtr_console import ConsoleStyle, ExitCode, as_command


@final
@as_service()
class Repo:
    def value(self) -> str:
        return "from app one"


@as_command("only:one")
async def only_one(io: ConsoleStyle, repo: Injected[Repo]) -> int:
    io.text(repo.value())
    return ExitCode.SUCCESS


@final
@as_command("only:one:cls")
class OnlyOneCommand:
    def __init__(self, repo: Repo) -> None:
        self._repo = repo

    async def __call__(self, io: ConsoleStyle) -> int:
        io.text(self._repo.value())
        return ExitCode.SUCCESS


@final
class Greeter:
    def __init__(self, text: str) -> None:
        self.text = text


@as_service(qualifier="formal")
def formal_greeter() -> Greeter:
    return Greeter("good day from app one")


@as_command("only:one:qualified")
async def only_one_qualified(
    io: ConsoleStyle, greeter: Annotated[Greeter, Target("formal")]
) -> int:
    io.text(greeter.text)
    return ExitCode.SUCCESS
