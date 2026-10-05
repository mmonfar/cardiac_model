"""CICU v2: occupancy from operated patients, v1 untouched."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cardiac_capacity import CicuParams, CicuSimulator, cicu, cicu_v2

LOS = (14, 10, 5, 3)


def test_steady_state_equals_littles_law() -> None:
    # Backlog never empties and nobody deteriorates, so surgeries are 5/week, all urgent.
    df, _ = cicu_v2.run_simulation(
        5,
        20,
        rounding_method="none",
        initial_backlog=1000,
        weekly_referrals=0,
        category_distribution=(1, 0, 0, 0),
        deterioration_rates=(0, 0, 0, 0),
    )
    steady = df["cicu_occupancy"].to_numpy()[4:]
    assert steady == pytest.approx(5 * 14 / 7, abs=1e-9)


def test_ledger_matches_sum_surgeries_times_los_over_7_with_mixed_categories() -> None:
    surgeries = np.tile([2.0, 1.0, 1.0, 1.0], (12, 1))
    mean_occ, peak = cicu_v2.bed_ledger(surgeries, LOS)
    expected = sum(s * los for s, los in zip([2, 1, 1, 1], LOS, strict=True)) / 7
    assert mean_occ[4:] == pytest.approx(expected, abs=1e-9)
    assert (peak >= mean_occ - 1e-12).all()


def test_bed_freed_on_actual_discharge_day() -> None:
    # 7 one-day stays in one week, spread Mon-Fri (1.4 a day): each bed is free the next day.
    mean_occ, peak = cicu_v2.bed_ledger(np.array([[7.0], [0.0]]), (1,))
    assert peak[0] == pytest.approx(1.4)
    assert mean_occ[0] == pytest.approx(1.0)
    assert mean_occ[1] == pytest.approx(0.0)  # nothing carries into the next week


def test_sign_is_fixed_more_surgery_means_more_icu_load() -> None:
    v1 = [cicu.run_simulation(c, 52)[0]["cicu_occupancy"].max() for c in (3, 5, 8)]
    v2 = [cicu_v2.run_simulation(c, 52)[0]["cicu_occupancy"].max() for c in (3, 5, 8)]
    assert v1[0] > v1[1] > v1[2]  # v1: operating more LOWERS reported ICU load (the defect)
    assert v2[0] < v2[1] < v2[2]  # v2: operating more raises it
    assert v1[1] > 4 * v2[1] - 1  # v1 over-reads several-fold at the default capacity


def test_waiting_list_dynamics_are_v1s() -> None:
    a, sa = cicu.run_simulation(6, 30)
    b, sb = cicu_v2.run_simulation(6, 30)
    for col in ["total_closing", "total_surgeries", "weekly_backlog_cost", "cat1_closing"]:
        pd.testing.assert_series_equal(a[col], b[col])
    assert sa["finalState"] == sb["finalState"]
    assert b["cicu_occupancy_backlog_v1"].tolist() == a["cicu_occupancy"].tolist()


def test_week_zero_has_no_load_and_counts_surgeries_in_weighted_mode() -> None:
    df, summary = cicu_v2.run_simulation(5, 10, scheduling_mode="weighted")
    assert df["cicu_occupancy"].iloc[0] == 0
    assert summary["totalSurgeries"] > 0  # v1 quirk (always 0 here) is not carried into v2
    assert cicu.run_simulation(5, 10, scheduling_mode="weighted")[1]["totalSurgeries"] == 0


def test_capacity_table_uses_v2_load_and_can_pass() -> None:
    # v1 never passes at the default 10 beds; v2 with the same beds count can.
    assert not cicu.find_optimal_capacity(52)["meetsCriteria"].to_numpy().any()
    table = cicu_v2.find_optimal_capacity(52, cicu_beds=15)
    assert table["meetsCriteria"].to_numpy().any()
    assert table["maxCICU"].iloc[0] < table["maxCICU"].iloc[-1]


def test_simulator_switch() -> None:
    p = CicuParams()
    v1 = CicuSimulator(5, p).simulate(20)
    v2 = CicuSimulator(5, p, model_version="v2").simulate(20)
    assert "cicu_peak_daily" not in v1.columns and "cicu_peak_daily" in v2.columns
    again = CicuSimulator(5, p).simulate(20)
    assert again["cicu_occupancy"].tolist() == v1["cicu_occupancy"].tolist()
    with pytest.raises(ValueError):
        CicuSimulator(5, p, model_version="v3").simulate(5)
