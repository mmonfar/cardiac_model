"""Characterisation tests: values produced by the v1 CICU mode on synthetic parameters, pinned so
v1 behaviour stays reproducible inside v2."""

from __future__ import annotations

import pytest

from cardiac_capacity import cicu

# (mode, rounding) -> (totalCost, totalSurgeries, finalBacklog, finalState, max CICU occupancy)
PINNED = {
    ("priority", "round"): (106350000.0, 260, 60.0, [0.0, 1.0, 3.0, 56.0], 39.42857142857143),
    ("priority", "ceil"): (220550000.0, 260, 164.0, [1.0, 2.0, 43.0, 118.0], 86.14285714285714),
    ("priority", "floor"): (34330000.0, 213, 3.0, [0.0, 0.0, 1.0, 2.0], 37.285714285714285),
    ("priority", "none"): (
        105589764.37686771, 260, 60.0, [0.25, 0.75, 2.05, 56.95], 39.971428571428575
    ),
    ("weighted", "round"): (229180000.0, 0, 163.0, [0.0, 2.0, 68.0, 93.0], 91.28571428571428),
    ("weighted", "ceil"): (236860000.0, 0, 164.0, [2.0, 3.0, 55.0, 104.0], 92.14285714285714),
    ("weighted", "floor"): (245790000.0, 0, 185.0, [0.0, 1.0, 67.0, 117.0], 99.42857142857143),
    ("weighted", "none"): (
        231761352.60495898,
        0,
        171.35127894756005,
        [0.39691032836300466, 4.648480891753446, 56.832586387336406, 109.4733013401072],
        94.9463413530886,
    ),
}  # fmt: skip


@pytest.mark.parametrize(("mode", "rounding"), PINNED)
def test_capacity5_52_weeks(mode: str, rounding: str) -> None:
    cost, surgeries, backlog, final_state, max_cicu = PINNED[(mode, rounding)]
    df, summary = cicu.run_simulation(5, 52, rounding, scheduling_mode=mode)
    assert len(df) == 53  # week-0 baseline + 52 weeks
    assert summary["totalCost"] == pytest.approx(cost, rel=1e-12)
    assert summary["totalSurgeries"] == surgeries  # 0 in weighted mode: original quirk
    assert summary["finalBacklog"] == pytest.approx(backlog, rel=1e-12)
    assert summary["finalState"] == pytest.approx(final_state, rel=1e-12)
    assert df["cicu_occupancy"].max() == pytest.approx(max_cicu, rel=1e-12)


def test_week_zero_has_no_warning_flag() -> None:
    df, _ = cicu.run_simulation(5, 4)
    assert df["occupancy_warning"].isna().tolist() == [True, False, False, False, False]


DEFAULT_MAX_CICU = [92.0, 54.14285714285714, 39.42857142857143, 38.0, 36.57142857142857,
                    35.142857142857146, 33.714285714285715, 32.285714285714285,
                    30.857142857142854, 29.42857142857143, 28.714285714285715, 28.0]  # fmt: skip


def test_capacity_search_default_never_meets_criteria() -> None:
    # Occupancy is estimated from the *waiting* backlog, so with 10 beds no capacity in
    # 3..14 qualifies and the original app always showed "8+". Kept as-is (parity).
    table = cicu.find_optimal_capacity(52)
    assert table["capacity"].tolist() == list(range(3, 15))
    assert table["finalUrgent"].tolist() == [0.0] * 12
    assert table["maxCICU"].tolist() == pytest.approx(DEFAULT_MAX_CICU, rel=1e-12)
    assert not table["meetsCriteria"].to_numpy().any()
    assert cicu.recommended_capacity(table) is None


def test_capacity_search_with_40_beds_recommends_5() -> None:
    table = cicu.find_optimal_capacity(52, cicu_beds=40)
    assert table["maxCICU"].tolist() == pytest.approx(DEFAULT_MAX_CICU, rel=1e-12)
    assert cicu.recommended_capacity(table) == 5


def test_capacity_search_big_backlog() -> None:
    table = cicu.find_optimal_capacity(52, initial_backlog=120, weekly_referrals=9, cicu_beds=20)
    assert table["finalUrgent"].tolist() == [1.0] + [0.0] * 11
    assert table["maxCICU"].tolist() == pytest.approx(
        [235.85714285714286, 181.71428571428572, 143.85714285714286, 105.28571428571428,
         82.57142857142857, 81.14285714285714, 79.71428571428572, 78.28571428571428,
         76.85714285714286, 75.42857142857143, 74.0, 72.0],
        rel=1e-12,
    )  # fmt: skip
    assert cicu.recommended_capacity(table) is None
