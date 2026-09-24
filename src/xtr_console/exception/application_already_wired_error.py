"""An application was wired to a second container."""

from __future__ import annotations

from .console_error import ConsoleError

__all__ = ["ApplicationAlreadyWiredError"]


class ApplicationAlreadyWiredError(ConsoleError):
    """An application was wired to a second container."""

    application_name: str

    def __init__(self, application_name: str) -> None:
        """Record the application already wired."""
        self.application_name = application_name
        remedy = "build one application per container"
        super().__init__(
            f"Application {application_name!r} is wired to another container; {remedy}"
        )
