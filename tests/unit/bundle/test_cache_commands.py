"""``cache:clear`` and ``cache:warmup`` run the kernel's warmers and clearers on its cache."""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    CacheClearerInterface,
    CacheWarmer,
    ContainerBuilder,
    Kernel,
    NoConfig,
    ServiceConfigurator,
    as_bundle,
)

from xtr_console import Application, ApplicationTester, ExitCode, default_registry
from xtr_console.bundle import ConsoleBundle

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

pytestmark = pytest.mark.anyio


@final
class Log:
    def __init__(self) -> None:
        self.entries: list[str] = []


@final
class RoutesWarmer(CacheWarmer):
    def __init__(self, log: Log) -> None:
        self._log = log

    @override
    async def warm_up(self, cache_dir: Path, build_dir: Path | None = None) -> None:
        self._log.entries.append("routes")
        self._write_cache_file(cache_dir / "routes.json", "{}")

    @override
    def is_optional(self) -> bool:
        return False


@final
class TemplatesWarmer(CacheWarmer):
    def __init__(self, log: Log) -> None:
        self._log = log

    @override
    async def warm_up(self, cache_dir: Path, build_dir: Path | None = None) -> None:
        self._log.entries.append("templates")

    @override
    def is_optional(self) -> bool:
        return True


@final
class RemoteClearer(CacheClearerInterface):
    def __init__(self, log: Log) -> None:
        self._log = log

    @override
    async def clear(self, cache_dir: Path) -> None:
        self._log.entries.append(f"clear {cache_dir.name}")


@as_bundle("caching")
class CachingBundle(Bundle):
    @override
    def load_extension(
        self, config: NoConfig, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        del config, builder
        _ = services.set(Log)
        _ = services.set(RoutesWarmer)
        _ = services.set(TemplatesWarmer)
        _ = services.set(RemoteClearer)


def _kernel(project_dir: Path) -> Kernel:
    """A kernel whose project is ``project_dir``, so its cache never lands in the checkout."""
    _ = (project_dir / "pyproject.toml").write_text("")
    package = ModuleType("cache_app")
    package.__file__ = str(project_dir / "cache_app" / "__init__.py")
    return Kernel(
        package,
        env="test",
        bundles={ConsoleBundle: {"all": True}, CachingBundle: {"all": True}},
        resources=(),
    )


async def _run(project_dir: Path, args: Sequence[str]) -> tuple[int, str, list[str]]:
    async with await _kernel(project_dir).boot() as booted:
        tester = ApplicationTester(await booted.container.get(Application))
        code = await tester.execute(args)
        log = await booted.container.get(Log)
    return code, tester.display, log.entries


async def _warm(project_dir: Path) -> None:
    """Boot once, so the kernel warms the cache and later runs log only their command."""
    _, _, log = await _run(project_dir, ["list"])
    assert log == ["routes"]


async def test_warmup_runs_every_warmer_into_the_cache_directory(tmp_path: Path) -> None:
    await _warm(tmp_path)

    code, display, log = await _run(tmp_path, ["cache:warmup"])

    assert code == ExitCode.SUCCESS
    assert log == ["routes", "templates"]
    assert (tmp_path / "var" / "cache" / "test" / "routes.json").read_text() == "{}"
    assert 'Cache for the "test" environment (debug=true) was successfully warmed.' in display


async def test_warmup_can_skip_the_optional_warmers(tmp_path: Path) -> None:
    await _warm(tmp_path)

    _, _, log = await _run(tmp_path, ["cache:warmup", "--no-optional-warmers"])

    assert log == ["routes"]


async def test_clear_runs_the_clearers_removes_the_directory_and_warms_it_again(
    tmp_path: Path,
) -> None:
    await _warm(tmp_path)
    cache_dir = tmp_path / "var" / "cache" / "test"
    _ = (cache_dir / "stale.json").write_text("{}")

    code, display, log = await _run(tmp_path, ["cache:clear"])

    assert code == ExitCode.SUCCESS
    assert log == ["clear test", "routes", "templates"]
    assert sorted(path.name for path in cache_dir.iterdir()) == [
        ".warmed",
        ".warmed.lock",
        "routes.json",
    ]
    assert "was successfully cleared." in display


async def test_a_start_after_the_cache_was_warmed_runs_no_warmer(tmp_path: Path) -> None:
    await _warm(tmp_path)
    _ = await _run(tmp_path, ["cache:clear"])

    _, _, log = await _run(tmp_path, ["list"])

    assert log == []


async def test_clear_without_warmup_leaves_no_cache_directory_until_the_next_start(
    tmp_path: Path,
) -> None:
    await _warm(tmp_path)
    cache_dir = tmp_path / "var" / "cache" / "test"

    _, _, log = await _run(tmp_path, ["cache:clear", "--no-warmup"])

    assert log == ["clear test"]
    assert not cache_dir.exists()
    await _warm(tmp_path)


def test_the_cache_commands_are_not_in_the_process_wide_registry() -> None:
    names = [command.name for command in default_registry().commands()]

    assert not [name for name in names if name.startswith("cache:")]
