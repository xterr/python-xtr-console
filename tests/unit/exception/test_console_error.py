from __future__ import annotations

import pytest

from xtr_console import (
    ApplicationAlreadyWiredError,
    CommandSignatureError,
    ConsoleError,
    DuplicateCommandError,
    EventLoopRunningError,
    InvalidCommandNameError,
    InvalidCommandResultError,
    InvalidDefaultError,
    MissingContainerError,
    UnregisteredCommandError,
)


@pytest.mark.parametrize(
    "error",
    [
        ApplicationAlreadyWiredError("acme"),
        CommandSignatureError("user:create", "reason"),
        DuplicateCommandError("uc", "user:create"),
        EventLoopRunningError(),
        InvalidCommandNameError("-x", "reason"),
        InvalidCommandResultError("user:create", "str"),
        InvalidDefaultError("Role?", "root", ("user", "admin")),
        MissingContainerError("user:create", ("session",)),
        UnregisteredCommandError("user:create"),
    ],
)
def test_every_error_is_a_console_error(error: ConsoleError) -> None:
    assert isinstance(error, ConsoleError)


def test_a_missing_container_names_every_parameter_it_would_fill() -> None:
    error = MissingContainerError("user:create", ("session", "clock"))

    assert "session, clock" in str(error)
