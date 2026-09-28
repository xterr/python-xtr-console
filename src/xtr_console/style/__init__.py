"""How commands write to the terminal."""

from __future__ import annotations

from .console_style import ConsoleStyle
from .escape import escape

__all__ = ["ConsoleStyle", "escape"]
