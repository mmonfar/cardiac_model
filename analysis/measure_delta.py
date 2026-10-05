# ruff: noqa: E501  (long report strings)
"""v1 -> v2 delta on synthetic scenarios. Seeded; writes docs/v1-vs-v2.md.

Run: python analysis/measure_delta.py

Ward: 100 seeds per scenario for the fixed-configuration comparison (>= 30 required). v1 and v2
use different random streams, so each cell is an independent mean with its own CI (no paired differences
are claimed). Recommendation: v1 solver (single seed 42) versus the v2 recommender, both scored out of
sample on 200 fresh seeds under BOTH models. CICU: deterministic, so one run per capacity.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from cardiac_capacity import cicu, cicu_v2, recommend, ward_referral, ward_referral_v2
from cardiac_capacity.stats import mean_ci, wilson_interval
from cardiac_capacity.ward_referral import DEFAULT_PARAMS

N_SEEDS = 100
GOAL = 26
OOS_SEEDS = (
    5_000  # fresh seeds, disjoint from selection seeds (10,000+, 42) and validation (50,000+)
)
N_OOS = 200

MIX_ACUTE = {"dist_cat1": 40, "dist_cat2": 30, "dist_cat3": 15, "dist_cat4": 10, "dist_cat5": 5}
SCENARIOS: dict[str, dict[str, Any]] = {
    "A default (6 refs/wk, 5 slots, 8 beds)": {},
    "B low demand (3 refs/wk)": {"weekly_refs": 3},
    "C balanced (5 refs/wk)": {"weekly_refs": 5},
    "D overload (8 refs/wk)": {"weekly_refs": 8},
    "E high acuity (40/30/15/10/5 %, 4 refs/wk)": {**MIX_ACUTE, "weekly_refs": 4},
}
LOS = [22, 11, 5, 2, 2]


def load(params: dict[str, Any]) -> tuple[float, float]:
    """(slots load, bed load): referrals per slot, and demanded bed-days over bed-days available."""
    d = np.array([params[f"dist_cat{i}"] for i in range(1, 6)], dtype=float)
    mean_los = float((d / d.sum()) @ np.array(LOS))
    return (
        params["weekly_refs"] / params["surg_per_week"],
        params["weekly_refs"] * mean_los / (7 * (params["total_beds"] - params["safety_buffer"])),
    )


def fmt_ci(vals: list[float] | np.ndarray, nd: int = 1) -> str:
    m, lo, hi = mean_ci(vals)
    return f"{m:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


def prob(k: int, n: int) -> str:
    lo, hi = wilson_interval(k, n)
    return f"{100 * k / n:.0f}% [{100 * lo:.0f}, {100 * hi:.0f}]"


def fixed_config_table() -> list[str]:
    out = [
        f"| Scenario | slots load / bed load | v1 breaches wk {GOAL}, mean [95% CI] | v2 today | "
        f"v2 settled | v1 P(zero) | v2 P(zero) | v1 cancels / 52 wk | v2 cancels / 52 wk | "
        f"v1 mean ward occ. | v2 mean ward occ. |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, extra in SCENARIOS.items():
        p = {**DEFAULT_PARAMS, **extra}
        v1b, v2b, v2s, c1, c2, o1, o2 = [], [], [], [], [], [], []
        for s in range(N_SEEDS):
            a = ward_referral.run_simulation(p, [], 52, s)
            b = ward_referral_v2.run_simulation(p, [], 52, s, detail=False)
            v1b.append(float(a["Over_26_Wks"].iloc[GOAL]))
            v2b.append(float(b["Over_26_Wks"].iloc[GOAL]))
            v2s.append(
                float(
                    ward_referral_v2.run_simulation(
                        p, [], GOAL + 1, s, "settled", 52, detail=False
                    )["Over_26_Wks"].iloc[GOAL]
                )
            )
            c1.append(float(a["cancellations"].sum()))
            c2.append(float(b["cancellations"].sum()))
            o1.append(float(a["occupancy"].iloc[5:].mean()))
            o2.append(float(b["occupancy"].iloc[5:].mean()))
        z1 = sum(x == 0 for x in v1b)
        z2 = sum(x == 0 for x in v2b)
        sl, bl = load(p)
        out.append(
            f"| {name} | {sl:.2f} / {bl:.2f} | {fmt_ci(v1b)} | {fmt_ci(v2b)} | {fmt_ci(v2s)} | "
            f"{prob(z1, N_SEEDS)} | {prob(z2, N_SEEDS)} | {fmt_ci(c1, 0)} | {fmt_ci(c2, 0)} | "
            f"{fmt_ci(o1)} | {fmt_ci(o2)} |"
        )
    return out


def oos(params: dict[str, Any], slots: int, beds: int, version: str) -> tuple[int, int]:
    p = {**params, "surg_per_week": slots, "total_beds": beds}
    k = 0
    for i in range(N_OOS):
        if version == "v1":
            df = ward_referral.run_simulation(p, [], GOAL + 1, OOS_SEEDS + i)
            k += int(df["Over_26_Wks"].iloc[GOAL]) == 0
        else:
            k += ward_referral_v2.breaches_at(p, GOAL, OOS_SEEDS + i) == 0
    return k, N_OOS


def recommendation_table() -> list[str]:
    out = [
        "| Scenario | v1 solver pick (slots, beds) | its P(zero) out of sample, v1 model | "
        "its P(zero) out of sample, v2 model | v2 pick at 90% (slots, beds) | selection P "
        "| out-of-sample P(zero), v2 model [Wilson 95%] | boundary? |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, extra in SCENARIOS.items():
        p = {**DEFAULT_PARAMS, **extra}
        s1, b1 = ward_referral.find_ai_recommendation(p, GOAL)
        k1, n1 = oos(p, s1, b1, "v1")
        k1b, _ = oos(p, s1, b1, "v2")
        r = recommend.recommend(p, GOAL, 0.9, n_select=200, n_validate=N_OOS)
        pick = f"({r.slots}, {r.beds})" if r.found else "none in 1-24 beds, 1-12 slots"
        cell = (
            f"{100 * r.p_validate:.1f}% [{100 * r.ci_validate[0]:.1f}, {100 * r.ci_validate[1]:.1f}]"
            if r.found
            else "n/a"
        )
        out.append(
            f"| {name} | ({s1}, {b1}) | {prob(k1, n1)} | {prob(k1b, n1)} | {pick} | "
            f"{100 * r.p_select:.1f}% (n={r.n_select}) | {cell} | {'yes' if r.boundary else 'no'} |"
        )
    return out


def threshold_table() -> list[str]:
    out = [
        "| Threshold | pick (slots, beds) | selection P | out-of-sample P [Wilson 95%] |",
        "|---|---|---|---|",
    ]
    for t in (0.8, 0.9, 0.95):
        r = recommend.recommend(DEFAULT_PARAMS, GOAL, t, n_select=200, n_validate=N_OOS)
        pick = f"({r.slots}, {r.beds})" if r.found else "none"
        lo, hi = r.ci_validate
        out.append(
            f"| {t:.0%} | {pick} | {100 * r.p_select:.1f}% | "
            f"{100 * r.p_validate:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}] |"
        )
    return out


def start_mode_table() -> list[str]:
    out = [
        "| Start mode | pick (slots, beds) at 90% | out-of-sample P [Wilson 95%] |",
        "|---|---|---|",
    ]
    for mode in ("today", "settled"):
        r = recommend.recommend(
            {**DEFAULT_PARAMS, "weekly_refs": 4},
            GOAL,
            0.9,
            n_select=200,
            n_validate=N_OOS,
            start_mode=mode,
        )
        pick = f"({r.slots}, {r.beds})" if r.found else "none"
        lo, hi = r.ci_validate
        out.append(
            f"| {mode} | {pick} | {100 * r.p_validate:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}] |"
        )
    return out


def cicu_table() -> list[str]:
    out = [
        "| Capacity / wk | v1 peak load (waiting list) | v2 mean load, peak week | v2 peak day | v1 / v2 |",
        "|---|---|---|---|---|",
    ]
    for cap in (3, 4, 5, 6, 8, 10, 14):
        a = cicu.run_simulation(cap, 52)[0]
        b = cicu_v2.run_simulation(cap, 52)[0]
        v1 = float(a["cicu_occupancy"].to_numpy().max())
        v2m = float(b["cicu_occupancy"].to_numpy().max())
        v2p = float(b["cicu_peak_daily"].to_numpy().max())
        out.append(f"| {cap} | {v1:.1f} | {v2m:.1f} | {v2p:.1f} | {v1 / v2m:.1f}x |")
    return out


def cicu_recommended() -> list[str]:
    out = ["| CICU beds | v1 recommended capacity | v2 recommended capacity |", "|---|---|---|"]
    for beds in (10, 12, 15, 20):
        r1 = cicu.recommended_capacity(cicu.find_optimal_capacity(52, cicu_beds=beds))
        r2 = cicu.recommended_capacity(cicu_v2.find_optimal_capacity(52, cicu_beds=beds))
        out.append(
            f"| {beds} | {r1 if r1 is not None else 'none in 3-14'} | {r2 if r2 is not None else 'none in 3-14'} |"
        )
    return out


NOTES = """
## Reading these numbers (limits stated plainly)

