from __future__ import annotations

import subprocess
import sys
from io import StringIO

import pytest
from rich.console import Console
from xtr_logging import LoggerFactory, LoggingConfig
from xtr_logging.config import ConsoleHandlerSpec
from xtr_logging.processor.processor_registry import ProcessorRegistry

from xtr_console import ConsoleStyle, Verbosity
from xtr_console.integration.xtr_logging import follow


def logged_at(verbosity: Verbosity, *, decorated: bool = False) -> str:
    errors = StringIO()
    style = ConsoleStyle(
        Console(file=StringIO(), color_system=None),
        Console(file=errors, width=200, color_system=None),
        verbosity=verbosity,
    )
    style.decorated = decorated
    factory = LoggerFactory(
        LoggingConfig(handlers={"console": ConsoleHandlerSpec()}), registry=ProcessorRegistry()
    )
    logger = factory.logger()

    follow(factory, style)
    for level in ("debug", "info", "notice", "warning", "error"):
        message = f"at {level}"
        logger.log(level, message)

    return errors.getvalue()


@pytest.mark.parametrize(
    ("verbosity", "lowest"),
    [
        (Verbosity.QUIET, "error"),
        (Verbosity.NORMAL, "warning"),
        (Verbosity.VERBOSE, "notice"),
        (Verbosity.VERY_VERBOSE, "info"),
        (Verbosity.DEBUG, "debug"),
    ],
)
def test_the_console_handlers_print_from_the_level_the_verbosity_maps_to(
    verbosity: Verbosity, lowest: str
) -> None:
    levels = ["debug", "info", "notice", "warning", "error"]

    logged = logged_at(verbosity)

    printed = [level for level in levels if f"at {level}" in logged]
    assert printed == levels[levels.index(lowest) :]


def test_a_silent_command_logs_nothing() -> None:
    assert logged_at(Verbosity.SILENT) == ""


@pytest.mark.parametrize(("decorated", "coloured"), [(True, True), (False, False)])
def test_the_lines_are_coloured_as_the_error_output_is(decorated: bool, coloured: bool) -> None:
    assert ("\x1b[" in logged_at(Verbosity.NORMAL, decorated=decorated)) is coloured


def test_the_core_never_imports_xtr_logging() -> None:
    code = "import sys, xtr_console; print('xtr_logging' in sys.modules)"

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "False"
