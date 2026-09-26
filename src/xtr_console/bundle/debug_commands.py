"""``debug:bundles``, ``debug:config`` and ``debug:container`` — the kernel's report."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import (  # noqa: TC002 — the engine reads the annotations at runtime.
    Injected,
    KernelInterface,
    ServiceKey,
)

from xtr_console import ConsoleStyle, ExitCode, as_command

__all__ = ["DebugBundlesCommand", "DebugConfigCommand", "DebugContainerCommand"]


@as_command("debug:bundles")
@final
class DebugBundlesCommand:
    """List every bundle the kernel considered and what it decided about it."""

    async def __call__(self, io: ConsoleStyle, kernel: Injected[KernelInterface]) -> int:
        """Print the ``bundles`` section of the kernel's report."""
        io.console.print(kernel.report.render("bundles"))
        return ExitCode.SUCCESS


@as_command("debug:config")
@final
class DebugConfigCommand:
    """Show the resolved configuration of every bundle, or of one when named."""

    async def __call__(
        self, io: ConsoleStyle, kernel: Injected[KernelInterface], bundle: str | None = None
    ) -> int:
        """Print the ``configs`` section, filtered by ``bundle`` when given."""
        configs = kernel.report.configs
        if bundle is not None:
            configs = tuple(config for config in configs if config.bundle == bundle)
            if not configs:
                io.error(f"No bundle named {bundle!r}")
                return ExitCode.INVALID
        for config in configs:
            io.section(config.bundle)
            io.text(" -> ".join(config.steps))
            io.text(repr(config.value))
            io.newline()
        return ExitCode.SUCCESS


@as_command("debug:container")
@final
class DebugContainerCommand:
    """List every compiled definition; ``--tag`` filters by tag name."""

    async def __call__(
        self,
        io: ConsoleStyle,
        kernel: Injected[KernelInterface],
        *,
        tag: str | None = None,
    ) -> int:
        """Print the ``definitions`` section, filtered by ``tag`` when given."""
        if tag is None:
            io.console.print(kernel.report.render("definitions"))
            return ExitCode.SUCCESS
        matches = tuple(
            definition for definition in kernel.report.definitions if tag in definition.tags
        )
        if not matches:
            io.text(f"No definition tagged {tag!r}")
            return ExitCode.SUCCESS
        rows = tuple(
            (
                _service_name(definition.key),
                definition.provider_qualname,
                definition.kind,
                definition.lifetime,
            )
            for definition in matches
        )
        io.table(("Service", "Provider", "Kind", "Lifetime"), rows)
        return ExitCode.SUCCESS


def _service_name(key: ServiceKey) -> str:
    """Render a service key readably: ``module.Class`` or ``module.Class['qualifier']``."""
    service, qualifier = key
    name = service.__qualname__
    return name if qualifier is None else f"{name}[{qualifier!r}]"
