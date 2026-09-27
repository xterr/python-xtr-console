"""Unit tests for :class:`xtr_console.bundle.ConsoleBundle`."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Bundle, Kernel, as_bundle, qualified_name
from xtr_dependency_injection.testing import assert_zero_config

from tests.fixtures import app_env, app_one
from xtr_console import Application, ApplicationTester, ExitCode
from xtr_console.bundle import ConsoleBundle, ConsoleConfig

if TYPE_CHECKING:
    from xtr_dependency_injection.bundle.bundle import AnyBundle
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

_DEBUG_COMMANDS = importlib.import_module("xtr_console.bundle.debug_commands")


@as_bundle("idle")
class IdleBundle(Bundle):
    """Installed, as far as a test says, and listed by no application."""


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(ConsoleBundle)


async def test_function_command_runs_with_injected_service() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["only:one"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "from app one" in tester.display


async def test_function_command_receives_a_qualified_service() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["only:one:qualified"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "good day from app one" in tester.display


async def test_class_command_is_container_built() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["only:one:cls"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "from app one" in tester.display


async def test_debug_bundles_prints_the_bundles_section() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["debug:bundles"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "console" in tester.display
    assert "Bundles" in tester.display


async def _debug_bundles(
    monkeypatch: pytest.MonkeyPatch, installed: tuple[type[AnyBundle], ...]
) -> ApplicationTester:
    """Run ``debug:bundles`` on app_one with ``installed`` as the advertised bundles."""
    monkeypatch.setattr(_DEBUG_COMMANDS, "installed_bundles", lambda: installed)
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        tester = ApplicationTester(await container.get(Application))
        assert await tester.execute(["debug:bundles"]) == ExitCode.SUCCESS
    finally:
        await booted.shutdown()
    return tester


async def test_debug_bundles_names_an_installed_bundle_the_application_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tester = await _debug_bundles(monkeypatch, (ConsoleBundle, IdleBundle))

    left_out = tester.display.split("Installed, not active", 1)[1]
    assert "idle" in left_out
    assert qualified_name(IdleBundle) in left_out
    assert qualified_name(ConsoleBundle) not in left_out
    assert "bundles.py" in left_out


async def test_debug_bundles_adds_nothing_when_every_installed_bundle_is_considered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tester = await _debug_bundles(monkeypatch, (ConsoleBundle,))

    assert "Installed, not active" not in tester.display


async def test_debug_config_prints_the_named_bundle_config() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["debug:config", "console"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "console" in tester.display


async def test_debug_container_filters_by_tag() -> None:
    kernel = Kernel(app_one.__name__, env="test")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["debug:container", "--tag", "console.command"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS


def test_console_config_defaults_are_none_and_true() -> None:
    config = ConsoleConfig()

    assert (config.name, config.version, config.description) == (None, None, None)
    assert config.catch_exceptions is True


# ─── env-filtered list ───────────────────────────────────────────


async def test_list_omits_a_dev_only_command_in_prod() -> None:
    kernel = Kernel(app_env.__name__, env="prod")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["list"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "env:always" in tester.display
    assert "env:dev-only" not in tester.display


async def test_list_includes_a_dev_only_command_in_dev() -> None:
    kernel = Kernel(app_env.__name__, env="dev")
    booted = await kernel.boot()
    try:
        container: ContainerInterface = booted.container
        app = await container.get(Application)
        tester = ApplicationTester(app)
        code = await tester.execute(["list"])
    finally:
        await booted.shutdown()

    assert code == ExitCode.SUCCESS
    assert "env:always" in tester.display
    assert "env:dev-only" in tester.display
