from __future__ import annotations

import pytest

from xtr_console import Option


@pytest.mark.parametrize(
    ("alias", "aliases"), [("-f", ("-f",)), (("-f", "-F"), ("-f", "-F")), ((), ())]
)
def test_aliases_are_a_tuple_however_given(
    alias: str | tuple[str, ...], aliases: tuple[str, ...]
) -> None:
    assert Option(alias=alias).aliases == aliases


def test_an_option_sets_nothing_by_default() -> None:
    option = Option()

    assert (option.name, option.help, option.env_var, option.negative, option.count) == (
        None,
        None,
        None,
        None,
        False,
    )
