"""CICU mode v2: occupancy from operated patients (throughput x length of stay).

v1 (``cicu.py``, pinned) costs CICU load as ``sum(backlog_i x LOS_i / 7)``, i.e. from the
*waiting list*; it over-reads 4-7x and falls when more surgery is done. v2 keeps v1's waiting-list
dynamics unchanged (same deterministic fluid model, same rounding quirks) and replaces only the
occupancy: each week's surgeries are spread over five theatre days (Mon-Fri) and each operated
patient holds a CICU bed for ``LOS_i`` days (a daily bed ledger; discharge on the actual day).

Reported per week: ``cicu_occupancy`` = mean beds occupied over the week's 7 days,
``cicu_peak_daily`` = the busiest day, and ``cicu_occupancy_backlog_v1`` = the v1 figure for
comparison. In steady state ``cicu_occupancy`` equals ``sum(surgeries_i x LOS_i) / 7`` (Little's
law).
CICU beds still only raise a flag; they do not block surgery (unchanged from v1).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from cardiac_capacity import cicu

THEATRE_DAYS = 5


def bed_ledger(surgeries: np.ndarray, los_days: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    """(weekly mean occupancy, weekly peak daily occupancy) from weekly surgeries by category.

    ``surgeries`` has shape (weeks, categories). Surgeries of a week are spread evenly over the
    first five days; a stay of L days occupies the bed on L whole days (a fractional last day counts
    in proportion), freed on the actual discharge day.
    """
    n_weeks, n_cat = surgeries.shape
    days = 7 * n_weeks
    occupied = np.zeros(days)
    for i in range(n_cat):
        daily = np.zeros(days)
        for w in range(n_weeks):
            daily[7 * w : 7 * w + THEATRE_DAYS] += surgeries[w, i] / THEATRE_DAYS
        reach = int(np.ceil(los_days[i])) + 1
        kernel = np.clip(los_days[i] - np.arange(reach), 0.0, 1.0)
        occupied += np.convolve(daily, kernel)[:days]
    by_week = occupied.reshape(n_weeks, 7)
    return by_week.mean(axis=1), by_week.max(axis=1)


def run_simulation(
    capacity: int,
    weeks: int,
    rounding_method: str = "round",
    initial_backlog: float = 60,
    weekly_referrals: float = 5,
    category_distribution: Sequence[float] = (0.05, 0.15, 0.3, 0.5),
    deterioration_rates: Sequence[float] = (0, 0.05, 0.02, 0.01),
    costs: Sequence[float] = (100000, 90000, 50000, 30000),
    los_days: Sequence[float] = (14, 10, 5, 3),
    cicu_beds: float = 10,
    scheduling_mode: str = "priority",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """v1's waiting list with v2 occupancy; same signature and return shape as ``cicu``."""
    df, summary = cicu.run_simulation(
        capacity,
        weeks,
        rounding_method,
        initial_backlog,
        weekly_referrals,
        category_distribution,
        deterioration_rates,
        costs,
        los_days,
        cicu_beds,
        scheduling_mode,
    )
    surg = df[[f"surgeries_cat{i}" for i in range(1, 5)]].to_numpy(dtype=float)
    mean_occ, peak_occ = bed_ledger(surg, los_days)
    df = df.copy()
    df["cicu_occupancy_backlog_v1"] = df["cicu_occupancy"].astype(float)
    df["cicu_occupancy"] = mean_occ
    df["cicu_peak_daily"] = peak_occ
    df["occupancy_warning"] = df["cicu_peak_daily"] > cicu_beds
    df.loc[0, "occupancy_warning"] = False
    # v2 counts surgeries in both scheduling modes (v1's summary quirk stays in v1).
    summary = {
        **summary,
        "totalSurgeries": float(df["total_surgeries"].to_numpy(dtype=float).sum()),
    }
    return df, summary


def find_optimal_capacity(
    weeks: int,
    rounding_method: str = "round",
    initial_backlog: float = 60,
    weekly_referrals: float = 5,
    category_distribution: Sequence[float] = (0.05, 0.15, 0.3, 0.5),
    deterioration_rates: Sequence[float] = (0, 0.05, 0.02, 0.01),
    costs: Sequence[float] = (100000, 90000, 50000, 30000),
    los_days: Sequence[float] = (14, 10, 5, 3),
    cicu_beds: float = 10,
    scheduling_mode: str = "priority",
) -> pd.DataFrame:
    """Per capacity 3..14: final urgent backlog, peak weekly CICU load (v2) and whether both
    hold."""
    rows = []
    for cap in range(3, 15):
        df, summary = run_simulation(
            cap,
            weeks,
            rounding_method,
            initial_backlog,
            weekly_referrals,
            category_distribution,
            deterioration_rates,
            costs,
            los_days,
            cicu_beds,
            scheduling_mode,
        )
        final_urgent = summary["finalState"][0]
        max_cicu = float(df["cicu_peak_daily"].to_numpy().max())
        rows.append(
            {
                "capacity": cap,
                "finalUrgent": final_urgent,
                "maxCICU": max_cicu,
                "meetsCriteria": bool(final_urgent == 0 and max_cicu <= cicu_beds),
            }
        )
    return pd.DataFrame(rows)
