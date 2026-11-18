from __future__ import annotations

from io import StringIO
from typing import override

from xtr_console import ConsoleStyle
from xtr_console.style.exception_renderer import render_exception


class _UnprintableError(Exception):
    @override
    def __str__(self) -> str:
        raise ValueError("cannot say")


def _rendered(error: BaseException) -> str:
    errors = StringIO()
    style = ConsoleStyle(StringIO(), errors, width=120, decorated=False)
    render_exception(error, style)
    return errors.getvalue()


def test_the_renderer_names_an_unprintable_error_by_its_class() -> None:
    rendered = _rendered(_UnprintableError())

    assert "[ERROR]" in rendered
    assert "_UnprintableError" in rendered
    assert "Traceback" not in rendered


def test_a_printable_error_still_prints_its_message() -> None:
    assert "boom" in _rendered(RuntimeError("boom"))
