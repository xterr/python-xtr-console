"""How help is laid out: each section's title flush left, its entries indented under it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final, override

from cyclopts.help import DefaultFormatter, TableSpec
from cyclopts.help.specs import (
    DefaultStyled,
    get_default_command_columns,
    get_default_parameter_columns,
)
from rich.padding import Padding
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from cyclopts.help import ColumnSpec, HelpEntry, HelpPanel
    from rich.console import Console, ConsoleOptions
    from rich.table import Table

__all__ = ["COMMANDS_TITLE", "OPTIONS_TITLE", "SectionFormatter"]

COMMANDS_TITLE: Final = "Available commands"
"""The section listing the commands outside any namespace."""
OPTIONS_TITLE: Final = "Options"
"""The section listing the options, the global ones included."""

_SECTIONS: Final = frozenset({COMMANDS_TITLE, OPTIONS_TITLE})
_ENTRY_INDENT: Final = 2
_NAMESPACE_INDENT: Final = 1


@final
class SectionFormatter(DefaultFormatter):
    """Lays help out as ``list`` does.

    A section's title starts the line, followed by a colon; its entries sit two
    columns in. A namespace's commands are a section of their own, titled by the
    namespace one column in, and follow the commands outside any namespace with
    no blank line between them, so the commands read as one listing.
    """

    def __init__(self) -> None:
        """Lay entries out as two columns, two spaces apart, without a header."""
        super().__init__(table_spec=TableSpec(show_header=False, box=None, padding=(0, 2, 0, 0)))

    @override
    def __call__(self, console: Console, options: ConsoleOptions, panel: HelpPanel) -> None:
        """Print ``panel``: its title, its description when it has one, then its entries."""
        if not panel.entries:
            return
        console.print(DefaultStyled(_title(panel), theme=panel.theme))
        description = cast("object", panel.description)
        if isinstance(description, Text) and description.plain:
            console.print(Padding(description, (0, 0, 0, _ENTRY_INDENT)))
        build_columns = (
            get_default_command_columns
            if panel.format == "command"
            else get_default_parameter_columns
        )
        # The spec's own signature leaves its keyword overrides untyped; none are passed.
        build_table = cast(
            "Callable[[tuple[ColumnSpec, ...], Sequence[HelpEntry]], Table]",
            (self.table_spec or TableSpec()).build,
        )
        table = build_table(build_columns(console, options, panel.entries), panel.entries)
        console.print(DefaultStyled(Padding(table, (0, 0, 0, _ENTRY_INDENT)), theme=panel.theme))
        if not _lists_commands(panel):
            console.print()


def _is_namespace(panel: HelpPanel) -> bool:
    """Tell whether ``panel`` lists the commands of one namespace.

    The global options are listed as commands too, so the format alone does not tell.
    """
    return panel.format == "command" and str(panel.title) not in _SECTIONS


def _lists_commands(panel: HelpPanel) -> bool:
    return _is_namespace(panel) or str(panel.title) == COMMANDS_TITLE


def _title(panel: HelpPanel) -> Text:
    """Return ``panel``'s title line: a namespace one column in, any other section with a colon."""
    if _is_namespace(panel):
        return Text(" " * _NAMESPACE_INDENT + str(panel.title), style="yellow")
    return Text(f"{panel.title}:", style="bold yellow")
