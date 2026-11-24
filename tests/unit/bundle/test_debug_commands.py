"""The kernel's debug commands stay out of the process-wide registry."""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_dependency_injection.bundle import AdvertisedBundles
from xtr_dependency_injection.diagnostics.report import (
    ConfigReport,
    KernelReport,
    ScanReport,
    SetAsideReport,
)

from xtr_console import ConsoleStyle, ExitCode, default_registry
from xtr_console.bundle import debug_commands
from xtr_console.command.commands_declared_on import commands_declared_on

if TYPE_CHECKING:
    from xtr_dependency_injection import KernelInterface


def test_the_debug_commands_are_not_in_the_process_wide_registry() -> None:
    names = [command.name for command in default_registry().commands()]

    assert not [name for name in names if name.startswith("debug:")]


def test_the_debug_commands_are_still_declared_on_their_classes() -> None:
    commands = (
        debug_commands.DebugBundlesCommand,
        debug_commands.DebugConfigCommand,
        debug_commands.DebugContainerCommand,
    )

    names = [entry.name for command in commands for entry in commands_declared_on(command)]

    assert names == ["debug:bundles", "debug:config", "debug:container"]


@final
class _Kernel:
    """Only the report the debug commands read."""

    def __init__(self, report: KernelReport) -> None:
        self.report: KernelReport = report


@pytest.mark.anyio
async def test_debug_config_prints_values_literally() -> None:
    # A value holding brackets — a pattern, a type — must not be read as markup.
    value = {"pattern": "[a-z]", "kind": "list[int]"}
    report = KernelReport(configs=(ConfigReport("[shop]", value, ("default",)),))
    output = StringIO()
    io = ConsoleStyle(output, StringIO(), width=400, decorated=False)
    kernel = cast("KernelInterface", cast("object", _Kernel(report)))

    code = await debug_commands.DebugConfigCommand()(io, kernel)

    assert code == ExitCode.SUCCESS
    assert "[shop]" in output.getvalue()
    assert repr(value) in output.getvalue()


async def _debug_bundles(monkeypatch: pytest.MonkeyPatch, report: KernelReport) -> str:
    """Run ``debug:bundles`` on ``report``, with nothing advertised, and return what it printed."""
    monkeypatch.setattr(debug_commands, "advertised_bundles", lambda: AdvertisedBundles((), ()))
    output = StringIO()
    io = ConsoleStyle(output, StringIO(), width=400, decorated=False)
    kernel = cast("KernelInterface", cast("object", _Kernel(report)))

    assert await debug_commands.DebugBundlesCommand()(io, kernel) == ExitCode.SUCCESS
    return output.getvalue()


@pytest.mark.anyio
async def test_debug_bundles_lists_every_module_set_aside(monkeypatch: pytest.MonkeyPatch) -> None:
    set_aside = (
        SetAsideReport("shop.fixtures.users", ("acme_faker", "xtr_orm_fixtures"), expected=True),
        SetAsideReport("shop.helpers", ("acme_faker",), through="shop.fake"),
    )
    report = KernelReport(scan=ScanReport(set_aside=set_aside))

    shown = (await _debug_bundles(monkeypatch, report)).split("Set aside", 1)[1]

    rows = [" ".join(line.replace("│", " ").split()) for line in shown.splitlines()]
    assert "shop.fixtures.users acme_faker, xtr_orm_fixtures - yes" in rows
    assert "shop.helpers acme_faker shop.fake no" in rows
    assert "Nothing they define is registered" in shown


@pytest.mark.anyio
async def test_debug_bundles_adds_no_set_aside_section_when_nothing_was(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "Set aside" not in await _debug_bundles(monkeypatch, KernelReport())
