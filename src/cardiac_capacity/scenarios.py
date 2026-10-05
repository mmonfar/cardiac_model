"""Synthetic parameter sets for tests, demos and parity runs.

No real patient, referral or cost data: every value is invented to span the original apps'
slider ranges.
"""

from __future__ import annotations

from typing import Any

from cardiac_capacity.ward_referral import DEFAULT_PARAMS

# A live ward as the original app's floor-map editor seeds it: three occupied beds.
LIVE_WARD: list[dict[str, Any]] = [
    {"cat": 1, "days_remaining": 14},
    {"cat": 2, "days_remaining": 7},
    {"cat": 3, "days_remaining": 3},
]

# Ward-referral scenarios spanning the original sliders' ranges (synthetic).
WARD_SCENARIOS: dict[str, dict[str, Any]] = {
    "default": dict(DEFAULT_PARAMS),
    "baseline": {**DEFAULT_PARAMS, "surg_per_week": 3, "total_beds": 7},
    "tight": {**DEFAULT_PARAMS, "total_beds": 5, "surg_per_week": 3, "weekly_refs": 9},
    "roomy": {**DEFAULT_PARAMS, "total_beds": 15, "surg_per_week": 10, "weekly_refs": 3},
    "buffered": {**DEFAULT_PARAMS, "safety_buffer": 3, "total_beds": 12},
    "all_legacy": {**DEFAULT_PARAMS, "dist_legacy": 100},
    "no_legacy": {**DEFAULT_PARAMS, "dist_legacy": 0},
    "acute_mix": {**DEFAULT_PARAMS, "dist_cat1": 60, "dist_cat2": 30, "dist_cat5": 0},
    "long_stays": {**DEFAULT_PARAMS, "los_cat1": 40, "los_cat2": 20, "los_scale": 2.0},
    "fast_decline": {**DEFAULT_PARAMS, "det_5to4": 0.1, "det_4to3": 0.1, "det_2to1": 0.3},
    "big_backlog": {**DEFAULT_PARAMS, "total_backlog": 400, "weekly_refs": 15},
    "empty_backlog": {**DEFAULT_PARAMS, "total_backlog": 0, "weekly_refs": 1},
    "sparse_params": {"weekly_refs": 4, "total_beds": 6, "safety_buffer": 1, "surg_per_week": 4},
}

# CICU scenarios (synthetic), combined with every rounding and scheduling mode.
CICU_SCENARIOS: dict[str, dict[str, Any]] = {
    "default": {"capacity": 5},
    "low_capacity": {"capacity": 3},
    "high_capacity": {"capacity": 14},
    "big_backlog": {"capacity": 8, "initial_backlog": 200, "weekly_referrals": 9},
    "no_backlog": {"capacity": 4, "initial_backlog": 0, "weekly_referrals": 2},
    "urgent_mix": {"capacity": 6, "category_distribution": [0.4, 0.3, 0.2, 0.1]},
    "fast_decline": {"capacity": 5, "deterioration_rates": [0, 0.2, 0.15, 0.1]},
    "odd_referrals": {"capacity": 7, "weekly_referrals": 7, "initial_backlog": 37},
}
