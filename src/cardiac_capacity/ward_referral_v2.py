"""Ward-referral mode v2: the v1 waiting-list simulation with four changes.

v1 (``ward_referral.py``) stays pinned. v2 changes, each addressing a known weakness of v1:

1. **Beds free on the actual discharge day** (v1: once a week, so every stay rounded up to 7 days).
   Theatre days are Mon-Fri; the weekly slots are spread round-robin over them; a bed is free from
   the day after a stay ends (stay = ceil of the Gamma draw in days, minimum 1; same Gamma as v1).
2. **Deterioration is per patient and follows the patient's own category**: one Bernoulli(p_cat)
   draw
   per patient per week, legacy patients included (v1: Poisson total, victims drawn uniformly,
   legacy
   immune from the rate but still picked). A long-wait rule multiplies the odds once a patient has
   waited ``long_wait_weeks`` (default 26) by ``long_wait_or`` (default 1.49).
   v1's jump of legacy patients to category 1 at 26 weeks is dropped.
3. **Two start modes**: ``"today"`` starts from the entered list and ward; ``"settled"`` starts
   empty
   and discards ``warmup_weeks`` (default 52) so the report is a steady-state question.
4. **Separate seeded streams** for initial state, arrivals, deterioration and length of stay.
   For one seed the initial list and the referrals are identical whatever beds and slots are
   chosen (tested); deterioration and length-of-stay draws still desynchronise once configurations
   admit different numbers, so pairing is partial (v1 interleaves all draws in one stream).

Also fixed : no 5,000-row buffer, the legacy count cannot exceed the backlog, a
cancellation is a scheduled slot that had a waiting patient but no free bed, and new referrals are
not flagged legacy. The output frame has the v1 columns.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

START_MODES = ("today", "settled")
THEATRE_DAYS = 5
DET_KEYS = ("det_2to1", "det_3to2", "det_4to3", "det_5to4")
DET_DEFAULTS = (0.12, 0.07, 0.04, 0.02)
LOS_DEFAULTS = (22, 11, 5, 2, 2)
LONG_WAIT_OR_DEFAULT = 1.49
LONG_WAIT_WEEKS_DEFAULT = 26


def _streams(seed: int | None) -> tuple[np.random.RandomState, ...]:
    if seed is None:
        return tuple(np.random.RandomState() for _ in range(4))
    return tuple(np.random.RandomState([seed, k]) for k in range(4))


def odds_adjusted(p: np.ndarray, odds_ratio: float) -> np.ndarray:
    """Probability after multiplying the odds by ``odds_ratio``."""
    return p * odds_ratio / (1 - p + p * odds_ratio)


def deterioration_probabilities(params: Mapping[str, Any]) -> np.ndarray:
    """Weekly probability of moving up one category, indexed by category 0..5 (0 and 1 are 0)."""
    rates = [params.get(k, d) for k, d in zip(DET_KEYS, DET_DEFAULTS, strict=True)]
    return np.array([0.0, 0.0, *rates], dtype=float)


def run_simulation(
    params: Mapping[str, Any],
    current_ward: Sequence[Mapping[str, Any]],
    weeks: int = 52,
    seed: int | None = None,
    start_mode: str = "today",
    warmup_weeks: int = 52,
    detail: bool = True,
) -> pd.DataFrame:
    """Weekly frame (columns as v1). ``detail=False`` skips the per-week ward records."""
    if start_mode not in START_MODES:
        raise ValueError(f"start_mode must be one of {START_MODES}")
    r_init, r_arr, r_det, r_los = _streams(seed)
    settled = start_mode == "settled"
    skip = warmup_weeks if settled else 0
    total_weeks = weeks + skip

    los_map = np.array(
        [0, *[params.get(f"los_cat{i}", d) for i, d in enumerate(LOS_DEFAULTS, start=1)]],
        dtype=float,
    )
    p_det = deterioration_probabilities(params)
    long_weeks = int(params.get("long_wait_weeks", LONG_WAIT_WEEKS_DEFAULT))
    p_det_long = odds_adjusted(p_det, float(params.get("long_wait_or", LONG_WAIT_OR_DEFAULT)))

    dist = np.array([params.get(f"dist_cat{i}", 10) for i in range(1, 6)], dtype=float)
    cat_probs = dist / dist.sum()
    slots_week = int(params["surg_per_week"])
    eff_cap = int(params["total_beds"]) - int(params["safety_buffer"])
    los_scale = float(params.get("los_scale", 1.0))
    weekly_refs = float(params["weekly_refs"])

    # Ward: absolute day on which each occupied bed is free again.
    if settled:
        ward_end = np.zeros(0)
        ward_cats = np.zeros(0, dtype=int)
    else:
        ward_end = np.ceil(
            np.array([p.get("days_remaining", 5) for p in current_ward], dtype=float)
        )
        ward_cats = np.array([p.get("cat", 3) for p in current_ward], dtype=int)

    # Backlog: category and whole weeks waited.
    if settled:
        cat = np.zeros(0, dtype=int)
        wait = np.zeros(0, dtype=int)
    else:
        total_bl = int(params.get("total_backlog", 60))
        legacy_pct = params.get("dist_legacy", 25) / 100
        n_leg = min(total_bl, int(r_init.poisson(total_bl * legacy_pct)))
        n_fresh = total_bl - n_leg
        cat = np.concatenate(
            [np.full(n_leg, 5), r_init.choice([1, 2, 3, 4, 5], size=n_fresh, p=cat_probs)]
        ).astype(int)
        wait = np.concatenate(
            [r_init.randint(1, 25, size=n_leg), r_init.randint(0, 25, size=n_fresh)]
        ).astype(int)

    base_slots, extra = divmod(slots_week, THEATRE_DAYS)
    history: list[dict[str, Any]] = []
    cancels = 0
    admitted = {f"Cat {i}": 0 for i in range(1, 6)}
    n_det = 0

    for week in range(total_weeks):
        start_day = week * 7
        occupied_now = ward_end > start_day
        counts = np.bincount(cat, minlength=6)
        row: dict[str, Any] = {
            "week": week - skip,
            **{f"Cat {i}": int(counts[i]) for i in range(1, 6)},
            "Over_26_Wks": int(np.sum(wait >= 26)),
            "occupancy": int(occupied_now.sum()),
            "cancellations": cancels,
            "admissions": admitted,
            "det_events": n_det,
            "ward_state": [],
        }
        if detail:
            row["ward_state"] = [
                {"cat": int(c), "days_remaining": float(e - start_day)}
                for c, e in zip(ward_cats[occupied_now], ward_end[occupied_now], strict=True)
            ]
        history.append(row)
        if week == total_weeks - 1:
            break

        # Aging, then per-patient deterioration on the patient's own category.
        wait = wait + 1
        probs = np.where(wait >= long_weeks, p_det_long[cat], p_det[cat])
        moved = r_det.random_sample(cat.size) < probs
        n_det = int(moved.sum())
        cat = cat - moved.astype(int)

        # New referrals.
        n_new = int(r_arr.poisson(weekly_refs))
        if n_new:
            cat = np.concatenate([cat, r_arr.choice([1, 2, 3, 4, 5], size=n_new, p=cat_probs)])
            wait = np.concatenate([wait, r_arr.poisson(2, size=n_new)])

        # The week's theatre days: beds free on the day the stay ends.
        cancels = 0
        admitted = {f"Cat {i}": 0 for i in range(1, 6)}
        keep = ward_end > start_day
        ward_end, ward_cats = ward_end[keep], ward_cats[keep]
        for d in range(THEATRE_DAYS):
            day = start_day + d
            todays = base_slots + (1 if d < extra else 0)
            if todays == 0:
                continue
            free = max(0, eff_cap - int(np.sum(ward_end > day)))
            waiting = cat.size
            n_adm = min(todays, free, waiting)
            cancels += min(todays, waiting) - n_adm
            if n_adm == 0:
                continue
            order = np.lexsort((-wait, cat))
            take, rest = order[:n_adm], order[n_adm:]
            adm_cats = cat[take]
            stays = np.ceil(np.maximum(1.0, r_los.gamma(shape=los_map[adm_cats], scale=los_scale)))
            ward_end = np.concatenate([ward_end, day + stays])
            ward_cats = np.concatenate([ward_cats, adm_cats])
            cats_u, counts_u = np.unique(adm_cats, return_counts=True)
            for c, k in zip(cats_u, counts_u, strict=True):
                admitted[f"Cat {int(c)}"] += int(k)
            cat, wait = cat[rest], wait[rest]

    frame = pd.DataFrame(history)
    if skip:
        frame = frame.iloc[skip:].reset_index(drop=True)
    return frame


def breaches_at(
    params: Mapping[str, Any],
    goal_week: int,
    seed: int,
    current_ward: Sequence[Mapping[str, Any]] = (),
    start_mode: str = "today",
    warmup_weeks: int = 52,
) -> int:
    """Patients waiting 26+ weeks at ``goal_week`` in one replication (fast path)."""
    df = run_simulation(
        params, current_ward, goal_week + 1, seed, start_mode, warmup_weeks, detail=False
    )
    return int(df["Over_26_Wks"].iloc[goal_week])
