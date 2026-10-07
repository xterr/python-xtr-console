"""The declarations an application writes on its own functions, classes and parameters.

``as_command`` declares a command; ``Argument`` and ``Option`` say what one of its
parameters looks like on the command line, attached with ``Annotated``::

    async def export(
        io: ConsoleStyle,
        path: Annotated[Path, Argument(help="Where to write.")],
        *,
        force: Annotated[bool, Option(alias="-f")] = False,
    ) -> int: ...

Whether a parameter is an argument or an option is still its place in the signature —
before a bare ``*`` or after it. The marker only fine-tunes it, and must match that place.
"""

from __future__ import annotations

from .argument import Argument
from .as_command import as_command
from .option import Option

__all__ = ["Argument", "Option", "as_command"]
