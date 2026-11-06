"""What-if runner (station 2): same seeds, paired difference, duration ranges, refusals."""

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import whatif as wi

BLOCK = cp.Event("block_beds", 4, start_week=2, duration_weeks=12)


def test_empty_scenario_refused() -> None:
    with pytest.raises(ValueError, match="at least one event"):
        wi.run_whatif(cp.PolicyParams(), ())


def test_too_few_runs_refused() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        wi.run_whatif(cp.PolicyParams(), (BLOCK,), runs=1)


def test_baseline_matches_plain_replicate() -> None:
    r = wi.run_whatif(cp.PolicyParams(), (BLOCK,), weeks=20, runs=6)
    plain = [x.list_end for x in cp.replicate(cp.PolicyParams(), 20, 6, wi.SEED0)]
    assert r.get("list_end").baseline.mean == pytest.approx(sum(plain) / 6)


def test_same_seeds_are_repeatable() -> None:
    a = wi.run_whatif(cp.PolicyParams(), (BLOCK,), weeks=20, runs=5)
    b = wi.run_whatif(cp.PolicyParams(), (BLOCK,), weeks=20, runs=5)
    assert a == b


def test_event_outside_window_gives_zero_difference() -> None:
    late = cp.Event("block_beds", 4, start_week=100, duration_weeks=3)
    r = wi.run_whatif(cp.PolicyParams(), (late,), weeks=20, runs=5)
    for m in r.measures:
        assert m.difference.min == 0 and m.difference.max == 0
        assert m.verdict == "no clear change"


def test_blocked_beds_make_list_longer() -> None:
    heavy = cp.Event("block_beds", 6, start_week=1, duration_weeks=20)
    r = wi.run_whatif(cp.PolicyParams(), (heavy,), weeks=26, runs=10)
    m = r.get("list_end")
    assert m.difference.p50 > 0
    assert m.scenario.p5 <= m.scenario.p50 <= m.scenario.p95
    assert m.verdict == "worse"
    assert "longer" in wi.verdict_line(r)


def test_duration_range_differs_between_seeds() -> None:
    rng_ev = cp.Event("block_beds", 6, start_week=1, duration_weeks=2, duration_max_weeks=20)
    r = wi.run_whatif(cp.PolicyParams(), (rng_ev,), weeks=26, runs=12)
    fixed = wi.run_whatif(cp.PolicyParams(), (cp.Event("block_beds", 6, start_week=1, duration_weeks=2),), weeks=26, runs=12)
    assert r.get("list_end").scenario.spread > fixed.get("list_end").scenario.spread - 1e-9
    assert r.get("list_end").scenario.mean != fixed.get("list_end").scenario.mean


def test_measures_have_plain_labels_and_units() -> None:
    r = wi.run_whatif(cp.PolicyParams(), (BLOCK,), weeks=10, runs=3)
    assert all(m.label and m.unit for m in r.measures)
