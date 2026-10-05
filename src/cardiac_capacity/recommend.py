"""v2 recommendation: smallest configuration that clears 26-week waits in enough futures.

The rule: recommend the (beds, slots) configuration for which the share of
simulated
futures with **zero** patients waiting 26+ weeks at the goal week is at least ``threshold`` (default
0.90). Among feasible configurations: fewest beds, then fewest slots. For each slots value the
smallest
feasible beds is found by bisection, which assumes the success probability does not fall as beds
rise
(true for the model up to noise; with shared seeds the noise is small, and the tests check the
answer
against brute force on a small grid). Selection and validation use **disjoint seeds**, so the
reported
out-of-sample success rate is not inflated by picking the configuration on the same runs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cardiac_capacity import ward_referral_v2 as v2
from cardiac_capacity.stats import wilson_interval

DEFAULT_THRESHOLD = 0.90


@dataclass(frozen=True)
class Recommendation:
    found: bool
    slots: int | None
    beds: int | None
    threshold: float
    n_select: int
    p_select: float
    n_validate: int
    p_validate: float
    ci_validate: tuple[float, float]
    boundary: bool  # answer sits on the edge of the search box
    evaluations: int


def success_count(
    params: Mapping[str, Any],
    goal_week: int,
    n: int,
    seed0: int,
    current_ward: Sequence[Mapping[str, Any]] = (),
    start_mode: str = "today",
    warmup_weeks: int = 52,
) -> int:
    """Replications (of ``n``, seeds ``seed0..``) with zero 26+ week waits at the goal week."""
    return sum(
        v2.breaches_at(params, goal_week, seed0 + i, current_ward, start_mode, warmup_weeks) == 0
        for i in range(n)
    )


def recommend(
    params: Mapping[str, Any],
    goal_week: int,
    threshold: float = DEFAULT_THRESHOLD,
    n_select: int = 100,
    n_validate: int = 200,
    seed_select: int = 10_000,
    seed_validate: int = 50_000,
    max_beds: int = 24,
    max_slots: int = 12,
    current_ward: Sequence[Mapping[str, Any]] = (),
    start_mode: str = "today",
    warmup_weeks: int = 52,
    require_ci: bool = False,
) -> Recommendation:
    """Search beds 1..max_beds x slots 1..max_slots. ``require_ci`` demands that the Wilson lower
    bound (not just the point estimate) meets the threshold."""
    if not 0 < threshold < 1:
        raise ValueError("threshold must be between 0 and 1")
    cache: dict[tuple[int, int], tuple[bool, int]] = {}
    evals = 0

    def score(k: int) -> float:
        return wilson_interval(k, n_select)[0] if require_ci else k / n_select

    def ok(slots: int, beds: int) -> bool:
        """Does the configuration meet the threshold? Stops early once it cannot."""
        nonlocal evals
        key = (slots, beds)
        if key not in cache:
            evals += 1
            cfg = {**params, "surg_per_week": slots, "total_beds": beds}
            k = 0
            for i in range(n_select):
                if score(k + n_select - i) < threshold:  # even all-success from here fails
                    break
                k += (
                    v2.breaches_at(
                        cfg, goal_week, seed_select + i, current_ward, start_mode, warmup_weeks
                    )
                    == 0
                )
            cache[key] = (score(k) >= threshold, k)
        return cache[key][0]

    best: tuple[int, int] | None = None  # (beds, slots)
    for slots in range(1, max_slots + 1):
        top = best[0] - 1 if best else max_beds
        if top < 1 or not ok(slots, top):
            continue
        lo, hi = 1, top  # hi is feasible
        while lo < hi:
            mid = (lo + hi) // 2
            if ok(slots, mid):
                hi = mid
            else:
                lo = mid + 1
        best = (hi, slots)

    if best is None:
        return Recommendation(
            False, None, None, threshold, n_select, 0.0, 0, 0.0, (0.0, 0.0), False, evals
        )
    beds, slots = best
    selected = cache[(slots, beds)][1]
    cfg = {**params, "surg_per_week": slots, "total_beds": beds}
    validated = success_count(
        cfg, goal_week, n_validate, seed_validate, current_ward, start_mode, warmup_weeks
    )
    return Recommendation(
        True,
        slots,
        beds,
        threshold,
        n_select,
        selected / n_select,
        n_validate,
        validated / n_validate,
        wilson_interval(validated, n_validate),
        beds == max_beds or slots == max_slots,
        evals,
    )
