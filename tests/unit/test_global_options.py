from __future__ import annotations

import pytest

from xtr_console import ConsoleStyle, Verbosity
from xtr_console.global_options import GlobalOptions


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        ([], None),
        (["-v"], Verbosity.VERBOSE),
        (["-vv"], Verbosity.VERY_VERBOSE),
        (["-vvv"], Verbosity.DEBUG),
        (["-vvvv"], Verbosity.DEBUG),
        (["--verbose"], Verbosity.VERBOSE),
        (["--verbose=1"], Verbosity.VERBOSE),
        (["--verbose=2"], Verbosity.VERY_VERBOSE),
        (["--verbose=3"], Verbosity.DEBUG),
        (["-v", "-vvv", "-vv"], Verbosity.DEBUG),
        (["-q"], Verbosity.QUIET),
        (["--quiet"], Verbosity.QUIET),
        (["--silent"], Verbosity.SILENT),
    ],
)
def test_it_reads_the_verbosity_asked_for(tokens: list[str], expected: Verbosity | None) -> None:
    assert GlobalOptions.parse(tokens).verbosity is expected


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [(["-vvv", "-q"], Verbosity.QUIET), (["-q", "--silent", "-v"], Verbosity.SILENT)],
)
def test_silence_wins_over_quiet_which_wins_over_verbose(
    tokens: list[str], expected: Verbosity
) -> None:
    assert GlobalOptions.parse(tokens).verbosity is expected


def test_the_options_are_read_before_and_after_the_command() -> None:
    options = GlobalOptions.parse(["-vv", "user:create", "ada", "-n", "--admin"])

    assert (options.verbosity, options.interactive, options.remaining) == (
        Verbosity.VERY_VERBOSE,
        False,
        ("user:create", "ada", "--admin"),
    )


def test_everything_after_a_bare_double_dash_belongs_to_the_command() -> None:
    options = GlobalOptions.parse(["grep", "--", "-v", "-q"])

    assert (options.verbosity, options.remaining) == (None, ("grep", "--", "-v", "-q"))


@pytest.mark.parametrize("token", ["--verbose=4", "-vx", "--verbose2", "-qq"])
def test_a_token_that_only_looks_like_one_is_left_for_the_parser(token: str) -> None:
    assert GlobalOptions.parse([token]).remaining == (token,)


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [([], None), (["--ansi"], True), (["--no-ansi"], False), (["--no-ansi", "--ansi"], True)],
)
def test_it_reads_whether_output_is_decorated(tokens: list[str], expected: bool | None) -> None:
    assert GlobalOptions.parse(tokens).decorated is expected


@pytest.mark.parametrize(("tokens", "expected"), [([], True), (["-n"], False)])
def test_it_reads_whether_to_ask_questions(tokens: list[str], expected: bool) -> None:
    assert GlobalOptions.parse(tokens).interactive is expected


def test_applying_nothing_leaves_the_style_as_it_was() -> None:
    style = ConsoleStyle(verbosity=Verbosity.VERBOSE)

    GlobalOptions.parse([]).apply(style)

    assert (style.verbosity, style.interactive) == (Verbosity.VERBOSE, True)


@pytest.mark.parametrize("tokens", [["-q"], ["--silent"], ["-n"]])
def test_a_quiet_or_non_interactive_run_asks_no_questions(tokens: list[str]) -> None:
    style = ConsoleStyle()

    GlobalOptions.parse(tokens).apply(style)

    assert style.interactive is False


def test_applying_sets_the_verbosity_asked_for() -> None:
    style = ConsoleStyle()

    GlobalOptions.parse(["-vvv"]).apply(style)

    assert style.verbosity is Verbosity.DEBUG
