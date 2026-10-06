"""Presentation of cardiac-capacity results: status labels, colours, copy.

Every number shown comes from ``cardiac_capacity``; nothing here simulates. State is carried
by an explicit text label first; colour only reinforces it.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardiac_capacity import Distribution
from cardiac_capacity.recommend_cicu import CicuRecommendation
from cardiac_capacity_planner import brand as tokens

TEAL = tokens.TEAL
INK = tokens.CANVAS

# NON-BRAND semantic constants. The identity has one accent and no red or amber on
# purpose; these are this app's own states, kept local. Always paired with a label.
RED = "#b3402f"
AMBER = "#c98a1b"

WARD_CATEGORIES = [f"Cat {i}" for i in range(1, 6)]  # 1 = most urgent
CICU_CATEGORIES = ["Urgent", "Emergency", "Semi-urgent", "Routine"]


@dataclass(frozen=True)
class StatusView:
    label: str
    colour: str
    directive: str


def breach_status(at_target: Distribution, target_week: int) -> StatusView:
    """Classify the 26-week breach distribution at the target week across Monte Carlo runs."""
    if at_target.p95 == 0:
        return StatusView(
            "Stable",
            TEAL,
            f"No patient waits 26+ weeks at week {target_week} in 95 % of runs.",
        )
    if at_target.p50 == 0:
        return StatusView(
            "At risk",
            AMBER,
            f"Most runs clear the 26-week list by week {target_week}, "
            f"but the worst 5 % still hold {at_target.p95:.0f}+ patients.",
        )
    return StatusView(
        "Breaching",
        RED,
        f"The median run still has {at_target.p50:.0f} patients waiting 26+ weeks "
        f"at week {target_week}.",
    )


def cicu_status(peak_occupancy: float, beds: float, final_urgent: float) -> StatusView:
    """Mirror the v1 capacity criteria: urgent cleared and occupancy within beds."""
    if final_urgent == 0 and peak_occupancy <= beds:
        return StatusView("Within capacity", TEAL, "Urgent list cleared; CICU load within beds.")
    if final_urgent == 0:
        return StatusView(
            "Over CICU beds",
            AMBER,
            f"Urgent list cleared, but estimated CICU load peaks at {peak_occupancy:.1f} "
            f"against {beds:g} beds.",
        )
    return StatusView(
        "Urgent backlog",
        RED,
        f"{final_urgent:g} urgent patients still waiting at the end of the horizon.",
    )


def plan_status(rec: CicuRecommendation, target: float) -> StatusView:
    """Status of the v2 CICU recommendation: a plan that holds, or none."""
    if not rec.found or rec.check is None:
        return StatusView(
            "No feasible plan",
            RED,
            "No plan in the search keeps the list stable inside the occupancy target. "
            "More beds or fewer referrals would be needed.",
        )
    lo, _hi = rec.check.ci
    if lo >= rec.threshold:
        return StatusView(
            "Plan holds",
            TEAL,
            f"The recommended plan met every condition in {rec.check.p_ok:.0%} of fresh years "
            f"(at least {lo:.0%} at the low end of the interval).",
        )
    return StatusView(
        "Plan likely holds",
        AMBER,
        f"The recommended plan met every condition in {rec.check.p_ok:.0%} of fresh years, but the "
        f"interval reaches below the {rec.threshold:.0%} threshold.",
    )


def band_text(d: Distribution, fmt: str = "{:.0f}") -> str:
    """'p50 (p5–p95)' in one short string."""
    return f"{fmt.format(d.p50)} ({fmt.format(d.p5)}–{fmt.format(d.p95)})"
