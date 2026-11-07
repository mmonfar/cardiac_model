"""Recovery options for a what-if scenario (station 4): reuse ``recommend`` on the scenario.

Every sentence comes from a run. When no plan works, the answer says so.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import recommend_cicu as rc
from cardiac_capacity.whatif import check_events

MAX_OPTIONS = 3
# Real capacity limit: a theatre list grows by whole cases on the five theatre days, so the search tries the
# current plan and up to this many extra cases a week, one at a time (never a jump from 5 to 15).
MAX_EXTRA_CASES = 3


@dataclass(frozen=True)
class Option:
    rank: int
    slots: int
    surge: bool
    share_ok: float  # share of simulated futures that meet every condition
    worsen_mean: float  # children who get worse while waiting, mean
    list_end_mean: float
    text: str
    worsen_p50: float = 0.0  # median over the same seeds as the what-if screen
    list_end_p50: float = 0.0


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
    return Option(rank, e.slots, e.surge, e.p_ok, e.det_mean, e.list_end_mean, text, e.det_p50, e.list_end_p50)


def recover(
    params: cp.PolicyParams,
    events: tuple[cp.Event, ...],
    weeks: int = 26,
    runs: int = 30,
    seed0: int = 500,
    **recommend_kwargs: object,
) -> Recovery:
    """Rank recovery plans for ``params`` plus ``events``.

    ``weeks``, ``runs`` and ``seed0`` are the scenario of the what-if run: the plans are tried on the same
    futures, so the current plan here equals the "your case" figures there. The search goes from the current
    number of cases a week up to ``MAX_EXTRA_CASES`` more, one case at a time. Extra keywords go to ``recommend``.
    """
    check_events(events)
    scen = replace(params, events=tuple(params.events) + tuple(events))
    lo, hi = scen.slots, scen.slots + MAX_EXTRA_CASES
    kw: dict[str, object] = {"n_select": runs, "seed_select": seed0, "min_slots": lo, "max_slots": hi}
    kw.update(recommend_kwargs)
    rec = rc.recommend(scen, weeks=weeks, **kw)  # type: ignore[arg-type]
    now = rc.evaluate_plan(scen, scen.slots, scen.surge_beds > 0, weeks, rec.n_select, seed0)
    do_nothing = _option(0, now)
    if not rec.found:
        pools = (False, True) if kw.get("consider_surge", True) else (False,)
        tried = [rc.evaluate_plan(scen, s, sg, weeks, rec.n_select, seed0) for sg in pools for s in range(lo, hi + 1)]
        be = max(tried, key=lambda e: (e.p_ok, -e.det_mean, -e.slots))
        fails = rc.failure_reasons(cp.replicate(scen.with_plan(be.slots, be.surge), weeks, rec.n_select, seed0), scen)
        why = ", ".join(f"{k} in {v:.0%}" for k, v in sorted(fails.items(), key=lambda kv: -kv[1]) if v > 0)
        msg = (
            f"No safe plan found within {hi} elective cases a week (tried {lo} to {hi}, with and without the extra bed). "
            f"The closest is {_label(be.slots, be.surge)}; it meets every condition in {be.p_ok:.0%} of possible futures."
            + (f" What stops it: {why} of futures." if why else "")
        )
        return Recovery(False, (), do_nothing, _option(0, be), rec, msg)
    good = sorted(
        (e for e in rec.table if e.complete and e.p_ok >= rec.threshold),
        key=lambda e: (e.det_mean, e.slots, e.surge),
    )
    # The recommended plan first, then the next best different plans.
    chosen = rec.plan
    ordered = ([chosen] if chosen is not None else []) + [e for e in good if e is not chosen]
    options = tuple(_option(i + 1, e) for i, e in enumerate(ordered[:MAX_OPTIONS]))
    return Recovery(True, options, do_nothing, None, rec, rc.plain_words(rec, scen))
