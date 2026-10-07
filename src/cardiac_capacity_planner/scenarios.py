"""The decision summary's arithmetic: compare "do nothing" with the levers, check staffing.

Pure functions over ``cardiac_capacity.cicu_policy`` results (no Streamlit), so the page is thin
and the logic is testable. Levers: more theatre sessions, more CICU beds, both. Staffing is a
constraint on the levers, not a lever with its own model: a figure is only as good as the cap
the user enters, and with no cap entered staffing is reported as "not limiting".
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from cardiac_capacity import cicu_policy as cp

WEEKS = 52
N_RUNS = 60
SEED0 = 5_000


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    slots: int
    beds: int


@dataclass(frozen=True)
class Outcome:
    option: Option
    list_start: float
    list_end: float
    list_end_lo: float
    list_end_hi: float
    cancelled: float
    worsen: float
    worsen_lo: float
    worsen_hi: float
    occupancy: float
    over_26_end: float
    p_list_shrinks: float
    weeks_at_limit: float  # share of weeks the beds open to planned operations were all taken
    elective_beds: int  # beds open to planned operations (the comfortable level x beds)
    cat1_waits: float  # share of runs where a life-threatening case waited for a bed
    staffing: str
    staffing_ok: bool
    extra_sessions_needed: int
    extra_beds_needed: int

    @property
    def stops_growth(self) -> bool:
        return self.list_end <= self.list_start


def options(slots: int, beds: int, step: int) -> list[Option]:
    return [
        Option("nothing", "Do nothing", slots, beds),
        Option("sessions", f"Add {step} theatre sessions a week", slots + step, beds),
        Option("beds", f"Add {step} CICU beds", slots, beds + step),
        Option(
            "both",
            f"Add {step} theatre sessions and {step} CICU beds",
            slots + step,
            beds + step,
        ),
    ]


def staffing_check(
    opt: Option, staffed_sessions: int, staffed_beds: int
) -> tuple[str, bool, int, int]:
    """Status text, ok flag, extra staffed sessions needed, extra staffed beds needed.

    A cap of 0 means "not entered": staffing is then reported as not limiting.
    """
    if staffed_sessions <= 0 and staffed_beds <= 0:
        return "Not set (not limiting)", True, 0, 0
    ds = max(0, opt.slots - staffed_sessions) if staffed_sessions > 0 else 0
    db = max(0, opt.beds - staffed_beds) if staffed_beds > 0 else 0
    if ds == 0 and db == 0:
        return "Within your staffing", True, 0, 0
    parts = []
    if ds:
        parts.append(f"{ds} more staffed session{'s' if ds > 1 else ''}")
    if db:
        parts.append(f"{db} more staffed bed{'s' if db > 1 else ''}")
    return "Needs " + " and ".join(parts), False, ds, db


def _weeks_at_limit(pol: cp.PolicyParams, n: int = 20) -> float:
    """Share of weeks in which the beds open to planned operations were all taken at some point.

    Planned operations are cancelled when those beds are full, even if average occupancy is low.
    """
    hit = 0
    total = 0
    for i in range(n):
        f = cp.run_frame(pol, WEEKS, SEED0 + i).dropna(subset=["occupancy_peak"])
        hit += int((f["occupancy_peak"] >= pol.elective_limit - 1e-9).sum())
        total += len(f)
    return hit / total if total else 0.0


def evaluate(
    base: cp.PolicyParams, opt: Option, staffed_sessions: int, staffed_beds: int
) -> Outcome:
    pol = replace(base, slots=opt.slots, beds=opt.beds, surge_beds=0)
    ms = cp.replicate(pol, WEEKS, N_RUNS, SEED0)

    def arr(name: str) -> np.ndarray:
        return np.array([getattr(m, name) for m in ms], dtype=float)

    end, det = arr("list_end"), arr("det_events")
    text, ok, ds, db = staffing_check(opt, staffed_sessions, staffed_beds)
    return Outcome(
        option=opt,
        list_start=float(np.median(arr("list_start"))),
        list_end=float(np.median(end)),
        list_end_lo=float(np.percentile(end, 5)),
        list_end_hi=float(np.percentile(end, 95)),
        cancelled=float(np.median(arr("cancellations"))),
        worsen=float(np.median(det)),
        worsen_lo=float(np.percentile(det, 5)),
        worsen_hi=float(np.percentile(det, 95)),
        occupancy=float(np.median(arr("mean_occupancy"))),
        over_26_end=float(np.median(arr("over_26_end"))),
        p_list_shrinks=float(np.mean(end <= arr("list_start"))),
        weeks_at_limit=_weeks_at_limit(pol),
        elective_beds=pol.elective_limit,
        cat1_waits=float(np.mean(arr("cat1_unserved_days") > 0)),
        staffing=text,
        staffing_ok=ok,
        extra_sessions_needed=ds,
        extra_beds_needed=db,
    )


CANCEL_TOLERANCE = 2  # extra cancelled operations a year that still count as "no worse"


def cancels_ok(now: Outcome, o: Outcome) -> bool:
    """True if the option does not raise cancellations above do-nothing (plus the tolerance)."""
    return o.cancelled <= now.cancelled + CANCEL_TOLERANCE


def recommend(outcomes: list[Outcome]) -> Outcome | None:
    """The smallest change that stops the list growing without raising cancellations.

    Order of preference is the order of ``options`` (sessions, beds, both); an option inside the
    staffing cap wins over one outside it. If every list-stopping option raises cancellations
    above do-nothing (by more than ``CANCEL_TOLERANCE``), the one with the fewest cancellations is
    recommended and ``tradeoff`` names the cost. ``None`` if nothing stops the list growing.
    """
    now = outcomes[0]
    helps = [o for o in outcomes[1:] if o.stops_growth]
    if not helps:
        return None
    clean = [o for o in helps if cancels_ok(now, o)]
    pool = clean or sorted(helps, key=lambda o: (o.cancelled, o.list_end))[:1]
    inside = [o for o in pool if o.staffing_ok]
    return (inside or pool)[0]


def tradeoff(outcomes: list[Outcome], pick: Outcome) -> str:
    """Plain-language trade-off when the recommendation raises cancellations, else empty."""
    now = outcomes[0]
    if cancels_ok(now, pick):
        return ""
    text = (
        f"This also raises cancelled operations from {now.cancelled:.0f} to {pick.cancelled:.0f} "
        "a year, because the beds become the limit."
    )
    safer = [o for o in outcomes[1:] if o is not pick and o.stops_growth and cancels_ok(now, o)]
    if safer:
        o = safer[0]
        text += f" {o.option.label} keeps cancellations at {o.cancelled:.0f}."
    return text


def weekly_list(base: cp.PolicyParams, opt: Option, n: int = 40) -> tuple[list[int], ...]:
    """Median and 5th-95th percentile of the waiting list by week, over ``n`` seeded runs."""
    pol = replace(base, slots=opt.slots, beds=opt.beds, surge_beds=0)
    lists = np.array(
        [cp.run_frame(pol, WEEKS, SEED0 + i)["list"].to_numpy() for i in range(n)], dtype=float
    )
    return (
        list(range(lists.shape[1])),
        [float(x) for x in np.median(lists, axis=0)],
        [float(x) for x in np.percentile(lists, 5, axis=0)],
        [float(x) for x in np.percentile(lists, 95, axis=0)],
    )
