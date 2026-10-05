# ruff: noqa: E501  (long prose in docstrings and plain-language strings)
"""CICU planner v2, stochastic: bed-limited surgery, an occupancy ceiling, an optional surge bed.

New module . v1 and the deterministic ``cicu_v2`` stay as they are; this engine exists
because the new objective needs seeds, per-patient deterioration and beds that actually block surgery.

Weekly loop with five theatre days (Mon-Fri), as ``ward_referral_v2``:

1. Age the list one week and draw one Bernoulli deterioration per patient on the patient's own category
   (odds multiplied by ``long_wait_or`` once a patient has waited ``long_wait_weeks``). Spontaneous resolution
   and deadline checks (case mix) happen here too.
2. Poisson referrals, plus planned stage-2 re-entries (case mix).
3. Each theatre day, candidates are taken by category then longest wait.
   - Category 1 (life-threatening) is operated on the first theatre day it is on the list, whatever the elective
     slot count, and may use every base bed.
   - Elective categories (2-4) use the weekly ``slots`` and may enter only while fewer than
     ``floor(target_occupancy * beds)`` base beds are occupied, which keeps the rest of the unit as headroom for
     life-threatening cases (the occupancy ceiling, default 85%, a user setting).
   - A surge bed (opened only if ``surge_beds > 0``) takes elective patients whose expected stay is at most
     ``surge_max_los_days``; it sits outside the ceiling and is counted separately as bed-days.
4. Stays are ``ceil(Gamma(shape = mean days, scale = 1))`` days, minimum 1, and a bed is free from the day after
   the stay ends (same convention as ``ward_referral_v2``). Occupancy is counted every day.

Streams are separate seeded ``RandomState([seed, k])`` (initial list, arrivals, deterioration, stay, misc), so
the initial list and referrals are identical across plans for one seed; deterioration and stay draws
desynchronise once plans admit different numbers (partial pairing).

Per-run results (``run_metrics``) cover the measured window only; ``settled`` start discards ``warmup_weeks``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from cardiac_capacity.casemix import CaseMix

START_MODES = ("today", "settled")
THEATRE_DAYS = 5
DEFAULT_RATES = (0.0, 0.05, 0.02, 0.01)  # CicuParams defaults (placeholders)


@dataclass(frozen=True)
class PolicyParams:
    """One plan plus one scenario. ``slots``, ``beds`` and ``surge_beds`` are the decisions."""

    slots: int = 5
    beds: int = 10
    target_occupancy: float = 0.85
    surge_beds: int = 0
    surge_max_los_days: float = 3.0
    weekly_referrals: float = 5.0
    initial_backlog: int = 60
    category_distribution: tuple[float, ...] = (0.05, 0.15, 0.30, 0.50)
    los_days: tuple[float, ...] = (14, 10, 5, 3)
    deterioration_rates: tuple[float, ...] = DEFAULT_RATES
    long_wait_or: float = 1.0
    long_wait_weeks: int = 26
    occupied_now: tuple[
        float, ...
    ] = ()  # days left for each CICU bed occupied today (start "today")
    start_mode: str = "today"
    warmup_weeks: int = 52
    casemix: CaseMix | None = None

    @property
    def elective_limit(self) -> int:
        """Base beds that elective cases may fill: floor(target x beds), at least 1, at most all beds."""
        return int(min(self.beds, max(1, np.floor(self.target_occupancy * self.beds + 1e-9))))

    def with_plan(self, slots: int, surge: bool) -> PolicyParams:
        return replace(self, slots=slots, surge_beds=1 if surge else 0)


@dataclass(frozen=True)
class RunMetrics:
    """Outcomes of one replication over the measured window."""

    det_events: int
    deadline_missed: int
    interstage_deaths: int
    late_tgavsd: int
    resolved: int
    admissions: int
    cancellations: int
    list_start: int
    list_end: int
    list_peak: int
    over_26_end: int
    cat1_unserved_days: int
    mean_occupancy: float  # base beds, share of all base beds
    days_over_target: float  # share of days with base occupancy above the target
    days_full: float  # share of days with every base bed taken
    surge_days_used: int
    surge_days_open: int
    wait_at_surgery_sum: int = 0  # weeks waited, summed over patients operated in the window
    stay_sum: float = 0.0  # CICU days, summed over patients operated in the window
    stage1_operated: int = 0  # patients with a planned later stage operated in the window

    @property
    def mean_wait_at_surgery(self) -> float:
        return self.wait_at_surgery_sum / self.admissions if self.admissions else 0.0

    @property
    def mean_stay(self) -> float:
        return self.stay_sum / self.admissions if self.admissions else 0.0

    @property
    def growth(self) -> int:
        return self.list_end - self.list_start


def _streams(seed: int | None) -> tuple[np.random.RandomState, ...]:
    if seed is None:
        return tuple(np.random.RandomState() for _ in range(5))
    return tuple(np.random.RandomState([seed, k]) for k in range(5))


def _odds(p: np.ndarray, odds_ratio: float) -> np.ndarray:
    return p * odds_ratio / (1 - p + p * odds_ratio)


def _simulate(params: PolicyParams, weeks: int, seed: int | None, detail: bool) -> tuple[Any, ...]:
    if params.start_mode not in START_MODES:
        raise ValueError(f"start_mode must be one of {START_MODES}")
    if params.slots < 0 or params.beds < 1 or params.surge_beds < 0:
        raise ValueError("slots must be >= 0, beds >= 1, surge_beds >= 0")
    r_init, r_arr, r_det, r_los, r_misc = _streams(seed)
    settled = params.start_mode == "settled"
    skip = params.warmup_weeks if settled else 0
    total_weeks = weeks + skip
    mix = params.casemix

    rates = np.array(params.deterioration_rates, dtype=float)
    p_det: np.ndarray = np.concatenate([[0.0], rates])  # index by category 1..4 -> rates[cat-1]
    p_long: np.ndarray = _odds(p_det, params.long_wait_or)
    cat_los = np.array([0.0, *params.los_days], dtype=float)
    cat_probs = np.array(params.category_distribution, dtype=float)
    cat_probs = cat_probs / cat_probs.sum()

    if mix is not None:
        g_cat = np.array([g.cicu_cat for g in mix.groups], dtype=int)
        g_los = np.array([g.los_days for g in mix.groups], dtype=float)
        g_deadline = np.array([g.deadline_weeks or 0 for g in mix.groups], dtype=int)
        g_resolve = np.array([g.resolution_weekly for g in mix.groups], dtype=float)
        g_late = np.array([g.complication_late_weeks or 0 for g in mix.groups], dtype=int)
        shares = np.array(mix.arrival_shares(), dtype=float)
        stage_of = {i: g.stage2 for i, g in enumerate(mix.groups) if g.stage2}
    else:
        g_cat = np.zeros(0, dtype=int)
        g_deadline = np.zeros(0, dtype=int)
        g_late = np.zeros(0, dtype=int)
        g_los = np.zeros(0)
        g_resolve = np.zeros(0)
        shares = np.zeros(0)
        stage_of = {}

    slots_week = int(params.slots)
    base_slots, extra = divmod(slots_week, THEATRE_DAYS)
    beds = int(params.beds)
    e_limit = params.elective_limit
    surge_n = int(params.surge_beds)
    target_beds = params.target_occupancy * beds

    def draw_groups(n: int, rs: np.random.RandomState) -> np.ndarray:
        return rs.choice(len(shares), size=n, p=shares).astype(int)

    # Initial list.
    cat = np.zeros(0, dtype=int)
    wait = np.zeros(0, dtype=int)
    grp = np.zeros(0, dtype=int)
    base_end = np.zeros(0)
    if not settled:
        n0 = int(params.initial_backlog)
        if mix is not None:
            grp = draw_groups(n0, r_init)
            cat = g_cat[grp].astype(int)
        else:
            cat = r_init.choice([1, 2, 3, 4], size=n0, p=cat_probs).astype(int)
            grp = np.full(n0, -1, dtype=int)
        wait = r_init.randint(0, 25, size=n0).astype(int)
        base_end = np.array([max(1.0, np.ceil(d)) for d in params.occupied_now], dtype=float)
    flagged = np.zeros(cat.size, dtype=bool)
    surge_end = np.zeros(0)

    total_days = 7 * total_weeks
    occ_base = np.zeros(total_days)
    occ_surge = np.zeros(total_days)
    cat1_unserved = np.zeros(total_weeks, dtype=int)
    w_det = np.zeros(total_weeks, dtype=int)
    w_deadline = np.zeros(total_weeks, dtype=int)
    w_inter = np.zeros(total_weeks, dtype=int)
    w_late = np.zeros(total_weeks, dtype=int)
    w_res = np.zeros(total_weeks, dtype=int)
    w_adm = np.zeros(total_weeks, dtype=int)
    w_cancel = np.zeros(total_weeks, dtype=int)
    w_wait = np.zeros(total_weeks, dtype=int)
    w_stay = np.zeros(total_weeks)
    w_stage1 = np.zeros(total_weeks, dtype=int)
    list_closing = np.zeros(total_weeks + 1, dtype=int)
    over26_closing = np.zeros(total_weeks + 1, dtype=int)
    cat_closing = np.zeros((total_weeks + 1, 5), dtype=int)
    list_closing[0] = cat.size
    over26_closing[0] = int(np.sum(wait >= 26))
    cat_closing[0] = np.bincount(cat, minlength=5)[:5]
    reentry: dict[int, list[int]] = {}  # week -> group indices of planned stage-2 patients

    for week in range(total_weeks):
        # 1. Ageing, deterioration, resolution, deadlines.
        wait = wait + 1
        probs = np.where(wait >= params.long_wait_weeks, p_long.take(cat), p_det.take(cat))
        moved = r_det.random_sample(cat.size) < probs
        w_det[week] = int(moved.sum())
        cat = cat - moved.astype(int)
        if mix is not None and cat.size:
            gone = (r_misc.random_sample(cat.size) < g_resolve[grp]) & (g_resolve[grp] > 0)
            if gone.any():
                w_res[week] = int(gone.sum())
                keep = ~gone
                cat, wait, grp, flagged = cat[keep], wait[keep], grp[keep], flagged[keep]
            dl = g_deadline[grp]
            hit = (dl > 0) & (wait >= dl) & ~flagged
            w_deadline[week] = int(hit.sum())
            flagged = flagged | hit

        # 2. Referrals and planned re-entries.
        n_new = int(r_arr.poisson(params.weekly_referrals))
        if n_new:
            if mix is not None:
                new_g = draw_groups(n_new, r_arr)
                new_c = g_cat[new_g]
            else:
                new_c = r_arr.choice([1, 2, 3, 4], size=n_new, p=cat_probs).astype(int)
                new_g = np.full(n_new, -1, dtype=int)
            cat = np.concatenate([cat, new_c])
            grp = np.concatenate([grp, new_g])
            wait = np.concatenate([wait, np.zeros(n_new, dtype=int)])
            flagged = np.concatenate([flagged, np.zeros(n_new, dtype=bool)])
        if week in reentry:
            for gi in reentry.pop(week):
                cat = np.append(cat, g_cat[gi])
                grp = np.append(grp, gi)
                wait = np.append(wait, 0)
                flagged = np.append(flagged, False)

        # 3. Theatre days.
        cancels = 0
        for d in range(THEATRE_DAYS):
            day = 7 * week + d
            elective_slots = base_slots + (1 if d < extra else 0)
            if cat.size:
                base_end = base_end[base_end > day]
                surge_end = surge_end[surge_end > day]
                order = np.lexsort((-wait, cat))
                taken: list[int] = []
                electives_waiting = int(np.sum(cat > 1))
                admitted_elective = 0
                for idx in order:
                    c = int(cat[idx])
                    if c > 1 and elective_slots <= 0:
                        break
                    gi = int(grp[idx])
                    mean_los = float(g_los[gi]) if gi >= 0 else float(cat_los[c])
                    pool = ""
                    if c == 1:
                        if base_end.size < beds:
                            pool = "base"
                    elif base_end.size < e_limit:
                        pool = "base"
                    elif (
                        surge_n
                        and surge_end.size < surge_n
                        and mean_los <= params.surge_max_los_days
                    ):
                        pool = "surge"
                    if not pool:
                        continue
                    stay = float(
                        np.ceil(max(1.0, r_los.gamma(shape=max(mean_los, 0.1), scale=1.0)))
                    )
                    if pool == "base":
                        base_end = np.append(base_end, day + stay)
                    else:
                        surge_end = np.append(surge_end, day + stay)
                    taken.append(int(idx))
                    w_wait[week] += int(wait[idx])
                    w_stay[week] += stay
                    if c > 1:
                        elective_slots -= 1
                        admitted_elective += 1
                    if gi >= 0 and mix is not None:
                        if g_late[gi] and wait[idx] >= g_late[gi]:
                            w_late[week] += 1
                        st = stage_of.get(gi)
                        if st is not None:
                            w_stage1[week] += 1
                            if r_misc.random_sample() < st.interstage_mortality:
                                w_inter[week] += 1
                            else:
                                lo, hi = st.after_weeks
                                due = week + int(r_misc.randint(lo, hi))
                                if due < total_weeks:
                                    reentry.setdefault(due, []).append(mix.index(st.group_key))
                if electives_waiting:
                    cancels += max(
                        0,
                        min(base_slots + (1 if d < extra else 0), electives_waiting)
                        - admitted_elective,
                    )
                if taken:
                    w_adm[week] += len(taken)
                    keep = np.ones(cat.size, dtype=bool)
                    keep[taken] = False
                    cat, wait, grp, flagged = cat[keep], wait[keep], grp[keep], flagged[keep]
                cat1_unserved[week] += int(np.sum(cat == 1))
            else:
                base_end = base_end[base_end > day]
                surge_end = surge_end[surge_end > day]
            occ_base[day] = base_end.size
            occ_surge[day] = surge_end.size
        for day in range(7 * week + THEATRE_DAYS, 7 * week + 7):
            occ_base[day] = int(np.sum(base_end > day))
            occ_surge[day] = int(np.sum(surge_end > day))
        w_cancel[week] = cancels
        list_closing[week + 1] = cat.size
        over26_closing[week + 1] = int(np.sum(wait >= 26))
        cat_closing[week + 1] = np.bincount(cat, minlength=5)[:5]

    return (
        skip,
        total_weeks,
        occ_base,
        occ_surge,
        cat1_unserved,
        w_det,
        w_deadline,
        w_inter,
        w_late,
        w_res,
        w_adm,
        w_cancel,
        list_closing,
        over26_closing,
        cat_closing,
        target_beds,
        beds,
        surge_n,
        w_wait,
        w_stay,
        w_stage1,
    )


def _metrics(res: tuple[Any, ...], target_occupancy: float) -> RunMetrics:
    (skip, total_weeks, occ_base, occ_surge, c1, w_det, w_dl, w_in, w_late, w_res, w_adm, w_can,
     lst, over26, _cat, target_beds, beds, surge_n, w_wait, w_stay, w_stage1) = res  # fmt: skip
    s = slice(skip, total_weeks)
    ds = slice(7 * skip, 7 * total_weeks)
    ob = occ_base[ds]
    return RunMetrics(
        det_events=int(w_det[s].sum()),
        deadline_missed=int(w_dl[s].sum()),
        interstage_deaths=int(w_in[s].sum()),
        late_tgavsd=int(w_late[s].sum()),
        resolved=int(w_res[s].sum()),
        admissions=int(w_adm[s].sum()),
        cancellations=int(w_can[s].sum()),
        list_start=int(lst[skip]),
        list_end=int(lst[total_weeks]),
        list_peak=int(lst[skip : total_weeks + 1].max()),
        over_26_end=int(over26[total_weeks]),
        cat1_unserved_days=int(c1[s].sum()),
        mean_occupancy=float(ob.mean() / beds),
        days_over_target=float(np.mean(ob > target_beds + 1e-9)),
        days_full=float(np.mean(ob >= beds)),
        surge_days_used=int(np.sum(occ_surge[ds] > 0)),
        surge_days_open=int(surge_n * (total_weeks - skip) * 7),
        wait_at_surgery_sum=int(w_wait[s].sum()),
        stay_sum=float(w_stay[s].sum()),
        stage1_operated=int(w_stage1[s].sum()),
    )


def run_metrics(params: PolicyParams, weeks: int = 52, seed: int | None = None) -> RunMetrics:
    """One replication, outcomes over the measured ``weeks``."""
    return _metrics(_simulate(params, weeks, seed, detail=False), params.target_occupancy)


def run_frame(params: PolicyParams, weeks: int = 52, seed: int | None = None) -> pd.DataFrame:
    """One replication as a weekly frame (week 0 = the start of the measured window)."""
    res = _simulate(params, weeks, seed, detail=True)
    skip, total_weeks, occ_base, occ_surge, c1, w_det, w_dl, _wi, _wl, _wr, w_adm, w_can, lst, o26, cats, _tb, beds, _sn, _ww, _wsy, _ws1 = res  # fmt: skip
    rows = []
    for w in range(skip, total_weeks + 1):
        row: dict[str, Any] = {
            "week": w - skip,
            "list": int(lst[w]),
            **{f"cat{i}": int(cats[w][i]) for i in range(1, 5)},
            "over_26_weeks": int(o26[w]),
        }
        if w < total_weeks:
            days = slice(7 * w, 7 * w + 7)
            row.update(
                det_events=int(w_det[w]),
                deadline_missed=int(w_dl[w]),
                admissions=int(w_adm[w]),
                cancellations=int(w_can[w]),
                occupancy=float(occ_base[days].mean()),
                occupancy_peak=float(occ_base[days].max()),
                surge_occupancy=float(occ_surge[days].mean()),
                cat1_unserved_days=int(c1[w]),
            )
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame["beds"] = beds
    return frame


def replicate(params: PolicyParams, weeks: int, n: int, seed0: int) -> list[RunMetrics]:
    """``n`` seeded replications (seeds ``seed0 .. seed0 + n - 1``)."""
    return [run_metrics(params, weeks, seed0 + i) for i in range(n)]


def category_shares(params: PolicyParams) -> Sequence[float]:
    """Arrival category shares in force (from the case mix if one is set)."""
    if params.casemix is not None:
        return params.casemix.category_shares()
    p = np.array(params.category_distribution, dtype=float)
    return tuple(float(x) for x in p / p.sum())
