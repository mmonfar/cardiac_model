"""The seeded Monte Carlo kernel: determinism, seeding contract, and the p5/p50/p95 summary."""

from __future__ import annotations

import math
import random

import numpy as np
import pandas as pd
import pytest

from cardiac_capacity import montecarlo
from cardiac_capacity.montecarlo import Distribution, rng, run, summarize, weekly_band


def test_rng_matches_numpy_global_seeding() -> None:
    # The parity contract: rng(s) yields exactly the stream np.random.seed(s) would.
    np.random.seed(123)
    expected = (np.random.poisson(4.0, 5), np.random.gamma(2.0, 1.0, 3), np.random.random())
    r = rng(123)
    got = (r.poisson(4.0, 5), r.gamma(2.0, 1.0, 3), r.random_sample())
    assert (got[0] == expected[0]).all()
    assert (got[1] == expected[1]).all()
    assert got[2] == expected[2]


def test_rng_is_independent_of_global_state() -> None:
    np.random.seed(1)
    a = rng(9).random_sample(3)
    np.random.seed(2)
    np.random.random(100)
    b = rng(9).random_sample(3)
    assert (a == b).all()


def test_run_passes_consecutive_seeds() -> None:
    assert run(lambda s: s, 4, seed=10) == [10, 11, 12, 13]
    assert run(lambda s: s, 3) == [0, 1, 2]


def test_run_is_deterministic() -> None:
    def draw(s: int) -> float:
        return float(rng(s).normal())

    assert run(draw, 50, seed=7) == run(draw, 50, seed=7)
    assert run(draw, 50, seed=7) != run(draw, 50, seed=8)


def test_run_accepts_stdlib_rng_models() -> None:
    # How staff_planner_app.stochastic (random.Random(seed)) could adopt the kernel later.
    def model(s: int) -> float:
        return random.Random(s).random()  # noqa: S311 - simulation, not crypto

    assert run(model, 5, seed=3) == [random.Random(3 + i).random() for i in range(5)]  # noqa: S311


def test_run_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        run(lambda s: s, 0)


def test_summarize_known_values() -> None:
    d = summarize(range(101))
    assert d == Distribution(n=101, mean=50.0, p5=5.0, p50=50.0, p95=95.0, min=0.0, max=100.0)
    assert d.spread == 90.0


def test_summarize_linear_interpolates() -> None:
    d = summarize([1.0, 2.0, 3.0, 4.0])
    assert (d.p5, d.p50, d.p95) == pytest.approx((1.15, 2.5, 3.85))


def _nearest_rank(samples: list[float], p: float) -> float:
    # staff_planner_app.stochastic.DemandDistribution.percentile, restated.
    ordered = sorted(samples)
    return ordered[min(int(math.ceil(p * len(ordered))) - 1, len(ordered) - 1)]


@pytest.mark.parametrize("seed", range(5))
def test_inverted_cdf_equals_staff_planner_nearest_rank(seed: int) -> None:
    samples = list(rng(seed).gamma(3.0, 2.0, size=37))
    d = summarize(samples, method="inverted_cdf")
    assert d.p5 == _nearest_rank(samples, 0.05)
    assert d.p50 == _nearest_rank(samples, 0.50)
    assert d.p95 == _nearest_rank(samples, 0.95)


def test_summarize_single_value_is_degenerate() -> None:
    d = summarize([3.5])
    assert d.p5 == d.p50 == d.p95 == 3.5
    assert d.spread == 0


def test_summarize_rejects_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        summarize([])


def test_weekly_band() -> None:
    runs = [pd.DataFrame({"week": [0, 1, 2], "x": [i, 10 * i, 5]}) for i in range(11)]
    band = weekly_band(runs, "x")
    assert band["week"].tolist() == [0, 1, 2]
    assert band["p50"].tolist() == [5.0, 50.0, 5.0]
    assert band["p5"].tolist() == pytest.approx([0.5, 5.0, 5.0])
    assert band["p95"].tolist() == pytest.approx([9.5, 95.0, 5.0])


def test_percentiles_constant() -> None:
    assert montecarlo.PERCENTILES == (5, 50, 95)
