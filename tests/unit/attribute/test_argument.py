from __future__ import annotations

from xtr_console import Argument


def test_an_argument_sets_nothing_by_default() -> None:
    argument = Argument()

    assert (argument.name, argument.help, argument.env_var, argument.validator) == (
        None,
        None,
        None,
        None,
    )
