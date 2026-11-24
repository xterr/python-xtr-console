"""``about``: the project at a glance, called directly and through a booted kernel."""

from __future__ import annotations

import locale
import sys
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, cast, final

import pytest
import xtr_dependency_injection
from xtr_clock import MockClock
from xtr_dependency_injection import Kernel, qualified_name

from tests.fixtures import app_one
from xtr_console import Application, ApplicationTester, ConsoleStyle, ExitCode, default_registry
from xtr_console.bundle import about_command
from xtr_console.command.commands_declared_on import commands_declared_on

if TYPE_CHECKING:
    from xtr_dependency_injection import KernelInterface
    from xtr_service_contracts import ContainerInterface

_FROZEN = MockClock("2026-11-24 14:15:40", "Europe/Bucharest")


@final
class _Kernel:
    """Only the identity the about command reads."""

    def __init__(self, project_dir: Path) -> None:
        self.environment = "test"
        self.debug = True
        self.project_dir = project_dir


async def _run(project_dir: Path, cache_dir: Path | None = None) -> tuple[int, str]:
    """Run the command directly against ``project_dir`` and capture what it prints."""
    output = StringIO()
    io = ConsoleStyle(output, StringIO(), width=400, decorated=False)
    kernel = cast("KernelInterface", cast("object", _Kernel(project_dir)))
    cache = cache_dir if cache_dir is not None else project_dir / "var" / "cache" / "test"
    code = await about_command.AboutCommand(_FROZEN)(
        io,
        kernel,
        str(cache),
        str(cache),
        str(project_dir / "var" / "share"),
        str(project_dir / "var" / "log"),
    )
    return code, output.getvalue()


def _no_locale(*_args: object) -> tuple[None, None]:
    """Stand in for ``locale.getlocale``, reporting no locale at all."""
    return None, None


def _lines(display: str) -> list[str]:
    """The rendered rows with their borders stripped, as the eye reads them."""
    return [" ".join(line.replace("│", " ").split()) for line in display.splitlines()]


def test_the_about_command_is_not_in_the_process_wide_registry() -> None:
    names = [command.name for command in default_registry().commands()]

    assert "about" not in names


def test_the_about_command_is_still_declared_on_its_class() -> None:
    names = [entry.name for entry in commands_declared_on(about_command.AboutCommand)]

    assert names == ["about"]


@pytest.mark.anyio
async def test_it_reports_the_project_at_a_glance(tmp_path: Path) -> None:
    cache = tmp_path / "var" / "cache" / "test"
    cache.mkdir(parents=True)
    _ = (cache / "routes.json").write_bytes(b"x" * 17)
    (tmp_path / "var" / "share").mkdir(parents=True)

    code, display = await _run(tmp_path)

    assert code == ExitCode.SUCCESS
    rows = _lines(display)
    assert "xtr" in rows
    assert "Kernel" in rows
    assert "Python" in rows
    assert f"Version {xtr_dependency_injection.__version__}" in rows
    assert f"Type {qualified_name(Kernel)}" in rows
    assert "Environment test" in rows
    assert "Debug true" in rows
    assert "Cache directory ./var/cache/test (17 B)" in rows
    assert "Build directory ./var/cache/test (17 B)" in rows
    assert "Share directory ./var/share (0 B)" in rows
    assert "Log directory ./var/log (n/a)" in rows
    assert any(row.startswith("Version 3.14") for row in rows)
    assert "Architecture 64 bits" in rows
    assert any(row.startswith("Locale ") for row in rows)
    assert "Timezone EET (2026-11-24T14:15:40+02:00)" in rows


@pytest.mark.anyio
async def test_known_byte_counts_render_their_exact_sizes(tmp_path: Path) -> None:
    cache = tmp_path / "var" / "cache" / "test"
    cache.mkdir(parents=True)
    _ = (cache / "one.bin").write_bytes(b"x" * 1024)
    share = tmp_path / "var" / "share"
    share.mkdir(parents=True)
    with (share / "big.bin").open("wb") as stream:
        _ = stream.truncate(2 * 1024**2 + 512 * 1024)

    code, display = await _run(tmp_path)

    assert code == ExitCode.SUCCESS
    rows = _lines(display)
    assert "Cache directory ./var/cache/test (1 KiB)" in rows
    assert "Share directory ./var/share (2.5 MiB)" in rows


