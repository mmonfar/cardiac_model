"""Recovery options for a what-if scenario (station 4): reuse ``recommend`` on the scenario.

Every sentence comes from a run. When no plan works, the answer says so.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import recommend_cicu as rc
from cardiac_capacity.whatif import check_events

MAX_OPTIONS = 3
NO_PLAN = "No safe plan found. No option in the search keeps the list stable, the unit within its target and urgent cases served."


@dataclass(frozen=True)
class Option:
    rank: int
    slots: int
    surge: bool
    share_ok: float  # share of simulated futures that meet every condition
    worsen_mean: float  # children who get worse while waiting, mean
    list_end_mean: float
    text: str


@dataclass(frozen=True)
class Recovery:
    found: bool
    options: tuple[Option, ...]
    do_nothing: Option  # the current plan, under the scenario
    best_effort: Option | None  # closest plan when none is safe
    recommendation: rc.CicuRecommendation
    message: str


def _label(slots: int, surge: bool) -> str:
    return f"{slots} elective cases a week" + (" with the extra (surge) bed open" if surge else "")


def _option(rank: int, e: rc.PlanEval) -> Option:
    text = (
        f"{_label(e.slots, e.surge)}: meets every condition in {e.p_ok:.0%} of simulated futures; "
        f"about {e.det_mean:.0f} children get worse while waiting; list ends near {e.list_end_mean:.0f}."
    )
    return Option(rank, e.slots, e.surge, e.p_ok, e.det_mean, e.list_end_mean, text)


def recover(
    params: cp.PolicyParams,
    events: tuple[cp.Event, ...],
    weeks: int = 26,
    **recommend_kwargs: object,
) -> Recovery:
    """Rank recovery plans for ``params`` plus ``events``. Extra keywords go to ``recommend``."""
    check_events(events)
    scen = replace(params, events=tuple(params.events) + tuple(events))
    rec = rc.recommend(scen, weeks=weeks, **recommend_kwargs)  # type: ignore[arg-type]
    n = rec.n_select
    now = rc.evaluate_plan(scen, scen.slots, scen.surge_beds > 0, weeks, n, rc.SEED_SELECT)
    do_nothing = _option(0, now)
    if not rec.found:
        be = rec.best_effort
        return Recovery(False, (), do_nothing, None if be is None else _option(0, be), rec, NO_PLAN)
    good = sorted(
        (e for e in rec.table if e.complete and e.p_ok >= rec.threshold),
        key=lambda e: (e.det_mean, e.slots, e.surge),
    )
    # The recommended plan first, then the next best different plans.
    chosen = rec.plan
    ordered = ([chosen] if chosen is not None else []) + [e for e in good if e is not chosen]
    options = tuple(_option(i + 1, e) for i, e in enumerate(ordered[:MAX_OPTIONS]))
    return Recovery(True, options, do_nothing, None, rec, rc.plain_words(rec, scen))
