"""Refusing a value that converts but is out of bounds.

A validator is any callable taking the converted value and raising ``ValueError`` to refuse
it; :class:`Range` is the one shipped for numbers. It is never called with ``None`` — the
value of an ``X | None`` parameter left out.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Never, TypeAlias

from .range import Range

__all__ = ["Range", "Validator"]

Validator: TypeAlias = Callable[[Never], object]
"""Any one-argument callable: it receives the converted value, and raises ``ValueError``
to refuse it. What it returns is ignored."""
