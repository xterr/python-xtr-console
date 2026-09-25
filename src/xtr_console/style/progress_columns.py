"""What a progress bar shows: more the more verbose the run."""

from __future__ import annotations

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    ProgressColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from xtr_console.verbosity import Verbosity

__all__ = ["progress_columns"]


def progress_columns(verbosity: Verbosity) -> list[ProgressColumn]:
    """Return the columns: the description, bar, percentage and time left.

    ``-v`` adds the count done, ``-vv`` the time elapsed.
    """
    columns: list[ProgressColumn] = [
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ]
    if verbosity >= Verbosity.VERBOSE:
        columns.append(MofNCompleteColumn())
    if verbosity >= Verbosity.VERY_VERBOSE:
        columns.append(TimeElapsedColumn())
    columns.append(TimeRemainingColumn(elapsed_when_finished=True))
    return columns
