"""Stress-test library (what-if station 6): five ready-made synthetic shocks, run on the what-if engine.

Presets are separate data. They add no default event anywhere, so every earlier result is unchanged.
Each report uses ADEMP wording (Morris et al. 2019): aims, data, estimands, methods, performance.
It shows ranges (median and 5th to 95th percentile), never a point forecast. Synthetic data only.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import whatif

DISCLAIMER = (
    "Research and demonstration software. Not a medical device and not intended for clinical "
    "decision-making, diagnosis or treatment. Uses synthetic data only. Results are ranges of "
    "possible futures, not a forecast."
)


@dataclass(frozen=True)
class Preset:
    key: str
    title: str
    story: str  # one plain sentence, all synthetic
    events: tuple[cp.Event, ...]


# Spec section 2, example questions 1 to 5.
PRESETS: tuple[Preset, ...] = (
    Preset(
        "beds_blocked",
        "Three beds blocked",
        "Three CICU beds are blocked from week 2 for an unknown time (2 to 6 weeks).",
        (cp.Event("block_beds", 3, start_week=2, duration_weeks=2, duration_max_weeks=6),),
    ),
    Preset(
        "anaesthetist_leaves",
        "Anaesthetist resigns",
        "Theatre slots drop from 5 to 3 for 6 weeks from week 1.",
        (cp.Event("cut_theatre", 3, start_week=1, duration_weeks=6),),
    ),
    Preset(
        "outbreak",
        "Infection outbreak",
        "An outbreak closes 4 beds for 2 to 4 weeks from week 2.",
        (cp.Event("block_beds", 4, start_week=2, duration_weeks=2, duration_max_weeks=4),),
    ),
    Preset(
        "referral_surge",
        "Referral surge",
        "3 extra urgent cases a week for 4 weeks from week 1.",
        (cp.Event("extra_arrivals", 3, start_week=1, duration_weeks=4, urgency=1),),
    ),
    Preset(
        "theatre_closed",
        "Theatre closed",
        "Theatre is closed for 2 weeks from week 3.",
        (cp.Event("cut_theatre", 0, start_week=3, duration_weeks=2),),
    ),
)


def get_preset(key: str) -> Preset:
    for p in PRESETS:
        if p.key == key:
            return p
    raise KeyError(f"No stress test called {key!r}. Choose one of: {', '.join(p.key for p in PRESETS)}.")


def run_preset(
    key: str,
    params: cp.PolicyParams,
    weeks: int = whatif.DEFAULT_WEEKS,
    runs: int = whatif.DEFAULT_RUNS,
    seed0: int = whatif.SEED0,
) -> whatif.WhatIfResult:
    """Run one preset against ``params`` (baseline and shock on the same seeds)."""
    return whatif.run_whatif(params, get_preset(key).events, weeks, runs, seed0)


def _range(d) -> str:
    return f"{d.p50:.1f} (range {d.p5:.1f} to {d.p95:.1f})"


def ademp_report(preset: Preset, result: whatif.WhatIfResult) -> str:
    """Plain ADEMP text. Every number comes from ``result``; nothing is typed by hand."""
    lines = [
        f"## {preset.title}",
        f"Aims: show what happens to the service if this occurs. {preset.story}",
        "Data: a synthetic service and published-literature defaults. No patient data.",
        "Estimands: difference between the shock and the normal case on the same seeds, for each measure below.",
        f"Methods: {result.runs} simulated runs of {result.weeks} weeks; same seeds for both cases; "
        "an unknown length is drawn from its range in each run.",
        "Performance: median and 5th to 95th percentile band.",
    ]
    for m in result.measures:
        lines.append(
            f"- {m.label} ({m.unit}): normal {_range(m.baseline)}; with shock {_range(m.scenario)}; "
            f"difference {_range(m.difference)}; {m.verdict}."
        )
    lines.append(DISCLAIMER)
    return "\n".join(lines)
