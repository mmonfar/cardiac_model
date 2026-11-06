"""What-if runner (station 2): baseline and scenario on the same seeds, with ranges and the difference.

A range of possible futures, not a forecast. Results are medians with a 5th to 95th percentile band.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity.montecarlo import Distribution, summarize

DEFAULT_WEEKS = 26
DEFAULT_RUNS = 30
SEED0 = 500  # same seeds for baseline and scenario

# (field, plain label, unit)
MEASURES = (
    ("list_end", "Waiting list at the end", "children"),
    ("det_events", "Children who got worse while waiting", "children"),
    ("mean_occupancy", "Average share of beds in use", "share"),
    ("days_full", "Days with every bed taken", "share of days"),
    ("cat1_unserved_days", "Urgent days without a bed or slot", "days"),
)


@dataclass(frozen=True)
class MeasureResult:
    field: str
    label: str
    unit: str
    baseline: Distribution
    scenario: Distribution
    difference: Distribution  # scenario minus baseline, paired by seed

    @property
    def verdict(self) -> str:
        """Plain words: does the whole 90 % band of the difference sit on one side of zero?"""
        if self.difference.p5 > 0:
            return "worse"
        if self.difference.p95 < 0:
            return "better"
        return "no clear change"


@dataclass(frozen=True)
class WhatIfResult:
    events: tuple[cp.Event, ...]
    weeks: int
    runs: int
    seed0: int
    measures: tuple[MeasureResult, ...]

    def get(self, field: str) -> MeasureResult:
        for m in self.measures:
            if m.field == field:
                return m
        raise KeyError(field)


def check_events(events: tuple[cp.Event, ...]) -> None:
    """Refuse an empty or wrong scenario with a plain message."""
    if not events:
        raise ValueError("Add at least one event to run a what-if.")
    for e in events:
        if not isinstance(e, cp.Event):
            raise ValueError("Each event must be an Event.")


def run_whatif(
    params: cp.PolicyParams,
    events: tuple[cp.Event, ...],
    weeks: int = DEFAULT_WEEKS,
    runs: int = DEFAULT_RUNS,
    seed0: int = SEED0,
) -> WhatIfResult:
    """Run the plan without events (baseline) and with ``events`` (scenario) on the same seeds."""
    check_events(events)
    if not 1 <= weeks <= 520:
        raise ValueError("Weeks must be from 1 to 520.")
    if runs < 2:
        raise ValueError("Use at least 2 runs to show a range.")
    base_p = replace(params, events=())
    scen_p = replace(params, events=tuple(params.events) + tuple(events))
    base = cp.replicate(base_p, weeks, runs, seed0)
    scen = cp.replicate(scen_p, weeks, runs, seed0)
    out = []
    for field, label, unit in MEASURES:
        b = [float(getattr(r, field)) for r in base]
        s = [float(getattr(r, field)) for r in scen]
        out.append(
            MeasureResult(
                field, label, unit, summarize(b), summarize(s), summarize([y - x for x, y in zip(b, s)])
            )
        )
    return WhatIfResult(tuple(events), weeks, runs, seed0, tuple(out))


def verdict_line(result: WhatIfResult) -> str:
    """One plain sentence for the top of the results screen."""
    m = result.get("list_end")
    d = m.difference
    if m.verdict == "no clear change":
        return "The waiting list at the end is not clearly different from the normal case."
    word = "longer" if m.verdict == "worse" else "shorter"
    return (
        f"The waiting list at the end is {word} than normal: about {abs(d.p50):.0f} children "
        f"(range {d.p5:.0f} to {d.p95:.0f})."
    )