@pytest.mark.anyio
async def test_a_file_path_reports_its_own_size(tmp_path: Path) -> None:
    cache = tmp_path / "cache-file"
    _ = cache.write_bytes(b"x" * 17)

    code, display = await _run(tmp_path, cache_dir=cache)

    assert code == ExitCode.SUCCESS
    assert "Cache directory ./cache-file (17 B)" in _lines(display)


@pytest.mark.skipif(sys.platform == "win32", reason="chmod permissions do not apply on Windows")
@pytest.mark.anyio
async def test_an_unreadable_file_is_skipped_without_failing(tmp_path: Path) -> None:
    cache = tmp_path / "var" / "cache" / "test"
    cache.mkdir(parents=True)
    _ = (cache / "routes.json").write_bytes(b"x" * 17)
    unreadable = cache / "blocked.bin"
    _ = unreadable.write_bytes(b"y" * 100)
    unreadable.chmod(0o222)
    # POSIX stat() ignores the file's own permissions, so the size is not pinned
    # here; the skip itself is pinned by the unreadable-entry helper test below.
    code, display = await _run(tmp_path)

    assert code == ExitCode.SUCCESS
    assert any(row.startswith("Cache directory ./var/cache/test (") for row in _lines(display))


@pytest.mark.anyio
async def test_the_locale_falls_back_to_na_when_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(locale, "getlocale", _no_locale)
    monkeypatch.delenv("LANG", raising=False)

    code, display = await _run(tmp_path)

    assert code == ExitCode.SUCCESS
    assert "Locale n/a" in _lines(display)


@pytest.mark.anyio
async def test_a_path_with_markup_characters_renders_literally(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    cache = tmp_path / "di[r]" / "cache"
    cache.mkdir(parents=True)

    code, display = await _run(project, cache_dir=cache)

    assert code == ExitCode.SUCCESS
    assert "di[r]" in display


@pytest.mark.skipif(sys.platform == "win32", reason="creating a symlink needs privilege on Windows")
def test_directory_size_skips_an_entry_that_cannot_be_read(tmp_path: Path) -> None:
    _ = (tmp_path / "real.txt").write_bytes(b"x" * 17)
    (tmp_path / "broken.txt").symlink_to(tmp_path / "nonexistent")

    # The skip is pinned on the helper itself, private to the command module.
    assert about_command._directory_size(tmp_path) == 17  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("size", "formatted"),
    [
        (None, "n/a"),
        (0, "0 B"),
        (17, "17 B"),
        (1023, "1023 B"),
        (1024, "1 KiB"),
        (1024**2 - 1, "1023 KiB"),
        (1024**2, "1.0 MiB"),
        (2 * 1024**2 + 512 * 1024, "2.5 MiB"),
        (1024**3, "1.0 GiB"),
        (3 * 1024**3 + 256 * 1024**2, "3.2 GiB"),
    ],
)
def test_format_size(size: int | None, formatted: str) -> None:
    # Boundaries are pinned on the helper itself, private to the command module.
    shown = about_command._format_size(size)  # pyright: ignore[reportPrivateUsage]
    assert shown == formatted


def test_display_path_is_relative_inside_the_project(tmp_path: Path) -> None:
    # Pinned on the helper itself, private to the command module.
    shown = about_command._display_path(  # pyright: ignore[reportPrivateUsage]
        tmp_path / "var" / "cache", tmp_path
    )
    assert shown == "./var/cache"


def test_display_path_is_absolute_outside_the_project(tmp_path: Path) -> None:
    outside = Path("/elsewhere/cache")

    # Pinned on the helper itself, private to the command module.
    shown = about_command._display_path(  # pyright: ignore[reportPrivateUsage]
        outside, tmp_path
    )
    assert shown == str(outside)


@pytest.mark.anyio
async def test_about_runs_on_a_booted_kernel() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        tester = ApplicationTester(await container.get(Application))
        code = await tester.execute(["about"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "Environment" in tester.display
    assert "Cache directory" in tester.display
    assert "Log directory" in tester.display
    assert "Python" in tester.display
