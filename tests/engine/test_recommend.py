"""v2 recommender: the rule (>= threshold of futures clear 26-week waits)."""

from __future__ import annotations

from typing import Any

from cardiac_capacity import recommend as rec
from cardiac_capacity.ward_referral import DEFAULT_PARAMS

SMALL: dict[str, Any] = {
    **DEFAULT_PARAMS,
    "total_backlog": 25,
    "weekly_refs": 2,
    "dist_legacy": 30,
}
GOAL = 14


def brute_force(threshold: float, n: int, max_beds: int, max_slots: int) -> tuple[int, int] | None:
    feasible = []
    for beds in range(1, max_beds + 1):
        for slots in range(1, max_slots + 1):
            p = {**SMALL, "total_beds": beds, "surg_per_week": slots}
            if rec.success_count(p, GOAL, n, 10_000) / n >= threshold:
                feasible.append((beds, slots))
    return min(feasible) if feasible else None


def test_matches_brute_force_on_a_small_grid() -> None:
    for threshold in (0.5, 0.9):
        r = rec.recommend(SMALL, GOAL, threshold, 40, 40, max_beds=8, max_slots=4)
        expected = brute_force(threshold, 40, 8, 4)
        assert expected is not None and r.found
        assert (r.beds, r.slots) == expected


def test_threshold_is_respected_and_monotone() -> None:
    low = rec.recommend(SMALL, GOAL, 0.5, 40, 60, max_beds=10, max_slots=5)
    high = rec.recommend(SMALL, GOAL, 0.95, 40, 60, max_beds=10, max_slots=5)
    assert low.found and low.p_select >= 0.5
    assert high.found and high.p_select >= 0.95
    assert (high.beds or 0) >= (low.beds or 0)


def test_validation_uses_fresh_seeds_and_reports_a_ci() -> None:
    r = rec.recommend(SMALL, GOAL, 0.9, 40, 100, max_beds=10, max_slots=5)
    lo, hi = r.ci_validate
    assert r.found and 0 <= lo <= r.p_validate <= hi <= 1
    cfg = {**SMALL, "total_beds": r.beds, "surg_per_week": r.slots}
    assert r.p_validate == rec.success_count(cfg, GOAL, 100, 50_000) / 100


def test_not_found_when_demand_is_impossible() -> None:
    hard = {**SMALL, "weekly_refs": 15}
    r = rec.recommend(hard, GOAL, 0.9, 20, 20, max_beds=3, max_slots=3)
    assert not r.found and r.beds is None


def test_ci_rule_is_at_least_as_strict() -> None:
    a = rec.recommend(SMALL, GOAL, 0.9, 60, 20, max_beds=12, max_slots=5)
    b = rec.recommend(SMALL, GOAL, 0.9, 60, 20, max_beds=12, max_slots=5, require_ci=True)
    assert a.found
    assert (not b.found) or (b.beds or 0) >= (a.beds or 0)