- Section 1: fixing the bed clock lowers mean ward occupancy (A: 8.0 to 6.6 beds; B: 6.7 to 2.8) because v1 held
  every stay for whole weeks. Effects on 26-week waits are small or mixed at a fixed configuration (E is worse
  under v2: 13.1 to 15.6); scenario B's P(zero) rises 11% to 22%. 'Settled' answers a different question from
  'today': D (overload) keeps growing from an empty list (166 breaches); B and C clear.
- Section 2: the v1 solver's picks cleared all 26-week waits in 77-86% of fresh v1 runs (0% in E, where it fell
  back to the current setup because nothing reached zero on its one run). The v2 recommender's picks scored
  88.5-96.5% out of sample; two of five point estimates sit just under 90% (B 88.5%, D 89.5%) with CIs that
  include 90%: choosing the smallest passing setup on selection seeds is slightly optimistic, which is why the
  app reports the fresh-run rate and its CI next to the pick. The v1 pick scored under v2 depends on the model:
  v1 over-provisioned beds in D (100%), under-provisioned in B and E.
- v2 picks use many slots (9-11) because the starting list (60 patients, a quarter of them already waiting) must be
  worked off before week 26 and referrals alone are 3-8 a week. Search range: beds 1-24, slots 1-12; no pick sat on
  the edge of that range.
