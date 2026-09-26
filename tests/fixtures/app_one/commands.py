from __future__ import annotations

from typing import final

from xtr_dependency_injection import Injected, as_service

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
