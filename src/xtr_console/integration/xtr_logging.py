"""xtr-logging's console handlers following the command they log for.

A container providing both the application and a ``LoggerFactory`` wires
this on its own — see :mod:`xtr_console.bundle`. Without one::

    from xtr_console.integration.xtr_logging import follow

    application.on_configure(lambda io: follow(factory, io))
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from xtr_logging import Verbosity

from xtr_console.style.decoration import is_decorated

if TYPE_CHECKING:
    from xtr_logging import LoggerFactory

    from xtr_console.style import ConsoleStyle

__all__ = ["follow"]


def follow(factory: LoggerFactory, style: ConsoleStyle) -> None:
    """Make every console handler of ``factory`` follow the command ``style`` writes for.

    The handlers print at the level the
    verbosity maps to — nothing for ``--silent``, errors for ``-q``, warnings
    by default, then notices, info and debug for ``-v`` to ``-vvv`` — on the
    command's error output, coloured only when that output is.
    """
    console = style.error_console
    factory.set_verbosity(Verbosity(style.verbosity.value))
    # Standard error is left to the handler to look up as it writes, so a
    # live progress bar that redirects it still gets the log lines above it.
    factory.set_console_stream(
        None if console.file is sys.stderr else console.file, colors=is_decorated(console)
    )
