from __future__ import annotations

from xtr_dependency_injection import when

from xtr_console import ConsoleStyle, ExitCode, as_command


@as_command("env:always", description="Always available.")
async def always(io: ConsoleStyle) -> int:
    io.text("always")
    return ExitCode.SUCCESS


@when("dev")
@as_command("env:dev-only", description="Only in dev.")
async def dev_only(io: ConsoleStyle) -> int:
    io.text("dev only")
    return ExitCode.SUCCESS
