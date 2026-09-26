"""Keeping text from outside the program from being read as markup."""

from __future__ import annotations

from rich.markup import escape as _escape_markup

__all__ = ["escape"]


def escape(text: str) -> str:
    """Return ``text`` with anything that reads as a markup tag escaped.

    Messages, list items, table cells and questions are markup: ``"[bold]x[/bold]"`` prints
    a bold ``x``, and a bracketed word that reads as a tag — ``list[int]`` — is taken as one.
    Pass anything that comes from outside the program through this first::

        io.success(f"Saved {escape(path)}")
    """
    return _escape_markup(text)
