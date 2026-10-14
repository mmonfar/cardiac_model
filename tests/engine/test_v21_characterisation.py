"""Characterisation of v2.1 behaviour (migrate-with-parity).

``tests/golden/v21.json`` was generated from the unchanged v2.1.0 engine before any v2.2 change.
The category path and the v2.1 case mix must still reproduce it exactly on the same seeds.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import parameter_sets
from cardiac_capacity.casemix import DEFAULT_CASEMIX
from cardiac_capacity_planner import scenarios

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "golden" / "v21.json").read_text())
RATES = parameter_sets.get("literature").cicu_rates()
BASE = cp.PolicyParams(
    slots=5, beds=10, weekly_referrals=6.0, initial_backlog=60, deterioration_rates=RATES
)
CONFIGS = {
    "category_default": cp.PolicyParams(),
    "category_literature": BASE,
    "casemix_literature": replace(BASE, casemix=DEFAULT_CASEMIX),
    "casemix_settled_surge": replace(
        BASE,
        casemix=DEFAULT_CASEMIX,
        start_mode="settled",
        slots=7,
        beds=12,
        surge_beds=1,
        warmup_weeks=20,
    ),
    "category_longwait": replace(BASE, long_wait_or=1.49),
}


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_v21_run_metrics_unchanged(name: str) -> None:
    for seed, expected in GOLDEN["runs"][name].items():
        got = asdict(cp.run_metrics(CONFIGS[name], 52, int(seed)))
        for key, value in expected.items():
            assert got[key] == pytest.approx(value), (name, seed, key)


def test_v21_summary_outcome_unchanged() -> None:
    o = scenarios.evaluate(replace(BASE, casemix=None), scenarios.options(5, 10, 2)[0], 0, 0)
    got = asdict(o)
    got.pop("option")
    for key, value in GOLDEN["evaluate_nothing"].items():
        assert got[key] == pytest.approx(value), key
