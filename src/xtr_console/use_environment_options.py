"""Reading ``--env`` and ``--no-debug`` off the command line, before the kernel is built."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Final

from .global_options import GlobalOptions

if TYPE_CHECKING:
    from collections.abc import MutableMapping, Sequence

__all__ = ["use_environment_options"]

_ENV_VARIABLE: Final = "APP_ENV"
_DEBUG_VARIABLE: Final = "APP_DEBUG"


def use_environment_options(
    argv: Sequence[str] | None = None, environ: MutableMapping[str, str] | None = None
) -> None:
    """Set ``APP_ENV`` and ``APP_DEBUG`` from ``-e``/``--env`` and ``--no-debug``.

    The environment decides which bundles run and which configuration loads,
    so it must be known before the kernel is built — before the console, and
    its parsing of the command line, exist. Call this first in a console entry
    point, before the environment files are loaded: an environment variable
    already set wins over the files, so they then load for the environment
    asked for::

        def main() -> None:
            use_environment_options()
            load_environment()
            raise SystemExit(kernel.run(console))

    The options stay on the command line; the application takes them off
    before the command sees it.

    Args:
        argv: The command line; ``sys.argv[1:]`` when left out.
        environ: Where to set the variables; ``os.environ`` when left out.
    """
    options = GlobalOptions.parse(
        list(argv) if argv is not None else sys.argv[1:], environment_options=True
    )
    target = environ if environ is not None else os.environ
    if options.environment is not None:
        target[_ENV_VARIABLE] = options.environment
    if options.debug is False:
        target[_DEBUG_VARIABLE] = "0"
