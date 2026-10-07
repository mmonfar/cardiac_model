"""CICU mode: deterministic discrete-time waiting list constrained by CICU beds.

This is the v1 CICU mode, kept as published in v1 with the
arithmetic unchanged; see ``tests/engine/test_cicu_pinned.py``. The model has no randomness, so the
``CicuSimulator`` wrapper ignores ``seed`` and reports ``stochastic = False``: a Monte Carlo
run over it returns a degenerate distribution (p5 = p50 = p95), which is the honest answer.

Four categories (urgent → routine). Each week: operate in priority order (or by fixed
weights), deteriorate one category up by rate, add referrals by the category mix, then cost
the backlog and estimate CICU occupancy as ``sum(backlog * LOS_days / 7)``.

Known quirks kept on purpose (v1 behaviour, preserved):

- ``weeks`` produces ``weeks + 1`` rows (a week-0 baseline plus weeks 1..N); week 0 has no
  deterioration/referral columns and ``occupancy_warning`` is missing (NaN) there.
- In ``"weighted"`` mode ``summary["totalSurgeries"]`` stays 0: v1 only counts
  surgeries in priority mode. The weekly ``total_surgeries`` column is correct in both modes.
- An unknown ``scheduling_mode`` falls back to priority order; an unknown rounding method
  falls back to ``round``.
- ``find_optimal_capacity`` searches capacities 3..14 only.

The v1 list defaults are tuples here (never mutated in either version).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

MODE = "cicu"
ROUNDING_METHODS = ("round", "ceil", "floor", "none")
SCHEDULING_MODES = ("priority", "weighted")


def apply_rounding(value: Any, method: str) -> Any:
    """Apply rounding based on selected method."""
    if method == "ceil":
        return np.ceil(value)
    elif method == "floor":
        return np.floor(value)
    elif method == "none":
        return value
    else:  # default 'round'
        return np.round(value)


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
    scheduling_mode: str = "priority",  # 'priority' or 'weighted'
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Weekly frame of the simulation and a summary dict of final metrics."""

    def apply_r(x: Any) -> Any:
        return apply_rounding(x, rounding_method)

    weekly_data: list[dict[str, Any]] = []

    # Initial backlog split by category
    categories: list[Any] = [apply_r(initial_backlog * p) for p in category_distribution]

    # Initial CICU occupancy (0 at start)
    cicu_occupancy: Any = 0

    cumulative_cost = sum(count * costs[i] for i, count in enumerate(categories))
    total_surgeries = 0

    # --- Week 0 baseline ---
    weekly_data.append(
        {
            "week": 0,
            "cat1_opening": categories[0],
            "cat2_opening": categories[1],
            "cat3_opening": categories[2],
            "cat4_opening": categories[3],
            "total_opening": sum(categories),
            "surgeries_cat1": 0,
            "surgeries_cat2": 0,
            "surgeries_cat3": 0,
            "surgeries_cat4": 0,
            "total_surgeries": 0,
            "cicu_occupancy": cicu_occupancy,
            "total_closing": sum(categories),
            "weekly_backlog_cost": cumulative_cost,
            "cumulative_cost": cumulative_cost,
        }
    )

    # --- Weeks 1 to N ---
    for week in range(1, weeks + 1):
        week_data: dict[str, Any] = {}
        week_data["week"] = week
        week_data["cat1_opening"] = categories[0]
        week_data["cat2_opening"] = categories[1]
        week_data["cat3_opening"] = categories[2]
        week_data["cat4_opening"] = categories[3]
        week_data["total_opening"] = sum(categories)

        # Step 1: Determine surgery order
        surgery_order = [0, 1, 2, 3]
        if scheduling_mode == "weighted":
            # Weighted allocation: 50% urgent, 30% emergency, 20% semi/routine
            weights = [0.5, 0.3, 0.15, 0.05]
            surgeries: list[Any] = [0, 0, 0, 0]
            remaining = capacity
            for i, w in enumerate(weights):
                allocated = min(apply_r(capacity * w), categories[i], remaining)
                surgeries[i] = allocated
                categories[i] -= allocated
                remaining -= allocated
            week_data.update({f"surgeries_cat{i + 1}": surgeries[i] for i in range(4)})
            week_data["total_surgeries"] = sum(surgeries)
        else:
            # Priority mode surgeries (also the fallback for an unknown mode)
            surgeries = [0, 0, 0, 0]
            remaining_capacity = capacity
            for cat in surgery_order:
                perform = min(categories[cat], remaining_capacity)
                surgeries[cat] = perform
                categories[cat] -= perform
                remaining_capacity -= perform
                total_surgeries += perform
                if remaining_capacity <= 0:
                    break
            week_data.update({f"surgeries_cat{i + 1}": surgeries[i] for i in range(4)})
            week_data["total_surgeries"] = sum(surgeries)

        # Step 2: Deterioration
        det_4to3 = apply_r(categories[3] * deterioration_rates[3])
        det_3to2 = apply_r(categories[2] * deterioration_rates[2])
        det_2to1 = apply_r(categories[1] * deterioration_rates[1])
        categories[3] -= det_4to3
        categories[2] += det_4to3 - det_3to2
        categories[1] += det_3to2 - det_2to1
        categories[0] += det_2to1

        week_data.update(
            {
                "deteriorated_4to3": det_4to3,
                "deteriorated_3to2": det_3to2,
                "deteriorated_2to1": det_2to1,
                "total_deteriorated": det_4to3 + det_3to2 + det_2to1,
            }
        )

        # Step 3: New referrals
        new_referrals = [apply_r(weekly_referrals * p) for p in category_distribution]
        for i in range(4):
            categories[i] += new_referrals[i]
        week_data.update(
            {
                "new_referrals_cat1": new_referrals[0],
                "new_referrals_cat2": new_referrals[1],
                "new_referrals_cat3": new_referrals[2],
                "new_referrals_cat4": new_referrals[3],
                "total_new_referrals": sum(new_referrals),
            }
        )

        # Step 4: Weekly cost
        weekly_backlog_cost = sum(categories[i] * costs[i] for i in range(4))
        cumulative_cost += weekly_backlog_cost

        # Step 5: CICU occupancy estimation (LOS in weeks = LOS_days / 7)
        cicu_occupancy = sum([categories[i] * los_days[i] / 7 for i in range(4)])
        occupancy_warning = cicu_occupancy > cicu_beds

        week_data.update(
            {
                "cat1_closing": categories[0],
                "cat2_closing": categories[1],
                "cat3_closing": categories[2],
                "cat4_closing": categories[3],
                "total_closing": sum(categories),
                "weekly_backlog_cost": weekly_backlog_cost,
                "cumulative_cost": cumulative_cost,
                "cicu_occupancy": cicu_occupancy,
                "occupancy_warning": occupancy_warning,
            }
        )

        weekly_data.append(week_data)

    df = pd.DataFrame(weekly_data)
    summary = {
        "finalState": categories,
        "totalCost": cumulative_cost,
        "totalSurgeries": total_surgeries,
        "finalBacklog": sum(categories),
        "recommended_capacity": capacity,  # placeholder; see find_optimal_capacity
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
    """Per capacity 3..14: final urgent backlog, peak CICU occupancy, and whether both hold
    (urgent cleared, occupancy within CICU beds)."""
    results = []
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
        max_cicu = df["cicu_occupancy"].max()
        meets_criteria = final_urgent == 0 and max_cicu <= cicu_beds
        results.append(
            {
                "capacity": cap,
                "finalUrgent": final_urgent,
                "maxCICU": max_cicu,
                "meetsCriteria": meets_criteria,
            }
        )
    return pd.DataFrame(results)


@dataclass(frozen=True)
class CicuParams:
    """Everything but capacity and horizon; defaults are v1's."""

    rounding_method: str = "round"
    initial_backlog: float = 60
    weekly_referrals: float = 5
    category_distribution: tuple[float, ...] = (0.05, 0.15, 0.3, 0.5)
    deterioration_rates: tuple[float, ...] = (0, 0.05, 0.02, 0.01)
    costs: tuple[float, ...] = (100000, 90000, 50000, 30000)
    los_days: tuple[float, ...] = (14, 10, 5, 3)
    cicu_beds: float = 10
    scheduling_mode: str = "priority"


def recommended_capacity(table: pd.DataFrame) -> int | None:
    """Smallest capacity meeting the criteria, or ``None`` (the v1 app showed "8+")."""
    caps = table["capacity"].to_numpy()[table["meetsCriteria"].to_numpy(dtype=bool)]
    return None if caps.size == 0 else int(caps.min())


@dataclass(frozen=True)
class CicuSimulator:
    """``CapacitySimulator`` for the CICU mode (deterministic)."""

    capacity: int = 5
    params: CicuParams = CicuParams()
    model_version: str = "v1"  # "v1" is pinned; "v2" = occupancy from operated patients

    @property
    def mode(self) -> str:
        return MODE

    @property
    def stochastic(self) -> bool:
        return False

    @property
    def outcome_label(self) -> str:
        return "Backlog at the final week"

    def _run(self, weeks: int) -> tuple[pd.DataFrame, dict[str, Any]]:
        if self.model_version == "v2":
            from cardiac_capacity import cicu_v2  # circular at import time

            return cicu_v2.run_simulation(self.capacity, weeks, **asdict(self.params))
        if self.model_version != "v1":
            raise ValueError("model_version must be 'v1' or 'v2'")
        return run_simulation(self.capacity, weeks, **asdict(self.params))

    def simulate(self, weeks: int = 52, seed: int | None = None) -> pd.DataFrame:
        del seed  # deterministic model
        return self._run(weeks)[0]

    def summary(self, weeks: int = 52) -> dict[str, Any]:
        return self._run(weeks)[1]

    def capacity_table(self, weeks: int = 52) -> pd.DataFrame:
        if self.model_version == "v2":
            from cardiac_capacity import cicu_v2  # circular at import time

            return cicu_v2.find_optimal_capacity(weeks, **asdict(self.params))
        return find_optimal_capacity(weeks, **asdict(self.params))

    def outcome(self, weekly: pd.DataFrame) -> float:
        return float(weekly["total_closing"].iloc[-1])
