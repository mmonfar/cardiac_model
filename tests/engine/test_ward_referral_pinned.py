"""Characterisation tests: values produced by the v1 ward engine (numpy 2.4
RandomState stream) on synthetic parameters, pinned so v1 behaviour stays
reproducible inside v2. If one fails, v1 behaviour changed; do not re-pin
without comparing against engine.py at tag v1-final."""

from __future__ import annotations

import pytest

from cardiac_capacity import ward_referral
from cardiac_capacity.scenarios import LIVE_WARD
from cardiac_capacity.ward_referral import DEFAULT_PARAMS

DEFAULT_OVER26 = [0, 0, 1, 4, 5, 6, 6, 6, 7, 7, 8, 7, 10, 12, 13, 13, 12, 11, 16, 18, 20, 20, 23,
                  25, 29, 30, 34, 37, 39, 45, 50, 55, 57, 60, 63, 64, 67, 72, 76, 79, 78, 79, 82,
                  84, 89, 91, 91, 95, 97, 105, 108, 106]  # fmt: skip
DEFAULT_OCC_TAIL = [8] * 22 + [7] + [8] * 22  # weeks 7..51


def test_default_seed42() -> None:
    df = ward_referral.run_simulation(DEFAULT_PARAMS, [], weeks=52, seed=42)
    assert len(df) == 52
    assert df["Over_26_Wks"].tolist() == DEFAULT_OVER26
    assert df["occupancy"].tolist() == [0, 5, 8, 8, 8, 8, 8, *DEFAULT_OCC_TAIL]
    assert int(df["cancellations"].to_numpy().sum()) == 137
    assert int(df["det_events"].to_numpy().sum()) == 418
    assert [int(df[f"Cat {i}"].to_numpy()[-1]) for i in range(1, 6)] == [40, 69, 60, 40, 20]
    assert sum(sum(a.values()) for a in df["admissions"]) == 118
    last_ward = df["ward_state"].iloc[-1]
    assert sum(b["days_remaining"] for b in last_ward) == pytest.approx(132.058770617579, abs=1e-9)


def test_live_ward_seed42_only_changes_early_occupancy() -> None:
    # The live ward consumes no random draws, so the waiting list is identical to the
    # empty-ward run; only the first weeks' occupancy differs.
    df = ward_referral.run_simulation(DEFAULT_PARAMS, LIVE_WARD, weeks=52, seed=42)
    assert df["Over_26_Wks"].tolist() == DEFAULT_OVER26
    assert df["occupancy"].tolist() == [3, 6, 8, 8, 8, 8, 8, *DEFAULT_OCC_TAIL]
    assert df["ward_state"].iloc[0] == [
        {"cat": 1, "days_remaining": 14.0},
        {"cat": 2, "days_remaining": 7.0},
        {"cat": 3, "days_remaining": 3.0},
    ]


def test_tight_seed7_26_weeks() -> None:
    params = {**DEFAULT_PARAMS, "total_beds": 5, "surg_per_week": 3, "weekly_refs": 9,
              "dist_legacy": 40}  # fmt: skip
    df = ward_referral.run_simulation(params, [], weeks=26, seed=7)
    assert df["Over_26_Wks"].tolist() == [0, 0, 1, 1, 3, 6, 8, 8, 8, 10, 9, 14, 15, 17, 18, 20,
                                          21, 21, 24, 27, 30, 30, 29, 31, 33, 40]  # fmt: skip
    assert df["occupancy"].tolist() == [0, 3] + [5] * 15 + [4] + [5] * 8
    assert int(df["cancellations"].to_numpy().sum()) == 38
    assert int(df["det_events"].to_numpy().sum()) == 128
    assert [int(df[f"Cat {i}"].to_numpy()[-1]) for i in range(1, 6)] == [37, 41, 53, 61, 50]
    last_ward = df["ward_state"].iloc[-1]
    assert sum(b["days_remaining"] for b in last_ward) == pytest.approx(55.67053101673399, abs=1e-9)


def test_v1_stress_test_ensemble() -> None:
    # The v1 "52-Week Stress Test": seed=i for i in range(20).
    finals = [
        int(ward_referral.run_simulation(DEFAULT_PARAMS, [], seed=i)["Over_26_Wks"].to_numpy()[-1])
        for i in range(20)
    ]
    assert finals == [74, 121, 84, 90, 103, 86, 116, 87, 109, 91,
                      75, 93, 97, 99, 123, 107, 62, 87, 92, 125]  # fmt: skip


@pytest.mark.parametrize(
    ("params", "target", "expected"),
    [
        (DEFAULT_PARAMS, 26, (8, 16)),
        ({**DEFAULT_PARAMS, "weekly_refs": 3, "total_beds": 10}, 12, (8, 16)),
    ],
)
def test_recommendation(params: dict, target: int, expected: tuple[int, int]) -> None:
    assert ward_referral.find_recommendation(params, target) == expected


def test_recommendation_falls_back_when_search_space_is_empty() -> None:
    # total_beds >= 17 leaves range(total_beds, 17) empty: the current config comes back.
    params = {**DEFAULT_PARAMS, "total_beds": 17, "surg_per_week": 4}
    assert ward_referral.find_recommendation(params, 10) == (4, 17)
