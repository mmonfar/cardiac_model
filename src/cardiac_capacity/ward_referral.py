"""Ward-referral mode: stochastic waiting list feeding a cardiac surgical ward.

This is the v1 ward engine (``engine.py`` at tag ``v1-final``). The arithmetic and the *order of
random draws* are those of v1, so every fixed seed reproduces the v1 output exactly (see
``tests/engine/test_ward_referral_pinned.py``). The one deliberate difference: v1 seeded numpy's
*global* RNG (``np.random.seed``); this module draws from a private ``RandomState``
(``montecarlo.rng``), which yields the identical stream without touching global state.
``seed=None`` therefore draws fresh entropy rather than continuing the global stream.

Weekly loop, per v1: log the state, then (except in the last week) age the backlog,
breach legacy patients at 26 weeks, deteriorate by Poisson, add Poisson referrals, discharge
(7 days per week), and admit by category then by longest wait into gamma-distributed stays.

Known quirks kept on purpose (v1 behaviour, preserved):

- ``dist_legacy`` defaults to 25 % for the starting backlog but 10 % for new referrals.
- The backlog is a fixed 5000-row buffer; referrals beyond 4999 active patients are dropped.
- ``find_recommendation`` only searches ``total_beds`` .. 16 and ``slots`` 1 .. 12, with
  seed 42, and falls back to the current configuration if nothing reaches zero risk.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from cardiac_capacity import ward_referral_v2
from cardiac_capacity.montecarlo import rng

MODE = "ward_referral"


def run_simulation(
    params: Mapping[str, Any],
    current_ward: Sequence[Mapping[str, Any]],
    weeks: int = 52,
    seed: int | None = None,
) -> pd.DataFrame:
    r = rng(seed)

    # --- 1. SETUP PARAMETERS ---
    history = []

    # Map categories to their mean LOS for Gamma distribution
    los_map = np.array(
        [
            0,
            params.get("los_cat1", 22),
            params.get("los_cat2", 11),
            params.get("los_cat3", 5),
            params.get("los_cat4", 2),
            params.get("los_cat5", 2),
        ]
    )

    # Map categories to their deterioration probabilities
    det_rates = np.array(
        [
            0,
            0,
            params.get("det_2to1", 0.12),
            params.get("det_3to2", 0.07),
            params.get("det_4to3", 0.04),
            params.get("det_5to4", 0.02),
        ]
    )

    total_dist = sum([params.get(f"dist_cat{i}", 10) for i in range(1, 6)])
    cat_probs = [params.get(f"dist_cat{i}", 10) / total_dist for i in range(1, 6)]

    # Ward state: days remaining for occupied beds
    ward_days = np.array([p.get("days_remaining", 5) for p in current_ward], dtype=float)
    ward_cats = np.array([p.get("cat", 3) for p in current_ward], dtype=int)

    # --- 2. INITIALIZE BACKLOG ---
    # Column 0: Category | Column 1: Weeks Waiting | Column 2: Is Legacy (1=True, 0=False)
    total_bl = params.get("total_backlog", 60)
    legacy_pct = params.get("dist_legacy", 25) / 100
    num_legacy = r.poisson(total_bl * legacy_pct)
    num_fresh = max(0, total_bl - num_legacy)

    backlog = np.zeros((5000, 3))

    # Legacy cohort: stable cat 5 carrying waiting-time "debt"
    backlog[:num_legacy, 0] = 5
    backlog[:num_legacy, 1] = r.randint(1, 25, size=num_legacy)
    backlog[:num_legacy, 2] = 1

    # Standard cohort
    backlog[num_legacy:total_bl, 0] = r.choice([1, 2, 3, 4, 5], size=num_fresh, p=cat_probs)
    backlog[num_legacy:total_bl, 1] = r.randint(0, 25, size=num_fresh)

    active_count = total_bl

    # --- 3. WEEKLY LOOP ---
    cancellations = 0
    admitted_counts = {f"Cat {i}": 0 for i in range(1, 6)}
    num_det = 0

    for week in range(weeks):
        # Logging first: week 0 records the ward exactly as given
        history.append(
            {
                "week": week,
                "Cat 1": np.sum(backlog[:active_count, 0] == 1),
                "Cat 2": np.sum(backlog[:active_count, 0] == 2),
                "Cat 3": np.sum(backlog[:active_count, 0] == 3),
                "Cat 4": np.sum(backlog[:active_count, 0] == 4),
                "Cat 5": np.sum(backlog[:active_count, 0] == 5),
                "Over_26_Wks": np.sum(backlog[:active_count, 1] >= 26),
                "occupancy": len(ward_days),
                "cancellations": cancellations,
                "admissions": admitted_counts,
                "det_events": num_det,
                "ward_state": [
                    {"cat": int(c), "days_remaining": d}
                    for c, d in zip(ward_cats, ward_days, strict=True)
                ],
            }
        )

        # Transition to the next week
        if week < weeks - 1:
            num_det = 0
            if active_count > 0:
                view = backlog[:active_count]

                # A) Aging
                view[:, 1] += 1

                # B) Legacy breach
                legacy_breach_mask = (view[:, 2] == 1) & (view[:, 1] >= 26) & (view[:, 0] > 1)
                view[legacy_breach_mask, 0] = 1

                # C) Clinical deterioration
                std_mask = (view[:, 2] == 0) & (view[:, 0] > 1)
                if np.any(std_mask):
                    current_cats = view[std_mask, 0].astype(int)
                    system_lambda = det_rates[current_cats].sum()
                    num_det = r.poisson(system_lambda)
                    if num_det > 0:
                        upgradable_idx = np.where(view[:, 0] > 1)[0]
                        if len(upgradable_idx) > 0:
                            actual_upgrades = min(num_det, len(upgradable_idx))
                            targets = r.choice(upgradable_idx, size=actual_upgrades, replace=False)
                            view[targets, 0] -= 1

            # D) New referrals
            new_refs = r.poisson(params["weekly_refs"])
            for _ in range(new_refs):
                if active_count < 4999:
                    is_special = (
                        1 if r.random_sample() < (params.get("dist_legacy", 10) / 100) else 0
                    )
                    arrival_week = max(0, r.poisson(2))
                    arrival_cat = r.choice([1, 2, 3, 4, 5], p=cat_probs)
                    if is_special and arrival_week >= 26:
                        arrival_cat = 1
                    backlog[active_count] = [arrival_cat, arrival_week, is_special]
                    active_count += 1

            # E) Discharges
            ward_days -= 7
            mask = ward_days > 0
            ward_days = ward_days[mask]
            ward_cats = ward_cats[mask]

            # F) Admissions & sorting
            eff_cap = params["total_beds"] - params["safety_buffer"]
            avail = int(max(0, eff_cap - len(ward_days)))
            to_admit = min(avail, params["surg_per_week"], active_count)
            cancellations = max(0, params["surg_per_week"] - avail) if active_count > 0 else 0
            admitted_counts = {f"Cat {i}": 0 for i in range(1, 6)}

            if to_admit > 0:
                idx = np.lexsort((-backlog[:active_count, 1], backlog[:active_count, 0]))
                backlog[:active_count] = backlog[idx]
                admitted_view = backlog[:to_admit]
                new_cats = admitted_view[:, 0].astype(int)
                counts = np.bincount(new_cats, minlength=6)
                for i in range(1, 6):
                    admitted_counts[f"Cat {i}"] = int(counts[i])

                shapes = los_map[new_cats]
                new_stays = r.gamma(shape=shapes, scale=params.get("los_scale", 1.0))
                ward_days = np.concatenate([ward_days, np.maximum(1, new_stays)])
                ward_cats = np.concatenate([ward_cats, new_cats])

                backlog[: active_count - to_admit] = backlog[to_admit:active_count]
                active_count -= to_admit

    return pd.DataFrame(history)


def find_recommendation(params: Mapping[str, Any], target_wk: int) -> tuple[int, int]:
    """(slots, beds) with zero patients over 26 weeks at ``target_wk`` and the lowest score."""
    best_score = float("inf")
    best_config = (params["surg_per_week"], params["total_beds"])

    for beds in range(params["total_beds"], 17):
        for slots in range(1, 13):
            test_params = {**params, "surg_per_week": slots, "total_beds": beds}
            df = run_simulation(test_params, [], weeks=target_wk + 1, seed=42)

            risk_at_target = df.iloc[target_wk]["Over_26_Wks"]
            total_cancels = df["cancellations"].sum()

            # Zero risk dominates; then cancellations, beds and slots
            score = (risk_at_target * 5000) + (total_cancels * 100) + (beds * 50) + (slots * 20)

            if risk_at_target == 0 and score < best_score:
                best_score = score
                best_config = (slots, beds)

    return best_config


DEFAULT_PARAMS: dict[str, Any] = {
    # The v1 app's PROPOSED-scenario sidebar defaults (app.py at tag v1-final).
    "total_backlog": 60,
    "dist_legacy": 10,
    "weekly_refs": 6,
    "dist_cat1": 10,
    "dist_cat2": 15,
    "dist_cat3": 20,
    "dist_cat4": 30,
    "dist_cat5": 25,
    "los_cat1": 22,
    "los_cat2": 11,
    "los_cat3": 5,
    "los_cat4": 2,
    "los_cat5": 2,
    "det_5to4": 0.02,
    "det_4to3": 0.04,
    "det_3to2": 0.07,
    "det_2to1": 0.12,
    "los_scale": 1.0,
    "total_beds": 8,
    "safety_buffer": 0,
    "surg_per_week": 5,
}


@dataclass(frozen=True)
class WardReferralSimulator:
    """``CapacitySimulator`` for the ward-referral mode."""

    params: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    current_ward: Sequence[Mapping[str, Any]] = ()
    model_version: str = "v1"  # "v1" is pinned; "v2" is ``ward_referral_v2`` 
    start_mode: str = "today"  # v2 only: "today" or "settled"
    warmup_weeks: int = 52  # v2 only, settled start

    @property
    def mode(self) -> str:
        return MODE

    @property
    def stochastic(self) -> bool:
        return True

    @property
    def outcome_label(self) -> str:
        return "Patients waiting 26+ weeks at the final week"

    def simulate(self, weeks: int = 52, seed: int | None = None) -> pd.DataFrame:
        if self.model_version == "v2":
            return ward_referral_v2.run_simulation(
                self.params, self.current_ward, weeks, seed, self.start_mode, self.warmup_weeks
            )
        if self.model_version != "v1":
            raise ValueError("model_version must be 'v1' or 'v2'")
        return run_simulation(self.params, self.current_ward, weeks=weeks, seed=seed)

    def outcome(self, weekly: pd.DataFrame) -> float:
        return float(weekly["Over_26_Wks"].iloc[-1])
