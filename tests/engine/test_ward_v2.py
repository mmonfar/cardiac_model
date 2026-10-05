"""Ward v2: daily bed clock, per-patient deterioration, start modes."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest

from cardiac_capacity import WardReferralSimulator, ward_referral
from cardiac_capacity import ward_referral_v2 as v2
from cardiac_capacity.scenarios import LIVE_WARD
from cardiac_capacity.ward_referral import DEFAULT_PARAMS

ZERO_DET = {"det_2to1": 0, "det_3to2": 0, "det_4to3": 0, "det_5to4": 0}


def only_cat(cat: int, **extra: Any) -> dict[str, Any]:
    dist = {f"dist_cat{i}": (100 if i == cat else 0) for i in range(1, 6)}
    return {**DEFAULT_PARAMS, **dist, "dist_legacy": 0, **extra}


def test_deterministic_per_seed_and_seed_matters() -> None:
    a = v2.run_simulation(DEFAULT_PARAMS, [], 30, seed=7)
    b = v2.run_simulation(DEFAULT_PARAMS, [], 30, seed=7)
    c = v2.run_simulation(DEFAULT_PARAMS, [], 30, seed=8)
    assert a["Over_26_Wks"].tolist() == b["Over_26_Wks"].tolist()
    assert a["Over_26_Wks"].tolist() != c["Over_26_Wks"].tolist()


def test_bad_start_mode() -> None:
    with pytest.raises(ValueError):
        v2.run_simulation(DEFAULT_PARAMS, [], 5, seed=1, start_mode="warm")


def test_occupancy_never_exceeds_usable_beds_and_counts_are_consistent() -> None:
    p = {**DEFAULT_PARAMS, "total_beds": 7, "safety_buffer": 2, "surg_per_week": 9}
    df = v2.run_simulation(p, LIVE_WARD, 40, seed=3)
    assert df["occupancy"].iloc[0] == 3  # the ward as entered
    assert df["occupancy"].iloc[1:].max() <= 5  # 7 beds minus a buffer of 2
    assert (df["cancellations"] >= 0).all()
    assert df["week"].tolist() == list(range(40))


def test_bed_freed_on_the_discharge_day_not_weekly() -> None:
    # One bed, 5 slots, one-day stays: each day's patient leaves before the next day's theatre
    # list, so all 5 are operated. With weekly release (v1) the bed turns over once a week.
    p = {
        **only_cat(5),
        **ZERO_DET,
        "total_beds": 1,
        "surg_per_week": 5,
        "total_backlog": 100,
        "weekly_refs": 0,
        "los_cat5": 1,
        "los_scale": 0.01,
    }
    df = v2.run_simulation(p, [], 4, seed=1)
    for w in (1, 2, 3):
        assert sum(df["admissions"].iloc[w].values()) == 5
    v1 = ward_referral.run_simulation(p, [], 4, seed=1)
    assert sum(v1["admissions"].iloc[1].values()) == 1


def test_long_stay_beds_not_released_early() -> None:
    p = {
        **only_cat(5),
        **ZERO_DET,
        "total_beds": 2,
        "surg_per_week": 5,
        "total_backlog": 100,
        "weekly_refs": 0,
        "los_cat5": 20,
        "los_scale": 1.0,
    }
    df = v2.run_simulation(p, [], 3, seed=1)
    assert df["occupancy"].iloc[1] == 2  # stays of about 20 days still occupy both beds
    assert sum(df["admissions"].iloc[1].values()) == 2
    assert df["cancellations"].iloc[1] == 3  # 5 slots, 2 admitted, patients were waiting


def test_monday_occupancy_matches_analytic_expectation() -> None:
    # No deterioration, no arrivals, 5 slots (one a day), plenty of beds: the stay distribution
    # fixes occupancy at the start of each week (a Little's-law style check of the daily clock).
    p = {
        **only_cat(5),
        **ZERO_DET,
        "total_beds": 60,
        "surg_per_week": 5,
        "total_backlog": 3000,
        "weekly_refs": 0,
        "los_cat5": 3,
        "los_scale": 1.0,
    }
    g = np.random.RandomState(0).gamma(3.0, 1.0, size=400_000)
    stay = np.ceil(np.maximum(1.0, g))
    expected = sum(float(np.mean(stay > 7 * w - d)) for w in range(1, 12) for d in range(5))
    occ = np.mean(
        [
            v2.run_simulation(p, [], 30, seed=s, detail=False)["occupancy"].iloc[12:].mean()
            for s in range(100)
        ]
    )
    assert occ == pytest.approx(expected, rel=0.04)


def count_moves(p: dict[str, Any], n: int) -> int:
    q = {**p, "total_backlog": n, "weekly_refs": 0, "surg_per_week": 0}
    return int(v2.run_simulation(q, [], 2, 5)["det_events"].iloc[1])


@pytest.mark.parametrize(("cat", "key", "rate"), [(3, "det_3to2", 0.2), (5, "det_5to4", 0.02)])
def test_deterioration_follows_own_category_rate(cat: int, key: str, rate: float) -> None:
    n = 5000
    k = count_moves({**only_cat(cat), **ZERO_DET, key: rate}, n)
    sd = math.sqrt(n * rate * (1 - rate))
    assert abs(k - n * rate) < 2.576 * sd  # inside the 99 % interval


def test_other_categories_do_not_deteriorate_and_cat1_is_stable() -> None:
    assert count_moves({**only_cat(1), **ZERO_DET, "det_2to1": 0.5}, 2000) == 0
    # Only cat 3 has a rate; a cat 4 list must not move.
    assert count_moves({**only_cat(4), **ZERO_DET, "det_3to2": 0.5}, 2000) == 0


def test_legacy_patients_follow_their_own_category() -> None:
    p = {
        **DEFAULT_PARAMS,
        **ZERO_DET,
        "det_5to4": 0.2,
        "dist_legacy": 100,
        "total_backlog": 4000,
        "weekly_refs": 0,
        "surg_per_week": 0,
    }
    df = v2.run_simulation(p, [], 2, seed=2)
    # v1 never deteriorated legacy patients; v2 does, and there is no jump to category 1.
    assert abs(df["det_events"].iloc[1] - 800) < 2.576 * math.sqrt(4000 * 0.2 * 0.8)
    assert df["Cat 1"].iloc[1] == 0


def test_long_wait_rule_multiplies_the_odds() -> None:
    base = {**only_cat(3), **ZERO_DET, "det_3to2": 0.2}
    n = 6000
    k = count_moves({**base, "long_wait_weeks": 0}, n)
    expected = float(v2.odds_adjusted(np.array([0.2]), 1.49)[0])  # about 0.2714
    assert expected > 0.27
    assert abs(k - n * expected) < 2.576 * math.sqrt(n * expected * (1 - expected))
    k_off = count_moves({**base, "long_wait_weeks": 0, "long_wait_or": 1.0}, n)
    assert abs(k_off - n * 0.2) < 2.576 * math.sqrt(n * 0.2 * 0.8)


def test_settled_start_discards_warmup_and_has_a_list() -> None:
    p = {**DEFAULT_PARAMS, "surg_per_week": 0}
    df = v2.run_simulation(p, LIVE_WARD, 10, seed=4, start_mode="settled", warmup_weeks=12)
    assert df["week"].tolist() == list(range(10))
    assert df["occupancy"].iloc[0] == 0  # the entered ward is ignored in a settled start
    assert sum(int(df[f"Cat {i}"].iloc[0]) for i in range(1, 6)) > 20  # 12 weeks of referrals


def test_arrivals_are_identical_across_configurations() -> None:
    def total_arrivals(beds: int, slots: int) -> int:
        p = {**DEFAULT_PARAMS, "total_beds": beds, "surg_per_week": slots}
        df = v2.run_simulation(p, [], 20, seed=11)
        backlog = df[[f"Cat {i}" for i in range(1, 6)]].sum(axis=1).to_numpy()
        adm = np.array([sum(a.values()) for a in df["admissions"]])
        return int((backlog[1:] - backlog[:-1] + adm[1:]).sum())

    assert total_arrivals(5, 3) == total_arrivals(12, 9)


def test_simulator_switch_and_v1_default_is_pinned() -> None:
    sim1 = WardReferralSimulator()
    assert sim1.model_version == "v1"
    ref = ward_referral.run_simulation(DEFAULT_PARAMS, [], 30, 42)
    assert sim1.simulate(30, 42)["Over_26_Wks"].tolist() == ref["Over_26_Wks"].tolist()
    sim2 = WardReferralSimulator(model_version="v2", start_mode="settled", warmup_weeks=8)
    exp = v2.run_simulation(DEFAULT_PARAMS, [], 30, 42, "settled", 8)
    assert sim2.simulate(30, 42)["Over_26_Wks"].tolist() == exp["Over_26_Wks"].tolist()
    with pytest.raises(ValueError):
        WardReferralSimulator(model_version="v9").simulate(3, 1)
