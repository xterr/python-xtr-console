from __future__ import annotations

from xtr_console import ConsoleStyle, ExitCode, as_command


@as_command("only:two")
async def only_two(io: ConsoleStyle) -> int:
    io.text("from app two")
    return ExitCode.SUCCESS
