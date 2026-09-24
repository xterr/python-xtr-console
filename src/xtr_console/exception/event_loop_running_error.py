"""A blocking run was started from code already running on an event loop."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["EventLoopRunningError"]


class EventLoopRunningError(ConsoleError):
    """A blocking run was started from code already running on an event loop."""

    def __init__(self) -> None:
        """Explain what to call instead."""
        remedy = "await Application.run_async() there instead"
        super().__init__(
            f"Application.run() starts its own event loop, so async code cannot call it; {remedy}"
        )
