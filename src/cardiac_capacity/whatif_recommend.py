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
# What "safe" means on screen 5. One sentence, shown once, so the word is never left to the reader.
SAFE_MEANING = "Safe here means: no worse than the normal case on every check."
# Tolerance when a plan's rate is compared with the normal case: none. Both are run on the same seeds
# (same futures), so the comparison is paired and a plain "<=" is exact; only float rounding is allowed for.
_EPS = 1e-9


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
    safe: bool = False  # no worse than the normal case on every check


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


def worse_than_normal(plan_rates: dict[str, float], normal_rates: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Checks where the plan fails in more futures than the normal case: name -> (plan rate, normal rate).

    Empty means safe. The normal case itself is always safe by this test.
    """
    return {k: (r, normal_rates[k]) for k, r in plan_rates.items() if r > normal_rates[k] + _EPS}


@dataclass(frozen=True)
class _Tried:
    e: rc.PlanEval
    worse: dict[str, tuple[float, float]]


def _try(scen: cp.PolicyParams, normal_rates: dict[str, float], slots: int, surge: bool, weeks: int, runs: int, seed0: int) -> _Tried:
    e = rc.evaluate_plan(scen, slots, surge, weeks, runs, seed0)
    ms = cp.replicate(scen.with_plan(slots, surge), weeks, runs, seed0)
    return _Tried(e, worse_than_normal(rc.failure_reasons(ms, scen), normal_rates))


def _option(rank: int, t: _Tried) -> Option:
    e = t.e
    verdict = "no worse than the normal case on every check" if not t.worse else "worse than the normal case on some checks"
    text = (
        f"{_label(e.slots, e.surge)}: {verdict}; "
        f"about {e.det_mean:.0f} children get worse while waiting; list ends near {e.list_end_mean:.0f}."
    )
    return Option(rank, e.slots, e.surge, e.p_ok, e.det_mean, e.list_end_mean, text, e.det_p50, e.list_end_p50, not t.worse)


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

    A plan is safe when it is no worse than the normal case (``params`` without the events, current plan, same
    seeds) on every check: list grew, unit above the occupancy target, a life-threatening case waited for a bed.
    """
    check_events(events)
    scen = replace(params, events=tuple(params.events) + tuple(events))
    lo, hi = scen.slots, scen.slots + MAX_EXTRA_CASES
    kw: dict[str, object] = {"n_select": runs, "seed_select": seed0, "min_slots": lo, "max_slots": hi}
    kw.update(recommend_kwargs)
    rec = rc.recommend(scen, weeks=weeks, **kw)  # type: ignore[arg-type]
    n = rec.n_select
    normal = params.with_plan(params.slots, params.surge_beds > 0)
    normal_rates = rc.failure_reasons(cp.replicate(normal, weeks, n, seed0), normal)
    now = _try(scen, normal_rates, scen.slots, scen.surge_beds > 0, weeks, n, seed0)
    do_nothing = _option(0, now)
    pools = (False, True) if kw.get("consider_surge", True) else (False,)
    tried = [_try(scen, normal_rates, s, sg, weeks, n, seed0) for sg in pools for s in range(lo, hi + 1)]
    safe = sorted((t for t in tried if not t.worse), key=lambda t: (t.e.det_mean, t.e.slots, t.e.surge))
    if not safe:
        be = min(tried, key=lambda t: (len(t.worse), sum(r - b for r, b in t.worse.values()), t.e.det_mean, t.e.slots))
        why = ", ".join(f"{k} in {r:.0%} of futures (normal case {b:.0%})" for k, (r, b) in be.worse.items())
        msg = (
            f"No safe plan found within {hi} elective cases a week (tried {lo} to {hi}, with and without the extra bed). "
            f"{SAFE_MEANING} The closest is {_label(be.e.slots, be.e.surge)}; it is worse than the normal case on: {why}."
        )
        return Recovery(False, (), do_nothing, _option(0, be), rec, msg)
    options = tuple(_option(i + 1, t) for i, t in enumerate(safe[:MAX_OPTIONS]))
    top = options[0]
    msg = (
        f"{SAFE_MEANING} Best safe plan: {_label(top.slots, top.surge)}; about {top.worsen_mean:.0f} children get worse "
        f"while waiting and the list ends near {top.list_end_mean:.0f}."
    )
    return Recovery(True, options, do_nothing, None, rec, msg)
