from __future__ import annotations

import pytest

from xtr_console import SHELL_VERBOSITY


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def shell_verbosity_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # Set, then delete: monkeypatch only restores a variable it has recorded,
    # and Application.run() writes this one back for the whole process.
    monkeypatch.setenv(SHELL_VERBOSITY, "0")
    monkeypatch.delenv(SHELL_VERBOSITY)
