"""Stochastic CICU engine: determinism, bed limit, ceiling, surge bed, rates, Little's law."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity.casemix import DEFAULT_CASEMIX, CaseMix, LesionGroup, StageReentry


def test_same_seed_same_result_and_seeds_differ() -> None:
    p = cp.PolicyParams()
    assert cp.run_metrics(p, 26, 3) == cp.run_metrics(p, 26, 3)
    assert cp.run_metrics(p, 26, 3) != cp.run_metrics(p, 26, 4)


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        cp.run_metrics(cp.PolicyParams(start_mode="never"), 4, 1)
    with pytest.raises(ValueError):
        cp.run_metrics(cp.PolicyParams(beds=0), 4, 1)


def test_elective_limit_is_floor_of_target_times_beds() -> None:
    assert cp.PolicyParams(beds=10, target_occupancy=0.85).elective_limit == 8
    assert cp.PolicyParams(beds=10, target_occupancy=1.0).elective_limit == 10
    assert cp.PolicyParams(beds=1, target_occupancy=0.5).elective_limit == 1


def test_ceiling_binds_electives_and_beds_are_never_exceeded() -> None:
    # Only elective category 3 patients: occupancy can never pass floor(0.85 x 10) = 8.
    p = cp.PolicyParams(
        slots=12,
        category_distribution=(0, 0, 1, 0),
        initial_backlog=200,
        deterioration_rates=(0, 0, 0, 0),
        weekly_referrals=8,
    )
    f = cp.run_frame(p, 26, 5)
    assert f["occupancy_peak"].max() <= 8
    # Raising the ceiling to 100% lets electives fill every bed, and no further.
    f2 = cp.run_frame(replace(p, target_occupancy=1.0), 26, 5)
    assert f2["occupancy_peak"].max() == 10


def test_life_threatening_cases_go_first_whatever_the_slot_count() -> None:
    p = cp.PolicyParams(
        slots=5,
        beds=40,
        category_distribution=(0.5, 0, 0, 0.5),
        initial_backlog=40,
        deterioration_rates=(0, 0, 0, 0),
        weekly_referrals=0,
    )
    f = cp.run_frame(p, 1, 2)
    # Every category 1 patient is operated in the week; routine patients wait for the five slots.
    assert f["cat1"].iloc[1] == 0
    assert f["cat4"].iloc[1] >= f["cat4"].iloc[0] - 5


def test_life_threatening_cases_may_use_the_headroom() -> None:
    # 10 category 1 patients arrive with 8 elective beds taken: they can fill the last 2 beds.
    p = cp.PolicyParams(
        slots=5,
        category_distribution=(0.5, 0, 0, 0.5),
        initial_backlog=60,
        deterioration_rates=(0, 0, 0, 0),
        weekly_referrals=0,
    )
    f = cp.run_frame(p, 1, 12)
    assert f["occupancy_peak"].iloc[0] <= 10


def test_surge_bed_takes_only_short_stays() -> None:
    base = dict(
        slots=12,
        beds=3,
        target_occupancy=0.67,  # ceiling of 2 base beds
        category_distribution=(0, 0, 0.5, 0.5),
        initial_backlog=100,
        deterioration_rates=(0, 0, 0, 0),
        weekly_referrals=6,
    )
    off = cp.run_metrics(cp.PolicyParams(**base), 26, 4)  # type: ignore[arg-type]
    assert off.surge_days_used == 0 and off.surge_days_open == 0
    on = cp.run_metrics(cp.PolicyParams(**base, surge_beds=1), 26, 4)  # type: ignore[arg-type]
    assert on.surge_days_used > 0 and on.surge_days_open == 26 * 7
    # No stay is short enough (cap below 1 day): the surge bed stays empty.
    none = cp.run_metrics(cp.PolicyParams(**base, surge_beds=1, surge_max_los_days=0.5), 26, 4)  # type: ignore[arg-type]
    assert none.surge_days_used == 0
    assert on.admissions >= off.admissions


def test_per_category_bernoulli_rate_within_99_percent_ci() -> None:
    n, p_true = 4000, 0.07
    p = cp.PolicyParams(
        slots=0,
        category_distribution=(0, 0, 1, 0),
        initial_backlog=n,
        deterioration_rates=(0, 0, p_true, 0),
        weekly_referrals=0,
    )
    k = cp.run_metrics(p, 1, 9).det_events
    assert abs(k - n * p_true) <= 2.5758 * math.sqrt(n * p_true * (1 - p_true))


def test_long_wait_odds_ratio_applies_after_the_threshold() -> None:
    n = 6000
    base = dict(
        slots=0,
        category_distribution=(0, 0, 1, 0),
        initial_backlog=n,
        deterioration_rates=(0, 0, 0.07, 0),
        weekly_referrals=0,
        long_wait_weeks=0,
    )
    k1 = cp.run_metrics(cp.PolicyParams(**base, long_wait_or=1.0), 1, 3).det_events  # type: ignore[arg-type]
    k2 = cp.run_metrics(cp.PolicyParams(**base, long_wait_or=2.0), 1, 3).det_events  # type: ignore[arg-type]
    odds = 0.07 / 0.93 * 2
    p2 = odds / (1 + odds)
    assert abs(k1 - n * 0.07) < 2.6 * math.sqrt(n * 0.07 * 0.93)
    assert abs(k2 - n * p2) < 2.6 * math.sqrt(n * p2 * (1 - p2))


def test_littles_law_without_blocking() -> None:
    p = cp.PolicyParams(
        slots=15,
        beds=60,
        target_occupancy=1.0,
        deterioration_rates=(0, 0, 0, 0),
        start_mode="settled",
        warmup_weeks=20,
        weekly_referrals=6,
    )
    ms = cp.replicate(p, 104, 12, 70)
    days = 7 * 104
    occ_beds = float(np.mean([m.mean_occupancy * 60 for m in ms]))
    flow = float(np.mean([m.admissions / days * m.mean_stay for m in ms]))
    assert occ_beds == pytest.approx(flow, rel=0.05)


def test_settled_start_ends_with_a_small_list_when_capacity_is_ample() -> None:
    p = cp.PolicyParams(slots=10, start_mode="settled", weekly_referrals=4)
    ms = cp.replicate(p, 26, 10, 3)
    assert max(m.list_end for m in ms) < 25
    assert all(m.list_start <= 25 for m in ms)  # a settled list, not today's 60


def _mix(*groups: LesionGroup) -> CaseMix:
    return CaseMix(groups=groups)


def test_interstage_mortality_and_stage2_reentry() -> None:
    st = StageReentry("s2", (3, 6), 0.5, "test")
    g1 = LesionGroup("s1", "stage 1", 1, 1.0, 2.0, "test", stage2=st)
    g2 = LesionGroup("s2", "stage 2", 3, 0.0, 2.0, "test")
    p = cp.PolicyParams(
        casemix=_mix(g1, g2),
        slots=5,
        beds=30,
        weekly_referrals=3,
        initial_backlog=0,
        deterioration_rates=(0, 0, 0, 0),
    )
    ms = cp.replicate(p, 52, 20, 1)
    ops = sum(m.stage1_operated for m in ms)
    deaths = sum(m.interstage_deaths for m in ms)
    assert ops > 400
    assert abs(deaths / ops - 0.5) < 2.6 * math.sqrt(0.25 / ops)
    # Survivors come back as stage-2 operations: total admissions exceed stage-1 operations.
    assert sum(m.admissions for m in ms) > ops


def test_deadline_missed_is_counted_when_beds_block() -> None:
    g = LesionGroup("d", "deadline", 1, 1.0, 20.0, "test", deadline_weeks=1, emergency=True)
    p = cp.PolicyParams(
        casemix=_mix(g),
        beds=1,
        slots=5,
        weekly_referrals=3,
        initial_backlog=0,
        deterioration_rates=(0, 0, 0, 0),
    )
    m = cp.run_metrics(p, 26, 2)
    assert m.deadline_missed > 0 and m.cat1_unserved_days > 0


def test_spontaneous_resolution_removes_patients() -> None:
    g = LesionGroup("r", "resolver", 4, 1.0, 2.0, "test", resolution_weekly=0.5)
    p = cp.PolicyParams(
        casemix=_mix(g),
        slots=0,
        initial_backlog=200,
        weekly_referrals=0,
        deterioration_rates=(0, 0, 0, 0),
    )
    m = cp.run_metrics(p, 4, 6)
    assert m.resolved > 150 and m.list_end < 30


def test_default_casemix_runs_and_frame_shape() -> None:
    p = cp.PolicyParams(casemix=DEFAULT_CASEMIX)
    f = cp.run_frame(p, 12, 4)
    assert list(f["week"]) == list(range(13))
    assert {"list", "occupancy", "det_events", "cat1"} <= set(f.columns)
