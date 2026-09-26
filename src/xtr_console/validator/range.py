"""Bounding a number."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["Range"]


@final
@dataclass(frozen=True, slots=True)
class Range:
    """Refuse a number outside the given bounds; each bound is optional.

    Attributes:
        gt: The number must be greater than this.
        gte: The number must be this or greater.
        lt: The number must be less than this.
        lte: The number must be this or less.

    Raises:
        ValueError: When no bound is given.
    """

    gt: float | None = None
    gte: float | None = None
    lt: float | None = None
    lte: float | None = None

    def __post_init__(self) -> None:
        """Refuse a range that bounds nothing."""
        if (self.gt, self.gte, self.lt, self.lte) == (None, None, None, None):
            msg = "Range needs at least one of gt, gte, lt or lte"
            raise ValueError(msg)

    def __call__(self, value: float) -> None:
        """Refuse ``value`` when it falls outside the bounds.

        Raises:
            ValueError: Naming the bound ``value`` breaks.
        """
        if self.gt is not None and not value > self.gt:
            msg = f"Must be > {self.gt}."
            raise ValueError(msg)
        if self.gte is not None and not value >= self.gte:
            msg = f"Must be >= {self.gte}."
            raise ValueError(msg)
        if self.lt is not None and not value < self.lt:
            msg = f"Must be < {self.lt}."
            raise ValueError(msg)
        if self.lte is not None and not value <= self.lte:
            msg = f"Must be <= {self.lte}."
            raise ValueError(msg)
