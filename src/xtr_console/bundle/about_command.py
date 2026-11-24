"""``about`` — the project at a glance."""

from __future__ import annotations

import asyncio
import locale
import os
import platform
import struct
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final, final

import xtr_dependency_injection
from rich import box
from rich.table import Table
from xtr_clock import ClockInterface, SystemClock
from xtr_dependency_injection import Autowire, Injected, Kernel, KernelInterface, qualified_name

from xtr_console import CommandsLocator, ConsoleStyle, ExitCode, as_command, escape

if TYPE_CHECKING:
    from xtr_clock import DatePoint

__all__ = ["AboutCommand"]

# The bundle finds this command on the class itself; this registry only
# keeps the declaration out of the process-wide one a container-less app reads.
_ABOUT_REGISTRY = CommandsLocator()

_KIB: Final = 1024

_DIRECTORY_LABELS = ("Cache directory", "Build directory", "Share directory", "Log directory")


@as_command(
    "about",
    description="Display information about the current project",
    registry=_ABOUT_REGISTRY,
)
@final
class AboutCommand:
    """Print the framework, the kernel and the runtime the project runs on."""

    __slots__ = ("_clock",)

    def __init__(self, clock: ClockInterface | None = None) -> None:
        """Read the current instant from ``clock``; the system clock when ``None``."""
        self._clock = clock if clock is not None else SystemClock()

    async def __call__(  # noqa: PLR0913, PLR0917 — each is a separate service or directory.
        self,
        io: ConsoleStyle,
        kernel: Injected[KernelInterface],
        cache_dir: Annotated[str, Autowire(param="kernel.cache_dir")],
        build_dir: Annotated[str, Autowire(param="kernel.build_dir")],
        share_dir: Annotated[str, Autowire(param="kernel.share_dir")],
        log_dir: Annotated[str, Autowire(param="kernel.log_dir")],
    ) -> int:
        """Display information about the current project.

        Args:
            io: Where the command writes.
            kernel: The kernel the project runs on.
            cache_dir: The environment's cache directory.
            build_dir: Where what is only ever read goes.
            share_dir: Where the processes of the project share files.
            log_dir: Where the project's processes write logs.
        """
        directories = (Path(cache_dir), Path(build_dir), Path(share_dir), Path(log_dir))
        # Walking a directory blocks, so all four walks share one thread.
        sizes = await asyncio.to_thread(_sizes_of, directories)

        table = Table(show_header=False, box=box.SQUARE)
        table.add_row("[bold]xtr[/bold]", "")
        table.add_row("Version", escape(xtr_dependency_injection.__version__))
        table.add_section()
        table.add_row("[bold]Kernel[/bold]", "")
        table.add_row("Type", escape(qualified_name(Kernel)))
        table.add_row("Environment", escape(kernel.environment))
        table.add_row("Debug", "true" if kernel.debug else "false")
        for label, directory, size in zip(_DIRECTORY_LABELS, directories, sizes, strict=True):
            table.add_row(label, _described(directory, size, kernel.project_dir))
        table.add_section()
        table.add_row("[bold]Python[/bold]", "")
        table.add_row("Version", escape(platform.python_version()))
        table.add_row("Architecture", f"{struct.calcsize('P') * 8} bits")
        table.add_row("Locale", escape(_locale()))
        table.add_row("Timezone", _timezone(self._clock.now()))
        io.console.print(table)
        return ExitCode.SUCCESS


def _sizes_of(directories: tuple[Path, ...]) -> tuple[int | None, ...]:
    """Measure every directory; runs off the event loop, since walking blocks."""
    return tuple(_directory_size(directory) for directory in directories)


def _directory_size(path: Path) -> int | None:
    """Total size of the files under ``path``; ``None`` when there is no such path.

    An entry that cannot be read is skipped rather than failing the report.
    """
    if path.is_file():
        return path.stat().st_size
    if not path.is_dir():
        return None
    size = 0
    for root, _directories, files in os.walk(path, followlinks=True):
        for filename in files:
            try:
                size += (Path(root) / filename).stat().st_size
            except OSError:
                continue
    return size


def _format_size(size: int | None) -> str:
    """Render ``size`` in bytes, kibibytes, mebibytes or gibibytes; ``n/a`` when unknown."""
    if size is None:
        return "n/a"
    if size < _KIB:
        return f"{size} B"
    if size < _KIB**2:
        return f"{size // _KIB} KiB"
    if size < _KIB**3:
        return f"{size / _KIB**2:.1f} MiB"
    return f"{size / _KIB**3:.1f} GiB"


def _display_path(path: Path, project_dir: Path) -> str:
    """Render ``path`` relative to the project when inside it, absolute otherwise."""
    try:
        return f"./{path.relative_to(project_dir)}"
    except ValueError:
        return str(path)


def _described(directory: Path, size: int | None, project_dir: Path) -> str:
    """The directory cell: its display path, then its size dimmed in parentheses."""
    shown = escape(_display_path(directory, project_dir))
    return f"{shown} [dim]({escape(_format_size(size))})[/dim]"


def _locale() -> str:
    """The locale's name: the C library's answer, ``LANG`` behind it, ``n/a`` past that."""
    return locale.getlocale()[0] or os.environ.get("LANG") or "n/a"


def _timezone(now: DatePoint) -> str:
    """The timezone cell: the zone's name, then the instant dimmed in parentheses."""
    name = now.tzname() or "n/a"
    return f"{escape(name)} [dim]({escape(now.isoformat(timespec='seconds'))})[/dim]"
