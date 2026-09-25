from __future__ import annotations

import pytest

from xtr_console import Verbosity


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("-2", Verbosity.SILENT),
        ("-1", Verbosity.QUIET),
        ("0", Verbosity.NORMAL),
        ("1", Verbosity.VERBOSE),
        ("2", Verbosity.VERY_VERBOSE),
        ("3", Verbosity.DEBUG),
    ],
)
def test_a_shell_level_names_a_verbosity(value: str, expected: Verbosity) -> None:
    assert Verbosity.from_shell(value) is expected


@pytest.mark.parametrize("value", [None, "", "loud", "4", "-3"])
def test_anything_else_is_normal(value: str | None) -> None:
    assert Verbosity.from_shell(value) is Verbosity.NORMAL


@pytest.mark.parametrize("verbosity", list(Verbosity))
def test_a_verbosity_round_trips_through_its_shell_level(verbosity: Verbosity) -> None:
    assert Verbosity.from_shell(str(verbosity.shell_level)) is verbosity


def test_verbosities_are_ordered_from_silent_to_debug() -> None:
    assert sorted(Verbosity) == [
        Verbosity.SILENT,
        Verbosity.QUIET,
        Verbosity.NORMAL,
        Verbosity.VERBOSE,
        Verbosity.VERY_VERBOSE,
        Verbosity.DEBUG,
    ]
