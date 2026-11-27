from __future__ import annotations

import pytest

from xtr_console import ConsoleStyle, Verbosity
from xtr_console.global_options import GlobalOptions, is_global_flag


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
        (["--verbose=4"], Verbosity.DEBUG),
        (["--verbose=9"], Verbosity.DEBUG),
        (["--verbose", "1"], Verbosity.VERBOSE),
        (["--verbose", "2"], Verbosity.VERY_VERBOSE),
        (["--verbose", "3"], Verbosity.DEBUG),
        (["--verbose", "4"], Verbosity.DEBUG),
        (["-v", "-vvv", "-vv"], Verbosity.DEBUG),
        (["-q"], Verbosity.QUIET),
        (["--quiet"], Verbosity.QUIET),
        (["--silent"], Verbosity.SILENT),
    ],
)
def test_it_reads_the_verbosity_asked_for(tokens: list[str], expected: Verbosity | None) -> None:
    assert GlobalOptions.parse(tokens).verbosity is expected


def test_a_detached_verbosity_value_is_read_off_with_its_flag() -> None:
    options = GlobalOptions.parse(["--verbose", "2", "inspect"])

    assert (options.verbosity, options.remaining, options.taken) == (
        Verbosity.VERY_VERBOSE,
        ("inspect",),
        ("--verbose", "2"),
    )


@pytest.mark.parametrize("token", ["inspect", "-1", "0", "2.5", "--"])
def test_a_token_that_is_no_verbosity_value_stays_the_commands(token: str) -> None:
    options = GlobalOptions.parse(["--verbose", token])

    assert (options.verbosity, options.remaining) == (Verbosity.VERBOSE, (token,))


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


@pytest.mark.parametrize("token", ["--verbose=0", "--verbose=x", "-vx", "--verbose2", "-qq"])
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


@pytest.mark.parametrize(
    "name",
    [
        "--silent",
        "-q",
        "--quiet",
        "-n",
        "--no-interaction",
        "--ansi",
        "--no-ansi",
        "-v",
        "-vv",
        "-vvv",
        "-vvvv",
        "--verbose",
        "--verbose=2",
        "--verbose=9",
        "-e",
        "--env",
        "--env=prod",
        "--no-debug",
    ],
)
def test_every_flag_the_command_line_takes_is_a_global_flag(name: str) -> None:
    assert is_global_flag(name)


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["-e", "prod", "about"], "prod"),
        (["about", "--env", "prod"], "prod"),
        (["--env=prod", "about"], "prod"),
        (["-e", "test", "--env=prod", "about"], "prod"),
        (["about"], None),
    ],
)
def test_it_reads_the_environment_asked_for(tokens: list[str], expected: str | None) -> None:
    options = GlobalOptions.parse(tokens, environment_options=True)

    assert (options.environment, options.remaining) == (expected, ("about",))


def test_it_reads_debug_switched_off() -> None:
    options = GlobalOptions.parse(["about", "--no-debug"], environment_options=True)

    assert (options.debug, options.remaining) == (False, ("about",))


@pytest.mark.parametrize(
    "tokens", [["about", "--env"], ["about", "--env="], ["about", "-e", "--", "x"]]
)
def test_an_environment_option_without_a_value_is_left_to_the_command_line(
    tokens: list[str],
) -> None:
    options = GlobalOptions.parse(tokens, environment_options=True)

    assert (options.environment, options.remaining) == (None, tuple(tokens))


def test_the_environment_options_are_left_alone_unless_asked_for() -> None:
    tokens = ["about", "-e", "prod", "--no-debug"]

    options = GlobalOptions.parse(tokens)

    assert (options.environment, options.debug, options.remaining) == (None, None, tuple(tokens))


@pytest.mark.parametrize("name", ["-x", "--verbosity", "-vx", "--quietly", "--verbose=0"])
def test_a_flag_the_command_line_leaves_alone_is_not_a_global_flag(name: str) -> None:
    assert not is_global_flag(name)
