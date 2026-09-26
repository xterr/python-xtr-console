from __future__ import annotations

import pytest

from xtr_console import (
    Application,
    ApplicationTester,
    CommandsLocator,
    ConsoleStyle,
    as_command,
    escape,
)


def test_a_bracketed_word_is_escaped() -> None:
    assert escape("list[int]") == r"list\[int]"


def test_text_without_markup_is_unchanged() -> None:
    assert escape("plain text") == "plain text"


@pytest.mark.anyio
async def test_escaped_text_prints_as_written() -> None:
    commands = CommandsLocator()

    @as_command("show", registry=commands)
    def show(io: ConsoleStyle) -> int:
        io.text(escape("[bold]not bold[/bold] list[int]"))
        return 0

    tester = ApplicationTester(Application("acme", commands=commands))
    _ = await tester.execute(["show"])

    assert "[bold]not bold[/bold] list[int]" in tester.display
