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
        cat1_waits=float(np.mean(arr("cat1_unserved_days") > 0)),
        staffing=text,
        staffing_ok=ok,
        extra_sessions_needed=ds,
        extra_beds_needed=db,
    )


def recommend(outcomes: list[Outcome]) -> Outcome | None:
    """The smallest change that stops the list growing; staffing-ok changes first.

    Order of preference is the order of ``options`` (sessions, then beds, then both), and an
    option inside the staffing cap wins over one outside it. ``None`` if nothing helps.
    """
    levers = outcomes[1:]
    helps = [o for o in levers if o.stops_growth]
    inside = [o for o in helps if o.staffing_ok]
    if inside:
        return inside[0]
    return helps[0] if helps else None


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
