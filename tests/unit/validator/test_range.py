from __future__ import annotations

import pytest

from xtr_console import Range


@pytest.mark.parametrize(
    ("bounds", "value"),
    [
        (Range(gt=0), 1),
        (Range(gte=1), 1),
        (Range(lt=5), 4.5),
        (Range(lte=5), 5),
        (Range(gte=1, lte=5), 3),
    ],
)
def test_a_value_within_the_bounds_passes(bounds: Range, value: float) -> None:
    bounds(value)


@pytest.mark.parametrize(
    ("bounds", "value", "complaint"),
    [
        (Range(gt=0), 0, "Must be > 0."),
        (Range(gte=1), 0, "Must be >= 1."),
        (Range(lt=5), 5, "Must be < 5."),
        (Range(lte=5), 6, "Must be <= 5."),
    ],
)
def test_a_value_outside_the_bounds_is_refused(bounds: Range, value: float, complaint: str) -> None:
    with pytest.raises(ValueError, match=complaint):
        bounds(value)


def test_a_range_without_bounds_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one"):
        _ = Range()
