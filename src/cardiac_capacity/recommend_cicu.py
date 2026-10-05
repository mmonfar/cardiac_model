# ruff: noqa: E501  (long prose in docstrings and plain-language strings)
"""CICU recommendation v2: clear the routine list, keep the unit at a safe occupancy, life-threatening first.

Replaces the inherited urgent-only criterion  for the v2 CICU planner; v1 is untouched .

The decision is a plan: elective cases per week (``slots``) and whether to open a surge bed.

Objective: minimise expected deterioration events and waiting-list growth, subject to the
occupancy target, with life-threatening cases first. Weights between harms are not defensible without a
clinician (Kochenderfer and Wheeler, *Algorithms for Optimization*, pp. 231-241), so this is an
epsilon-constraint formulation, not a weighted sum:

- **Feasible run** = all of: the list at the end of the horizon is no more than the list at the start plus
  ``growth_tolerance`` (stable or shrinking); mean occupancy of the base beds is at or below the target; no
  life-threatening case ever waited for a bed (``cat1_unserved_days == 0``).
- **Feasible plan** = share of feasible runs over futures at least ``threshold`` (default 90%).
- **Choice** = among feasible plans, the one with the fewest expected deterioration events; ties go to the
  fewest slots within one standard error of the best (the one-standard-error rule: a cheaper plan is preferred
  when it is statistically indistinguishable from the best).
- **Surge bed** is recommended when it is the only way to a feasible plan. If the user sets a cap on the bed-days
  they would open per deterioration avoided (no published threshold exists, so there is no default cap), it is
  also recommended when it lowers expected deterioration events with a paired 95% interval strictly below zero
  and costs no more than the cap. Its cost is always reported as bed-days opened (7 per week) against
  deterioration events avoided.

Selection seeds, validation seeds and the 30-seed check use disjoint seed blocks, so the reported success rate
is out of sample. The Wilson 95% interval is the company rule.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity.stats import mean_ci, wilson_interval

DEFAULT_THRESHOLD = 0.90
SEED_SELECT = 20_000
SEED_VALIDATE = 60_000
SEED_CHECK = 90_000


def growth_tolerance(params: cp.PolicyParams) -> int:
    """List growth that still counts as stable: about one week of referrals."""
    return max(1, round(params.weekly_referrals))


def run_ok(m: cp.RunMetrics, params: cp.PolicyParams, tolerance: int | None = None) -> bool:
    """Does one future meet every criterion?"""
    tol = growth_tolerance(params) if tolerance is None else tolerance
    return (
        m.growth <= tol
        and m.mean_occupancy <= params.target_occupancy + 1e-9
        and m.cat1_unserved_days == 0
    )


def failure_reasons(ms: list[cp.RunMetrics], params: cp.PolicyParams) -> dict[str, float]:
    """Share of futures failing each criterion (a run can fail several)."""
    tol = growth_tolerance(params)
    n = len(ms)
    return {
        "list grew": sum(m.growth > tol for m in ms) / n,
        "unit above the occupancy target": sum(
            m.mean_occupancy > params.target_occupancy + 1e-9 for m in ms
        )
        / n,
        "a life-threatening case waited for a bed": sum(m.cat1_unserved_days > 0 for m in ms) / n,
    }


@dataclass(frozen=True)
class PlanEval:
    slots: int
    surge: bool
    n: int
    n_ok: int
    det_mean: float
    det_se: float
    growth_mean: float
    list_end_mean: float
    occupancy_mean: float
    bed_days_opened: float  # surge bed-days opened per measured window, per run
    bed_days_used: float
    det: tuple[int, ...] = field(repr=False, default=())  # per seed, for paired differences
    complete: bool = True  # False when evaluation stopped early (cannot reach the threshold)

    @property
    def p_ok(self) -> float:
        return self.n_ok / self.n if self.n else 0.0


def evaluate_plan(
    params: cp.PolicyParams,
    slots: int,
    surge: bool,
    weeks: int,
    n: int,
    seed0: int,
    threshold: float | None = None,
) -> PlanEval:
    """Evaluate one plan on ``n`` seeds; stops early when ``threshold`` can no longer be met."""
    p = params.with_plan(slots, surge)
    tol = growth_tolerance(p)
    ok = 0
    dets: list[int] = []
    growth: list[int] = []
    lst: list[int] = []
    occ: list[float] = []
    used: list[int] = []
    opened = 0
    complete = True
    for i in range(n):
        if threshold is not None and (ok + n - i) / n < threshold - 1e-12:
            complete = False
            break
        m = cp.run_metrics(p, weeks, seed0 + i)
        ok += run_ok(m, p, tol)
        dets.append(m.det_events)
        growth.append(m.growth)
        lst.append(m.list_end)
        occ.append(m.mean_occupancy)
        used.append(m.surge_days_used)
        opened = m.surge_days_open
    k = len(dets)
    arr = np.array(dets, dtype=float)
    return PlanEval(
        slots,
        surge,
        k,
        ok,
        float(arr.mean()),
        float(arr.std(ddof=1) / math.sqrt(k)) if k > 1 else 0.0,
        float(np.mean(growth)),
        float(np.mean(lst)),
        float(np.mean(occ)),
        float(opened),
        float(np.mean(used)),
        tuple(dets),
        complete,
    )


def _choose(feasible: list[PlanEval]) -> PlanEval | None:
    """Fewest expected deterioration events; fewest slots within one standard error of the best."""
    if not feasible:
        return None
    best = min(feasible, key=lambda e: e.det_mean)
    near = [e for e in feasible if e.det_mean <= best.det_mean + best.det_se + 1e-12]
    return min(near, key=lambda e: e.slots)


@dataclass(frozen=True)
class Check:
    """An out-of-sample check of one plan on fresh seeds."""

    n: int
    n_ok: int
    p_ok: float
    ci: tuple[float, float]
    det_mean: float
    det_ci: tuple[float, float]
    det_p5: float
    det_p95: float
    list_end_mean: float
    growth_mean: float
    occupancy_mean: float
    failures: dict[str, float]
    per_seed: tuple[tuple[int, int, int, float, bool], ...]  # seed, det, growth, occupancy, ok


def check_plan(
    params: cp.PolicyParams, slots: int, surge: bool, weeks: int, n: int, seed0: int
) -> Check:
    p = params.with_plan(slots, surge)
    tol = growth_tolerance(p)
    ms = cp.replicate(p, weeks, n, seed0)
    flags = [run_ok(m, p, tol) for m in ms]
    det = np.array([m.det_events for m in ms], dtype=float)
    m_, lo, hi = (
        mean_ci(det) if n > 1 else (float(det.mean()), float(det.mean()), float(det.mean()))
    )
    k = sum(flags)
    return Check(
        n,
        k,
        k / n,
        wilson_interval(k, n),
        m_,
        (lo, hi),
        float(np.percentile(det, 5)),
        float(np.percentile(det, 95)),
        float(np.mean([m.list_end for m in ms])),
        float(np.mean([m.growth for m in ms])),
        float(np.mean([m.mean_occupancy for m in ms])),
        failure_reasons(ms, p),
        tuple(
            (seed0 + i, m.det_events, m.growth, m.mean_occupancy, f)
            for i, (m, f) in enumerate(zip(ms, flags, strict=True))
        ),
    )


@dataclass(frozen=True)
class SurgeAssessment:
    """Is the extra bed worth opening? Paired over the selection seeds."""

    considered: bool
    recommended: bool
    reason: str
    det_without: float | None
    det_with: float | None
    det_diff_ci: tuple[float, float] | None  # with minus without; negative = fewer events
    bed_days_opened: float  # per measured window
    bed_days_used: float
    bed_days_per_event_avoided: float | None


@dataclass(frozen=True)
class CicuRecommendation:
    found: bool
    slots: int | None
    surge: bool
    min_slots_feasible: (
        int | None
    )  # smallest slots meeting the threshold (no surge, or with if needed)
    threshold: float
    weeks: int
    n_select: int
    plan: PlanEval | None
    check: Check | None  # out-of-sample (validation seeds)
    seed_check: Check | None  # 30+ further seeds
    surge_assessment: SurgeAssessment
    min_plan: PlanEval | None  # the smallest feasible plan (just stops the list growing)
    best_effort: (
        PlanEval | None
    )  # when nothing is feasible: the plan with the highest success share
    table: tuple[PlanEval, ...]
    evaluations: int
    boundary: bool


def recommend(
    params: cp.PolicyParams,
    weeks: int = 52,
    threshold: float = DEFAULT_THRESHOLD,
    n_select: int = 60,
    n_validate: int = 200,
    n_seed_check: int = 30,
    max_slots: int = 15,
    consider_surge: bool = True,
    max_bed_days_per_event: float | None = None,
    seed_select: int = SEED_SELECT,
    seed_validate: int = SEED_VALIDATE,
    seed_check: int = SEED_CHECK,
) -> CicuRecommendation:
    """Search ``slots`` 1..max_slots, without and (optionally) with a surge bed."""
    if not 0 < threshold < 1:
        raise ValueError("threshold must be between 0 and 1")
    if n_seed_check < 30:
        raise ValueError("the seed-sensitivity check needs at least 30 seeds (company rule)")
    evals: list[PlanEval] = []
    n_evals = 0
    pools = (False, True) if consider_surge else (False,)
    by_pool: dict[bool, list[PlanEval]] = {}
    for surge in pools:
        rows = []
        for s in range(1, max_slots + 1):
            e = evaluate_plan(params, s, surge, weeks, n_select, seed_select, threshold)
            n_evals += 1
            rows.append(e)
        by_pool[surge] = rows
        evals.extend(rows)
    feas = {
        s: [e for e in rows if e.complete and e.p_ok >= threshold] for s, rows in by_pool.items()
    }
    best_no = _choose(feas[False])
    best_yes = _choose(feas.get(True, []))
    min_no = min((e.slots for e in feas[False]), default=None)
    min_yes = min((e.slots for e in feas.get(True, [])), default=None)

    assessment = _assess_surge(consider_surge, best_no, best_yes, max_bed_days_per_event)
    chosen = best_yes if assessment.recommended else best_no
    min_slots = (min_yes if assessment.recommended else min_no) if chosen else None
    pool_rows = feas[True] if assessment.recommended else feas[False]
    min_plan = next((e for e in pool_rows if e.slots == min_slots), None)

    best_effort = None
    if chosen is None:
        full = [evaluate_plan(params, max_slots, sg, weeks, n_select, seed_select) for sg in pools]
        n_evals += len(full)
        best_effort = max(full, key=lambda e: (e.p_ok, -e.det_mean))

    check = seed_chk = None
    if chosen is not None:
        check = check_plan(params, chosen.slots, chosen.surge, weeks, n_validate, seed_validate)
        seed_chk = check_plan(params, chosen.slots, chosen.surge, weeks, n_seed_check, seed_check)
    return CicuRecommendation(
        chosen is not None,
        None if chosen is None else chosen.slots,
        False if chosen is None else chosen.surge,
        min_slots,
        threshold,
        weeks,
        n_select,
        chosen,
        check,
        seed_chk,
        assessment,
        min_plan,
        best_effort,
        tuple(evals),
        n_evals,
        chosen is not None and chosen.slots == max_slots,
    )


def _assess_surge(
    considered: bool,
    best_no: PlanEval | None,
    best_yes: PlanEval | None,
    cap: float | None = None,
) -> SurgeAssessment:
    if not considered:
        return SurgeAssessment(
            False, False, "The surge bed was not considered.", None, None, None, 0, 0, None
        )
    if best_yes is None and best_no is None:
        return SurgeAssessment(
            True,
            False,
            "No plan reaches the threshold, with or without a surge bed.",
            None,
            None,
            None,
            0,
            0,
            None,
        )
    if best_no is None and best_yes is not None:
        return SurgeAssessment(
            True,
            True,
            "No plan without a surge bed keeps the list stable inside the occupancy target; with the extra bed one does.",
            None,
            best_yes.det_mean,
            None,
            best_yes.bed_days_opened,
            best_yes.bed_days_used,
            None,
        )
    if best_no is None:  # pragma: no cover - handled above
        raise RuntimeError("unreachable")
    if best_yes is None:
        return SurgeAssessment(
            True,
            False,
            "The surge bed does not make any plan feasible.",
            best_no.det_mean,
            None,
            None,
            0,
            0,
            None,
        )
    n = min(len(best_no.det), len(best_yes.det))
    diff = np.array(best_yes.det[:n], dtype=float) - np.array(best_no.det[:n], dtype=float)
    d_mean, d_lo, d_hi = mean_ci(diff) if n > 1 else (0.0, 0.0, 0.0)
    avoided = -d_mean
    per_event = best_yes.bed_days_opened / avoided if avoided > 0 else None
    significant = d_hi < 0
    worth = bool(significant and cap is not None and per_event is not None and per_event <= cap)
    if worth:
        reason = "The extra bed lowers expected deterioration events within your cost cap per event avoided."
    elif significant:
        reason = (
            "The extra bed lowers expected deterioration events, but it is not needed to keep the list stable "
            + (
                "and its cost per event avoided is above your cap."
                if cap is not None
                else "and no cost cap is set, so it is not recommended; the cost per event avoided is shown to decide."
            )
        )
    else:
        reason = "The extra bed does not lower deterioration events by a margin the seeds can tell apart from zero."
    return SurgeAssessment(
        True,
        worth,
        reason,
        best_no.det_mean,
        best_yes.det_mean,
        (d_lo, d_hi),
        best_yes.bed_days_opened,
        best_yes.bed_days_used,
        per_event,
    )


def stability(
    params: cp.PolicyParams,
    weeks: int = 52,
    threshold: float = DEFAULT_THRESHOLD,
    n_blocks: int = 30,
    n_select: int = 40,
    max_slots: int = 15,
    consider_surge: bool = True,
    max_bed_days_per_event: float | None = None,
    seed0: int = 200_000,
) -> list[tuple[int | None, bool]]:
    """Re-run the selection on ``n_blocks`` disjoint seed blocks: (slots, surge) each time.

    Offline check of how much the recommended setting itself depends on the seeds (company rule: at
    least 30). Selection only, no validation, so it is cheaper than ``recommend``.
    """
    out: list[tuple[int | None, bool]] = []
    for b in range(n_blocks):
        r = _select_only(
            params,
            weeks,
            threshold,
            n_select,
            max_slots,
            consider_surge,
            max_bed_days_per_event,
            seed0 + b * n_select,
        )
        out.append(r)
    return out


def _select_only(
    params: cp.PolicyParams,
    weeks: int,
    threshold: float,
    n_select: int,
    max_slots: int,
    consider_surge: bool,
    cap: float | None,
    seed0: int,
) -> tuple[int | None, bool]:
    pools = (False, True) if consider_surge else (False,)
    feas: dict[bool, list[PlanEval]] = {}
    for sg in pools:
        rows = [
            evaluate_plan(params, s, sg, weeks, n_select, seed0, threshold)
            for s in range(1, max_slots + 1)
        ]
        feas[sg] = [e for e in rows if e.complete and e.p_ok >= threshold]
    a = _assess_surge(consider_surge, _choose(feas[False]), _choose(feas.get(True, [])), cap)
    chosen = _choose(feas.get(True, [])) if a.recommended else _choose(feas[False])
    return (None, False) if chosen is None else (chosen.slots, chosen.surge)


def plain_words(rec: CicuRecommendation, params: cp.PolicyParams) -> str:
    """The result in sentences a clinician reads; every number comes from ``rec``."""
    target = f"{params.target_occupancy:.0%}"
    if not rec.found or rec.plan is None or rec.check is None:
        be = rec.best_effort
        tail = (
            ""
            if be is None
            else f" The closest plan ({be.slots} elective cases a week{' with the surge bed' if be.surge else ''}) "
            f"meets every condition in {be.p_ok:.0%} of simulated years."
        )
        return (
            f"No plan in the search (1 to {max(e.slots for e in rec.table)} elective cases a week) keeps the waiting list "
            f"from growing, keeps the unit at or below {target} full on average and never makes a "
            f"life-threatening case wait for a bed in at least {rec.threshold:.0%} of simulated years."
            + tail
            + " More CICU beds or fewer referrals would be needed; check the inputs."
        )
    c, s = rec.check, rec.seed_check
    if s is None:  # pragma: no cover - set whenever a plan is found
        raise RuntimeError("unreachable")
    surge_txt = (
        "Open the extra (surge) bed for short-stay cases."
        if rec.surge
        else "Keep the extra (surge) bed closed."
    )
    a = rec.surge_assessment
    cost = ""
    if rec.surge and a.bed_days_per_event_avoided is not None:
        cost = (
            f" The extra bed is open {a.bed_days_opened:.0f} bed-days a year and used on about "
            f"{a.bed_days_used:.0f} days, about {a.bed_days_per_event_avoided:.0f} bed-days opened for each "
            "deterioration avoided."
        )
    elif rec.surge:
        cost = f" The extra bed is open {a.bed_days_opened:.0f} bed-days a year (used on about {a.bed_days_used:.0f})."
    lo, hi = c.ci
    mp = rec.min_plan
    floor_txt = ""
    if (
        mp is not None
        and rec.min_slots_feasible is not None
        and rec.min_slots_feasible < (rec.slots or 0)
    ):
        floor_txt = (
            f" {rec.min_slots_feasible} a week is the least that stops the list growing "
            f"(about {mp.det_mean:.0f} patients worsen a year); the higher figure clears the starting backlog sooner, "
            "which is what lowers the number who worsen, and the slots are not all needed once the list is cleared."
        )
    return (
        f"Operate {rec.slots} elective cases a week (life-threatening cases are always operated first). {surge_txt}{floor_txt} "
        f"In {c.n} fresh simulated years this plan kept the waiting list from growing, kept the unit at or below "
        f"{target} full on average and never made a life-threatening case wait for a bed in {c.p_ok:.0%} of years "
        f"(95% interval {lo:.0%} to {hi:.0%}). Expect about {c.det_mean:.0f} patients to worsen while waiting "
        f"(middle 90% of years: {c.det_p5:.0f} to {c.det_p95:.0f}); the list ends at about {c.list_end_mean:.0f} "
        f"patients (it starts at {params.initial_backlog if params.start_mode == 'today' else 'its settled level'}). "
        f"On {s.n} other seeds the plan met every condition in {s.p_ok:.0%} of years.{cost} "
        f"{a.reason}"
    )
