"""``debug:bundles``, ``debug:config`` and ``debug:container`` — the kernel's report."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import (
    Injected,
    KernelInterface,
    ServiceKey,
    qualified_name,
)
from xtr_dependency_injection.bundle import advertised_bundles

from xtr_console import CommandsLocator, ConsoleStyle, ExitCode, as_command, escape

__all__ = ["DebugBundlesCommand", "DebugConfigCommand", "DebugContainerCommand"]

# The bundle finds these commands on the classes themselves; this registry only
# keeps the declaration out of the process-wide one a container-less app reads.
_DEBUG_REGISTRY = CommandsLocator()


@as_command("debug:bundles", registry=_DEBUG_REGISTRY)
@final
class DebugBundlesCommand:
    """List every bundle the kernel considered, and the installed ones it did not."""

    async def __call__(self, io: ConsoleStyle, kernel: Injected[KernelInterface]) -> int:
        """Print the kernel report's ``bundles`` section, the bundles left out, what was set aside.

        A bundle an installed distribution advertises but the application
        neither lists nor has required is usually a package added and never
        activated — nothing fails, its services are simply absent.

        An advertised entry that cannot be loaded is listed too, with what it
        said: it would otherwise be missing from both lists.

        So is every application module the scan set aside, needing a package
        this installation does not have: what a listed bundle that does not
        run would have used — fixtures without their library, in production —
        or, when not expected, a dependency missing from the installation.
        """
        io.console.print(kernel.report.render("bundles"), markup=False)
        advertised = advertised_bundles()
        considered = {bundle.qualname for bundle in kernel.report.bundles}
        left_out = tuple(
            (bundle.metadata().name, qualified_name(bundle))
            for bundle in advertised.bundles
            if qualified_name(bundle) not in considered
        )
        if left_out:
            io.newline()
            io.section("Installed, not active")
            io.table(("Name", "Class"), _escaped(left_out))
            io.note("List a bundle in the application's config/bundles.py to activate it.")
        if advertised.unusable:
            io.newline()
            io.section("Advertised, could not be loaded")
            io.table(("Entry point", "Error"), _escaped(advertised.unusable))
            io.note("Install what the package's bundle needs, or drop the package.")
        set_aside = kernel.report.scan.set_aside
        if set_aside:
            io.newline()
            io.section("Set aside")
            rows = tuple(
                (
                    entry.module,
                    ", ".join(entry.missing),
                    entry.through or "-",
                    "yes" if entry.expected else "no",
                )
                for entry in set_aside
            )
            io.table(("Module", "Needs", "Through", "Expected"), _escaped(rows))
            io.note("Nothing they define is registered. Not expected: install what is missing.")
        return ExitCode.SUCCESS


@as_command("debug:config", registry=_DEBUG_REGISTRY)
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
                io.error(f"No bundle named {escape(repr(bundle))}")
                return ExitCode.INVALID
        for config in configs:
            # Names, steps and values come from the application: printed as they are.
            io.section(escape(config.bundle))
            io.text(escape(" -> ".join(config.steps)))
            io.text(escape(repr(config.value)))
            io.newline()
        return ExitCode.SUCCESS


@as_command("debug:container", registry=_DEBUG_REGISTRY)
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
            io.console.print(kernel.report.render("definitions"), markup=False)
            return ExitCode.SUCCESS
        matches = tuple(
            definition for definition in kernel.report.definitions if tag in definition.tags
        )
        if not matches:
            io.text(f"No definition tagged {escape(repr(tag))}")
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
        io.table(("Service", "Provider", "Kind", "Lifetime"), _escaped(rows))
        return ExitCode.SUCCESS


def _escaped(
    rows: tuple[tuple[str, ...], ...] | list[tuple[str, str]],
) -> tuple[tuple[str, ...], ...]:
    """Return ``rows`` with every cell escaped, since table cells are markup."""
    return tuple(tuple(escape(cell) for cell in row) for row in rows)


def _service_name(key: ServiceKey) -> str:
    """Render a service key readably: ``module.Class`` or ``module.Class['qualifier']``."""
    service, qualifier = key
    name = service.__qualname__
    return name if qualifier is None else f"{name}[{qualifier!r}]"
