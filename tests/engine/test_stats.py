from __future__ import annotations

import pytest

from cardiac_capacity.stats import mean_ci, wilson_interval


def test_wilson_known_values() -> None:
    lo, hi = wilson_interval(5, 10)
    assert (lo, hi) == pytest.approx((0.2366, 0.7634), abs=1e-3)
    lo0, hi0 = wilson_interval(0, 10)
    assert lo0 == 0.0 and hi0 == pytest.approx(0.2775, abs=1e-3)
    assert wilson_interval(10, 10)[1] == pytest.approx(1.0)


def test_wilson_bad_input() -> None:
    with pytest.raises(ValueError):
        wilson_interval(3, 2)
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_mean_ci_contains_mean() -> None:
    m, lo, hi = mean_ci([1.0, 2.0, 3.0, 4.0])
    assert lo < m < hi and m == 2.5
