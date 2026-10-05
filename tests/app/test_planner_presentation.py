"""Status classification and formatting: pure functions over engine outputs."""

from __future__ import annotations

import pytest

from cardiac_capacity import summarize
from cardiac_capacity_planner import presentation as p


@pytest.mark.parametrize(
    ("samples", "label", "colour"),
    [
        ([0] * 20, "Stable", p.TEAL),
        ([0] * 15 + [3] * 5, "At risk", p.AMBER),
        ([0] * 5 + [4] * 15, "Breaching", p.RED),
        ([7] * 20, "Breaching", p.RED),
    ],
)
def test_breach_status(samples: list[int], label: str, colour: str) -> None:
    s = p.breach_status(summarize(samples), 26)
    assert (s.label, s.colour) == (label, colour)
    assert "26" in s.directive


@pytest.mark.parametrize(
    ("peak", "beds", "urgent", "label"),
    [
        (9.9, 10, 0, "Within capacity"),
        (10.0, 10, 0, "Within capacity"),  # original criterion is <=
        (10.1, 10, 0, "Over CICU beds"),
        (5.0, 10, 2, "Urgent backlog"),
        (50.0, 10, 1, "Urgent backlog"),
    ],
)
def test_cicu_status(peak: float, beds: float, urgent: float, label: str) -> None:
    assert p.cicu_status(peak, beds, urgent).label == label


def test_band_text() -> None:
    assert p.band_text(summarize(range(101))) == "50 (5–95)"
    assert p.band_text(summarize([1.25]), "{:.1f}") == "1.2 (1.2–1.2)"


def test_no_brand_colour_retyped() -> None:
    from cardiac_capacity_planner import brand as tokens

    assert p.TEAL == tokens.TEAL
    assert p.INK == tokens.CANVAS
