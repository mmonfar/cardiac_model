# ruff: noqa: E501  (plain-language page text)
"""What-if helpers for the screens: plain sentences, events from the answers, the log file, results for the log.

No simulation here: ``cardiac_capacity.whatif`` and ``whatif_recommend`` do the runs; the decision log is
``cardiac_capacity.decision_log``. Synthetic data only.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import cardiac_capacity
from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import diagnoses, whatif
from cardiac_capacity.decision_log import Entry

# The service the what-if starts from: the same defaults as the Decision summary page.
SLOTS, BEDS, BACKLOG, REFERRALS = 5, 10, 60, 6.0

URGENCY = {None: "Usual mix", 1: "Life-threatening", 2: "Urgent", 3: "Semi-urgent", 4: "Routine"}

# card key -> (button label, one-line help, event kind, level in the log)
CARDS = {
    "beds": ("Beds blocked", "Some CICU beds are not usable for a while.", "block_beds", "operational"),
    "theatre": ("Theatre cut", "Fewer operations a week, or none.", "cut_theatre", "tactical"),
    "outbreak": ("Outbreak", "Infection closes beds for a few weeks.", "block_beds", "operational"),
    "referrals": ("More referrals", "More new children arrive each week.", "extra_arrivals", "tactical"),
    "other": ("Something else", "Set up any of the three changes yourself.", "", "tactical"),
}
KIND_NAMES = {
    "block_beds": "Beds blocked",
    "cut_theatre": "Theatre cut",
    "extra_arrivals": "More referrals",
}


@dataclass(frozen=True)
class Answers:
    """What the manager typed on the 'Tell me more' screen."""

    kind: str
    amount: float
    start_week: int
    weeks_min: int
    weeks_max: int  # equal to weeks_min when the length is known
    urgency: int | None = None


def plan_label(slots: int, surge: bool) -> str:
    return f"{slots} elective cases a week" + (" with the extra (surge) bed open" if surge else "")


def base_params() -> cp.PolicyParams:
    mix = diagnoses.build_mix({})
    return cp.PolicyParams(
        slots=SLOTS,
        beds=BEDS,
        weekly_referrals=REFERRALS,
        initial_backlog=BACKLOG,
        deterioration_rates=(0.0, 0.0, 0.0, 0.0),
        casemix=mix.casemix,
    )


def make_event(a: Answers) -> cp.Event:
    """Build the engine event. The engine refuses out-of-range input with a plain message (ValueError)."""
    top = a.weeks_max if a.weeks_max != a.weeks_min else None
    if top is not None and top < a.weeks_min:
        raise ValueError("The longest time cannot be shorter than the shortest time.")
    return cp.Event(
        a.kind, a.amount, a.start_week, a.weeks_min, top, a.urgency if a.kind == "extra_arrivals" else None
    )


def when_text(a: Answers) -> str:
    start = "from the start" if a.start_week == 0 else f"from week {a.start_week}"
    if a.weeks_max != a.weeks_min:
        return f"{start}, for {a.weeks_min} to {a.weeks_max} weeks"
    return f"{start}, for {a.weeks_min} week{'s' if a.weeks_min != 1 else ''}"


def sentence(a: Answers) -> str:
    """One plain sentence that says what will be tested."""
    n = int(a.amount) if a.amount == int(a.amount) else a.amount
    if a.kind == "block_beds":
        what = f"{n} CICU bed{'s' if n != 1 else ''} blocked"
    elif a.kind == "cut_theatre":
        what = "Theatre closed" if n == 0 else f"Theatre cut to {n} operation{'s' if n != 1 else ''} a week"
    else:
        what = f"{n} extra new referral{'s' if n != 1 else ''} a week"
        if a.urgency:
            what += f" ({URGENCY[a.urgency].lower()})"
    return f"{what}, {when_text(a)}."


def fmt(field: str, v: float) -> str:
    if field in ("mean_occupancy", "days_full"):
        return f"{v * 100:.0f}%"
    return f"{v:.0f}"


def change_text(field: str, d: object) -> str:
    """Median change with the 5th to 95th percentile band, as plain words."""
    p5, p50, p95 = d.p5, d.p50, d.p95  # type: ignore[attr-defined]
    def n(v: float) -> str:
        t = f"{v:+.0f}"
        return "0" if t in ("+0", "-0") else t

    if field in ("mean_occupancy", "days_full"):
        return f"{n(p50 * 100)} points (range {n(p5 * 100)} to {n(p95 * 100)})"
    return f"{n(p50)} (range {n(p5)} to {n(p95)})"


VERDICT_WORDS = {"worse": "Worse", "better": "Better", "no clear change": "No clear change"}


def results_for_log(result: whatif.WhatIfResult) -> dict:
    return {
        "weeks": result.weeks,
        "runs": result.runs,
        "measures": [
            {
                "measure": m.label,
                "normal_median": round(m.baseline.p50, 3),
                "case_median": round(m.scenario.p50, 3),
                "change_p5": round(m.difference.p5, 3),
                "change_median": round(m.difference.p50, 3),
                "change_p95": round(m.difference.p95, 3),
                "verdict": m.verdict,
            }
            for m in result.measures
        ],
    }


def log_path() -> str:
    """Local file only. ``CARDIAC_WHATIF_LOG`` overrides it (tests, demos)."""
    env = os.environ.get("CARDIAC_WHATIF_LOG")
    p = Path(env) if env else Path.home() / ".cardiac_planner" / "decision_log.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


def make_entry(
    name: str,
    question: str,
    events: tuple[cp.Event, ...],
    level: str,
    result: whatif.WhatIfResult,
    choice: str,
    why: str,
    review_date: str | None,
) -> Entry:
    return Entry(
        asker=name,
        question=question,
        events=[asdict(e) for e in events],
        model_version=cardiac_capacity.__version__,
        parameter_set="literature",
        seeds=f"{result.seed0} to {result.seed0 + result.runs - 1}",
        results=results_for_log(result),
        decision_choice=choice,
        decision_by=name,
        decision_why=why,
        level=level,
        review_date=review_date,
    )
