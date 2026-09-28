"""The kernel's debug commands stay out of the process-wide registry."""

from __future__ import annotations

from xtr_console import default_registry
from xtr_console.bundle import debug_commands
from xtr_console.command.commands_declared_on import commands_declared_on


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
