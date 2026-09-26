"""What a command's parameter says about itself on the command line: ``Argument`` and ``Option``.

Attached with ``Annotated``::

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
from .option import Option

__all__ = ["Argument", "Option"]
