"""Two kernels in one process must see disjoint command sets (ORIG acceptance 3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel

from tests.fixtures import app_one, app_two
from xtr_console import Application

if TYPE_CHECKING:
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio


async def test_two_kernels_in_one_process_have_disjoint_commands() -> None:
    kernel_one = Kernel(app_one.__name__, env="test")
    kernel_two = Kernel(app_two.__name__, env="test")

    booted_one = await kernel_one.boot()
    try:
        booted_two = await kernel_two.boot()
        try:
            container_one: ContainerInterface = booted_one.container
            container_two: ContainerInterface = booted_two.container
            app_one_instance = await container_one.get(Application)
            app_two_instance = await container_two.get(Application)

            names_one = {c.name for c in app_one_instance.commands.commands()}
            names_two = {c.name for c in app_two_instance.commands.commands()}
        finally:
            await booted_two.shutdown()
    finally:
        await booted_one.shutdown()

    assert "only:one" in names_one
    assert "only:two" not in names_one
    assert "only:two" in names_two
    assert "only:one" not in names_two
