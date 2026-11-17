"""Turning an error into text, whatever the error does."""

from __future__ import annotations

__all__ = ["safe_str"]


def safe_str(error: BaseException) -> str:
    """Return ``str(error)``, or a stand-in naming its class when ``__str__`` raises.

    Reporting a failed command must not fail itself: a second exception raised
    while describing the first would replace the report with a traceback.
    """
    try:
        return str(error)
    except Exception:  # noqa: BLE001 — whatever it raises, the failure is still reported
        kind = type(error)
        return f"[unprintable {kind.__module__}.{kind.__qualname__}]"
