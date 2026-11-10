"""``cache:clear`` and ``cache:warmup``: the kernel's cache warmers and clearers, run."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, final

from xtr_dependency_injection import (
    Autowire,
    CacheWarmerAggregate,
    ChainCacheClearer,
    Injected,
    KernelInterface,
    WarmedCache,
)

from xtr_console import CommandsLocator, ConsoleStyle, ExitCode, Option, as_command, escape

__all__ = ["CacheClearCommand", "CacheWarmupCommand"]

# The bundle finds these commands on the classes themselves; this registry only
# keeps the declaration out of the process-wide one a container-less app reads.
_CACHE_REGISTRY = CommandsLocator()


@as_command("cache:clear", registry=_CACHE_REGISTRY)
@final
class CacheClearCommand:
    """Clear the cache, then warm it up again."""

    async def __call__(  # noqa: PLR0913, PLR0917 — each is a separate service, path or flag.
        self,
        io: ConsoleStyle,
        kernel: Injected[KernelInterface],
        clearer: Injected[ChainCacheClearer],
        warmer: Injected[CacheWarmerAggregate],
        warmed: Injected[WarmedCache],
        cache_dir: Annotated[str, Autowire(param="kernel.cache_dir")],
        build_dir: Annotated[str, Autowire(param="kernel.build_dir")],
        *,
        no_warmup: Annotated[bool, Option(name="--no-warmup")] = False,
        no_optional_warmers: Annotated[bool, Option(name="--no-optional-warmers")] = False,
    ) -> int:
        """Run every cache clearer, remove the cache directory, and warm the cache up again.

        Args:
            io: Where the command writes.
            kernel: The kernel whose cache is cleared.
            clearer: Every cache clearer.
            warmer: Every cache warmer.
            warmed: Records that the warmers filled the cache, so the next start skips them.
            cache_dir: The environment's cache directory.
            build_dir: Where what is only ever read goes.
            no_warmup: Leave the cache empty.
            no_optional_warmers: Skip the optional warmers.
        """
        io.text(f"Clearing the cache for the {_described(kernel)}")
        cache, build = Path(cache_dir), Path(build_dir)
        if build != cache:
            await clearer.clear(build)
        await clearer.clear(cache)
        _remove(cache, build)

        if not no_warmup:
            io.text("Warming up the cache")
            await _warm_up(warmer, warmed, cache, build, optional=not no_optional_warmers)

        io.success(f"Cache for the {_described(kernel)} was successfully cleared.")
        return ExitCode.SUCCESS


@as_command("cache:warmup", registry=_CACHE_REGISTRY)
@final
class CacheWarmupCommand:
    """Warm up the cache."""

    async def __call__(  # noqa: PLR0913, PLR0917 — each is a separate service, path or flag.
        self,
        io: ConsoleStyle,
        kernel: Injected[KernelInterface],
        warmer: Injected[CacheWarmerAggregate],
        warmed: Injected[WarmedCache],
        cache_dir: Annotated[str, Autowire(param="kernel.cache_dir")],
        build_dir: Annotated[str, Autowire(param="kernel.build_dir")],
        *,
        no_optional_warmers: Annotated[bool, Option(name="--no-optional-warmers")] = False,
    ) -> int:
        """Run every cache warmer, the optional ones too unless told not to.

        Args:
            io: Where the command writes.
            kernel: The kernel whose cache is warmed up.
            warmer: Every cache warmer.
            warmed: Records that the warmers filled the cache, so the next start skips them.
            cache_dir: The environment's cache directory.
            build_dir: Where what is only ever read goes.
            no_optional_warmers: Skip the optional warmers.
        """
        io.text(f"Warming up the cache for the {_described(kernel)}")
        await _warm_up(
            warmer, warmed, Path(cache_dir), Path(build_dir), optional=not no_optional_warmers
        )
        io.success(f"Cache for the {_described(kernel)} was successfully warmed.")
        return ExitCode.SUCCESS


async def _warm_up(
    warmer: CacheWarmerAggregate,
    warmed: WarmedCache,
    cache_dir: Path,
    build_dir: Path,
    *,
    optional: bool,
) -> None:
    """Run the warmers — the optional ones too when ``optional`` — and record the cache warm.

    Under the same lock the kernel warms under at boot, so a process starting
    meanwhile waits for this warm-up rather than running its own.
    """
    with warmed.lock():
        _create(build_dir)
        if optional:
            warmer.enable_optional_warmers()
        await warmer.warm_up(cache_dir, build_dir)
        warmed.mark_fresh()


def _create(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)


def _remove(*directories: Path) -> None:
    for directory in directories:
        if directory.exists():
            shutil.rmtree(directory)


def _described(kernel: KernelInterface) -> str:
    debug = "true" if kernel.debug else "false"
    return f'"{escape(kernel.environment)}" environment (debug={debug})'
