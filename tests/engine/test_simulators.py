"""Both modes implement one CapacitySimulator protocol; determinism of every seeded path."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cardiac_capacity import (
    CapacitySimulator,
    CicuParams,
    CicuSimulator,
    WardReferralSimulator,
    cicu,
    monte_carlo,
    ward_referral,
)
from cardiac_capacity.scenarios import LIVE_WARD, WARD_SCENARIOS
from cardiac_capacity.ward_referral import DEFAULT_PARAMS

SIMULATORS: dict[str, CapacitySimulator] = {
    "ward": WardReferralSimulator(),
    "ward_live": WardReferralSimulator(DEFAULT_PARAMS, LIVE_WARD),
    "cicu": CicuSimulator(),
    "cicu_weighted": CicuSimulator(
        6, CicuParams(scheduling_mode="weighted", rounding_method="ceil")
    ),
}


@pytest.mark.parametrize("name", SIMULATORS)
def test_implements_protocol(name: str) -> None:
    sim = SIMULATORS[name]
    assert isinstance(sim, CapacitySimulator)
    assert sim.mode in {"ward_referral", "cicu"}
    assert sim.outcome_label


@pytest.mark.parametrize("name", SIMULATORS)
def test_simulate_is_deterministic_per_seed(name: str) -> None:
    sim = SIMULATORS[name]
    a, b = sim.simulate(20, seed=11), sim.simulate(20, seed=11)
    pd.testing.assert_frame_equal(a, b)
    assert "week" in a.columns
    assert sim.outcome(a) == sim.outcome(b)


def test_ward_seeds_differ_cicu_seeds_do_not() -> None:
    ward, icu = SIMULATORS["ward"], SIMULATORS["cicu"]
    assert ward.stochastic and not icu.stochastic
    assert not ward.simulate(52, 1).equals(ward.simulate(52, 2))
    pd.testing.assert_frame_equal(icu.simulate(52, 1), icu.simulate(52, 2))


def test_wrappers_equal_functional_api() -> None:
    pd.testing.assert_frame_equal(
        WardReferralSimulator().simulate(52, 42),
        ward_referral.run_simulation(DEFAULT_PARAMS, [], 52, 42),
    )
    sim = CicuSimulator(7, CicuParams(initial_backlog=80, rounding_method="floor"))
    df, summary = cicu.run_simulation(7, 30, "floor", initial_backlog=80)
    pd.testing.assert_frame_equal(sim.simulate(30), df)
    assert sim.summary(30) == summary
    pd.testing.assert_frame_equal(
        sim.capacity_table(30), cicu.find_optimal_capacity(30, "floor", initial_backlog=80)
    )


@pytest.mark.parametrize("scenario", ["default", "tight", "roomy"])
def test_monte_carlo_is_reproducible(scenario: str) -> None:
    sim = WardReferralSimulator(WARD_SCENARIOS[scenario])
    runs_a, dist_a = monte_carlo(sim, 30, n=12, seed=5)
    runs_b, dist_b = monte_carlo(sim, 30, n=12, seed=5)
    assert dist_a == dist_b
    for a, b in zip(runs_a, runs_b, strict=True):
        pd.testing.assert_frame_equal(a, b)
    assert dist_a.p5 <= dist_a.p50 <= dist_a.p95
    assert dist_a.n == 12


def test_monte_carlo_seed0_reproduces_original_stress_test() -> None:
    # The original app's stress test was seed=i for i in range(20): monte_carlo(seed=0).
    runs, dist = monte_carlo(WardReferralSimulator(), 52, n=20, seed=0)
    finals = [int(r["Over_26_Wks"].to_numpy()[-1]) for r in runs]
    assert finals[:3] == [74, 121, 84]
    assert dist.p50 == float(np.median(finals))


def test_monte_carlo_over_deterministic_mode_is_degenerate() -> None:
    _, dist = monte_carlo(CicuSimulator(), 52, n=5)
    assert dist.p5 == dist.p50 == dist.p95 == 60.0


def test_simulation_leaves_global_numpy_state_alone() -> None:
    np.random.seed(99)
    before = np.random.get_state()[1].copy()  # type: ignore[index]
    WardReferralSimulator().simulate(10, seed=1)
    assert (np.random.get_state()[1] == before).all()  # type: ignore[index]