- Section 3: the threshold works as intended (selection and fresh-run rates move with it: 82%, 90.5%, 95%).
- Section 5: v1 over-reads 4.9x at the default capacity of 5 (39.4 vs 8.0 beds) and runs the wrong way (92 beds at
  capacity 3, 28 at 14); v2 rises with capacity (5.1 to 18.5 beds, mean of the busiest week).
- Section 6: v2 recommends capacity 3 at every bed count. That is the bottom of the 3-14 search range: the inherited
  criterion only requires urgent (category 1) cases to be cleared and load to fit, and priority scheduling
  always clears urgent cases first. It says nothing about the less urgent backlog. This criterion is unchanged
  from v1 and is left unchanged here on purpose; it is a modelling choice, not something v2 changed on its own.
- Deterioration rates in v2 are the v1 placeholders; the condition-group table is awaiting a clinical check.
  Nothing here is validated against real data.
"""


def main() -> None:
    t0 = time.time()
    parts = [
        "# v1 to v2 delta report (synthetic scenarios, generated by `measure_delta.py`)",
        "",
        f"Generated by `analysis/measure_delta.py`. Seeds: {N_SEEDS} per scenario for fixed-configuration "
        f"comparisons; out-of-sample checks use {N_OOS} fresh seeds ({OOS_SEEDS}-{OOS_SEEDS + N_OOS - 1}). "
        "All inputs are synthetic. Goal week = 26. 'Breaches' = patients waiting 26+ weeks at the goal week. "
        "Intervals: normal-approximation CI for means, Wilson for proportions. Not validated against real data.",
        "",
        "## 1. Ward, fixed configuration (same parameters, v1 vs v2)",
        "",
        *fixed_config_table(),
        "",
        "## 2. Ward, recommendation: v1 solver versus v2 recommender",
        "",
        "v1 solver: one replication per configuration, seed 42, beds from the current value to 16. v2: smallest "
        "(beds, then slots) with P(zero breaches at week 26) >= 90% on 200 selection seeds, scored on fresh seeds.",
        "",
        *recommendation_table(),
        "",
        "## 3. Threshold sensitivity (default scenario)",
        "",
        *threshold_table(),
        "",
        "## 4. Start mode (4 referrals/week, otherwise default)",
        "",
        "'today' starts from the entered list (60 patients, 25% long waiters); 'settled' starts empty and discards 52 weeks.",
        "",
        *start_mode_table(),
        "",
        "## 5. CICU load (deterministic, defaults, 52 weeks)",
        "",
        *cicu_table(),
        "",
        "## 6. CICU recommended capacity (urgent cleared and load within beds)",
        "",
        *cicu_recommended(),
        "",
        f"Runtime {time.time() - t0:.0f} s.",
        NOTES,
    ]
    (Path(__file__).resolve().parents[1] / "docs" / "v1-vs-v2.md").write_text("\n".join(parts), encoding="utf-8")
    print("ok", math.floor(time.time() - t0), "s")


if __name__ == "__main__":
    main()
