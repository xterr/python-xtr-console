from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING, final

import pytest
from rich.console import Console

from xtr_console import (
    Application,
    ApplicationTester,
    CommandsLocator,
    ConsoleStyle,
    ExitCode,
    InvalidDefaultError,
    as_command,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


@final
class Terminal:
    """A style writing to memory, answering questions from ``answers``."""

    def __init__(self, answers: Sequence[str] = (), *, interactive: bool = True) -> None:
        self.output = StringIO()
        self.style = ConsoleStyle(
            Console(file=self.output, width=60, color_system=None, highlight=False),
            input_stream=StringIO("".join(f"{answer}\n" for answer in answers)),
            interactive=interactive,
        )

    @property
    def lines(self) -> list[str]:
        return [line.rstrip() for line in self.output.getvalue().splitlines()]


# ─── structure ───────────────────────────────────────────────────


def test_a_title_is_underlined_to_its_length() -> None:
    terminal = Terminal()

    terminal.style.title("Import")

    assert terminal.lines[1:3] == ["Import", "======"]


def test_a_section_is_underlined_to_its_length() -> None:
    terminal = Terminal()

    terminal.style.section("Users")

    assert terminal.lines[1:3] == ["Users", "-----"]


def test_text_renders_markup() -> None:
    terminal = Terminal()

    terminal.style.text("[bold]done[/bold]")

    assert terminal.lines == ["done"]


def test_a_listing_bullets_every_item() -> None:
    terminal = Terminal()

    terminal.style.listing(["one", "two"])

    assert terminal.lines[:2] == [" * one", " * two"]


def test_newline_writes_blank_lines() -> None:
    terminal = Terminal()

    terminal.style.newline(2)

    assert terminal.lines == ["", ""]


def test_a_table_holds_its_headers_and_cells() -> None:
    terminal = Terminal()

    terminal.style.table(["Name", "Role"], [["ada", "admin"]])

    rendered = "\n".join(terminal.lines)
    assert all(word in rendered for word in ("Name", "Role", "ada", "admin"))


@pytest.mark.parametrize(
    ("write", "label"),
    [
        (ConsoleStyle.success, "[OK]"),
        (ConsoleStyle.error, "[ERROR]"),
        (ConsoleStyle.warning, "[WARNING]"),
        (ConsoleStyle.caution, "[CAUTION]"),
        (ConsoleStyle.note, "[NOTE]"),
        (ConsoleStyle.info, "[INFO]"),
    ],
)
def test_an_outcome_is_labelled(write: Callable[[ConsoleStyle, str], None], label: str) -> None:
    terminal = Terminal()

    write(terminal.style, "it happened")

    assert f"{label} it happened" in "\n".join(terminal.lines)


def test_progress_yields_every_item_in_order() -> None:
    terminal = Terminal()

    assert list(terminal.style.progress(["a", "b", "c"])) == ["a", "b", "c"]


# ─── questions ───────────────────────────────────────────────────


def test_ask_returns_the_answer() -> None:
    assert Terminal(["ada"]).style.ask("Name?") == "ada"


def test_ask_returns_the_default_for_an_empty_answer() -> None:
    assert Terminal([""]).style.ask("Name?", "ada") == "ada"


def test_ask_repeats_until_the_answer_is_a_choice() -> None:
    assert Terminal(["root", "admin"]).style.ask("Role?", choices=["user", "admin"]) == "admin"


def test_ask_hidden_returns_the_answer() -> None:
    assert Terminal(["s3cret"]).style.ask_hidden("Password?") == "s3cret"


@pytest.mark.parametrize(("answer", "expected"), [("y", True), ("n", False), ("", False)])
def test_confirm_reads_yes_or_no(answer: str, expected: bool) -> None:
    assert Terminal([answer]).style.confirm("Continue?") is expected


def test_a_style_that_is_not_interactive_answers_with_defaults() -> None:
    style = Terminal(interactive=False).style

    answers = (
        style.ask("Name?", "ada"),
        style.ask_hidden("Password?"),
        style.confirm("Go?", default=False),
    )

    assert answers == ("ada", "", False)


def test_it_writes_to_the_terminal_when_given_no_console() -> None:
    style = ConsoleStyle()

    assert (style.console.stderr, style.error_console.stderr, style.interactive) == (
        False,
        True,
        True,
    )


# ─── through a command ───────────────────────────────────────────


REPORTS = CommandsLocator()


@as_command("report", registry=REPORTS)
def report(io: ConsoleStyle) -> ExitCode:
    io.title("Monthly report")
    io.section("Users")
    io.table(["Name", "Role"], [["ada", "admin"], ["alan", "user"]])
    io.listing(["one", "two"])
    io.text("[bold]bold text[/bold]")
    for label, write in (
        ("info", io.info),
        ("note", io.note),
        ("warning", io.warning),
        ("caution", io.caution),
        ("error", io.error),
    ):
        write(f"{label} message")
    processed = sum(1 for _ in io.progress(range(3), description="Counting"))
    name = io.ask("Who is this for?", "the team")
    role = io.ask("Role?", "user", choices=["user", "admin"])
    token = io.ask_hidden("Token?")
    send = io.confirm("Send it?", default=False)
    io.success(f"processed={processed} name={name} role={role} token={token} send={send}")
    return ExitCode.SUCCESS


@pytest.fixture
def reporter() -> ApplicationTester:
    return ApplicationTester(Application("acme", commands=REPORTS))


@pytest.mark.anyio
async def test_a_command_writes_every_kind_of_output_in_order(reporter: ApplicationTester) -> None:
    _ = await reporter.execute(["report"], interactive=False)

    display = reporter.display
    expected = [
        "Monthly report",
        "==============",
        "Users",
        "-----",
        "Name",
        "alan",
        " * one",
        " * two",
        "bold text",
        "[INFO] info message",
        "[NOTE] note message",
        "[WARNING] warning message",
        "[CAUTION] caution message",
        "[ERROR] error message",
        "[OK] processed=3",
    ]
    positions = [display.find(fragment) for fragment in expected]
    assert -1 not in positions
    assert positions == sorted(positions)


@pytest.mark.anyio
async def test_a_command_reads_every_kind_of_answer(reporter: ApplicationTester) -> None:
    code = await reporter.execute(["report"], inputs=["Ops", "root", "admin", "s3cret", "y"])

    assert code == ExitCode.SUCCESS
    assert "name=Ops role=admin token=s3cret send=True" in reporter.display
    assert "Please select one of the available options" in reporter.display


@pytest.mark.anyio
async def test_a_command_run_without_interaction_gets_the_defaults(
    reporter: ApplicationTester,
) -> None:
    _ = await reporter.execute(["report"], interactive=False)

    assert "name=the team role=user token= send=False" in reporter.display


@pytest.mark.anyio
async def test_empty_answers_fall_back_to_the_defaults(reporter: ApplicationTester) -> None:
    _ = await reporter.execute(["report"], inputs=["", "", "", ""])

    assert "name=the team role=user token= send=False" in reporter.display


# ─── text that is not valid markup ───────────────────────────────


@pytest.mark.parametrize(
    ("write", "text"),
    [
        (ConsoleStyle.text, "closing [/] tag"),
        (ConsoleStyle.title, "Report [/x]"),
        (ConsoleStyle.section, "stray [/bold]"),
        (ConsoleStyle.success, "saved to [/tmp"),
    ],
)
def test_text_that_is_not_valid_markup_is_printed_as_it_is(
    write: Callable[[ConsoleStyle, str], None], text: str
) -> None:
    terminal = Terminal()

    write(terminal.style, text)

    assert text in "\n".join(terminal.lines)


def test_list_items_and_table_cells_that_are_not_valid_markup_print_as_they_are() -> None:
    terminal = Terminal()

    terminal.style.listing(["a [/b]"])
    terminal.style.table(["[/head]"], [["[/cell]"]])

    rendered = "\n".join(terminal.lines)
    assert all(text in rendered for text in ("a [/b]", "[/head]", "[/cell]"))


def test_a_question_that_is_not_valid_markup_is_still_asked() -> None:
    assert Terminal(["x"]).style.ask("Value [/]?") == "x"


# ─── when input runs out ─────────────────────────────────────────


@pytest.fixture
def closed_stdin(monkeypatch: pytest.MonkeyPatch) -> ConsoleStyle:
    """A style reading the terminal — whose input has ended, as in a CI job."""

    def ended(*_args: object, **_kwargs: object) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", ended)
    monkeypatch.setattr("getpass.getpass", ended)
    return ConsoleStyle(Console(file=StringIO(), color_system=None))


def test_ask_answers_with_its_default_when_input_has_ended(closed_stdin: ConsoleStyle) -> None:
    assert closed_stdin.ask("Name?", "ada") == "ada"


def test_confirm_answers_with_its_default_when_input_has_ended(closed_stdin: ConsoleStyle) -> None:
    assert closed_stdin.confirm("Go?", default=False) is False


def test_ask_hidden_answers_empty_when_input_has_ended(closed_stdin: ConsoleStyle) -> None:
    assert closed_stdin.ask_hidden("Token?") == ""


# ─── choices ─────────────────────────────────────────────────────


@pytest.mark.parametrize("interactive", [True, False])
def test_a_default_outside_the_choices_is_refused(interactive: bool) -> None:
    style = Terminal(["user"], interactive=interactive).style

    with pytest.raises(InvalidDefaultError) as raised:
        _ = style.ask("Role?", "root", choices=["user", "admin"])

    assert (raised.value.default, raised.value.choices) == ("root", ("user", "admin"))


def test_choices_without_a_default_are_accepted() -> None:
    assert Terminal(["admin"]).style.ask("Role?", choices=["user", "admin"]) == "admin"


def test_confirm_left_unanswered_is_a_no() -> None:
    assert Terminal([""]).style.confirm("Delete everything?") is False
