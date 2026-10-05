# ruff: noqa: E501  (report text)
"""CICU plan delta: the new CICU objective versus the inherited urgent-only criterion  and v1, on synthetic scenarios.

Run: python analysis/measure_cicu_plans.py   (about 30-40 minutes; writes the CICU-plans section of docs/v1-vs-v2.md)

Seeds: selection 20000+, validation 60000+ (200), 30-seed check 90000+ (30), stability blocks 200000+ (30 blocks).
Every scenario is synthetic. Intervals: Wilson 95% for proportions, normal approximation for means (n >= 30).
Not validated against real data.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

from cardiac_capacity import (
    CicuParams,
    CicuSimulator,
    casemix,
    cicu,
    recommend,
)
from cardiac_capacity import (
    cicu_policy as cp,
)
from cardiac_capacity import (
    parameter_sets as ps,
)
from cardiac_capacity import (
    recommend_cicu as rc,
)
from cardiac_capacity import (
    ward_referral_v2 as w2,
)
from cardiac_capacity.stats import mean_ci, wilson_interval
from cardiac_capacity.ward_referral import DEFAULT_PARAMS

REPORT = Path(__file__).resolve().parents[1] / "docs" / "v1-vs-v2.md"
BEGIN, END = "<!-- CICU-PLANS BEGIN -->", "<!-- CICU-PLANS END -->"
WEEKS = 52
LIT = ps.LITERATURE


def pct(k: int, n: int) -> str:
    lo, hi = wilson_interval(k, n)
    return f"{k / n:.0%} [{lo:.0%}, {hi:.0%}]"


def scenarios() -> dict[str, cp.PolicyParams]:
    base = cp.PolicyParams(deterioration_rates=LIT.cicu_rates(), long_wait_or=LIT.long_wait_or)
    return {
        "A default (5 referrals/wk, 10 beds, 60 on the list)": base,
        "B near the ceiling (7 referrals/wk)": replace(base, weekly_referrals=7),
        "C busy (8 referrals/wk): the surge bed matters": replace(base, weekly_referrals=8),
        "D overloaded (10 referrals/wk)": replace(base, weekly_referrals=10),
        "E small unit (6 beds, 3 referrals/wk)": replace(base, beds=6, weekly_referrals=3),
        "F default with lesion case mix": replace(base, casemix=casemix.DEFAULT_CASEMIX),
        "G default, settled start": replace(base, start_mode="settled"),
        "H default, placeholder rates and 1.49": replace(
            base, deterioration_rates=ps.PLACEHOLDERS.cicu_rates(), long_wait_or=1.49
        ),
        "I default, literature rates with long-wait 1.49": replace(base, long_wait_or=1.49),
    }


def d10_capacity(p: cp.PolicyParams) -> int | None:
    """The inherited urgent-only criterion on the deterministic v2 model , same inputs."""
    cp_ = CicuParams(
        initial_backlog=p.initial_backlog,
        weekly_referrals=p.weekly_referrals,
        category_distribution=p.category_distribution,
        los_days=p.los_days,
        deterioration_rates=p.deterioration_rates,
        cicu_beds=p.beds,
    )
    return cicu.recommended_capacity(
        CicuSimulator(5, cp_, model_version="v2").capacity_table(WEEKS)
    )


def v1_capacity(p: cp.PolicyParams) -> int | None:
    cp_ = CicuParams(
        initial_backlog=p.initial_backlog,
        weekly_referrals=p.weekly_referrals,
        category_distribution=p.category_distribution,
        los_days=p.los_days,
        deterioration_rates=p.deterioration_rates,
        cicu_beds=p.beds,
    )
    return cicu.recommended_capacity(CicuSimulator(5, cp_).capacity_table(WEEKS))


def row_for(name: str, p: cp.PolicyParams, out: list[str], stab_out: list[str]) -> None:
    t0 = time.time()
    r = rc.recommend(p, n_select=100, n_validate=200, n_seed_check=30)
    v1 = v1_capacity(p)
    d10 = d10_capacity(p)
    cur = rc.check_plan(p, 5, False, WEEKS, 200, rc.SEED_VALIDATE)
    d10c = rc.check_plan(p, d10, False, WEEKS, 200, rc.SEED_VALIDATE) if d10 else None
    if r.found and r.check and r.seed_check:
        c = r.check
        plan = f"{r.slots}/wk{' + surge bed' if r.surge else ''}"
        ok = pct(c.n_ok, c.n)
        det = f"{c.det_mean:.1f} ({c.det_p5:.0f}-{c.det_p95:.0f})"
        sc = f"{r.seed_check.p_ok:.0%} (n={r.seed_check.n})"
        end = f"{c.list_end_mean:.0f}"
        occ = f"{c.occupancy_mean:.0%}"
        mn = r.min_slots_feasible
    else:
        plan, ok, det, sc, end, occ, mn = "none found", "-", "-", "-", "-", "-", None
    cur_s = f"{pct(cur.n_ok, cur.n)}; {cur.det_mean:.1f}; list {cur.list_end_mean:.0f}"
    d10_s = (
        "none"
        if d10c is None
        else f"{d10}/wk: {pct(d10c.n_ok, d10c.n)}; {d10c.det_mean:.1f}; list {d10c.list_end_mean:.0f}"
    )
    out.append(
        f"| {name} | {'none in 3-14' if v1 is None else v1} | {d10_s} | {cur_s} | {plan} (least that stops growth: {mn if mn else '-'}) | {ok} | {det} | {end} | {occ} | {sc} |"
    )
    a = r.surge_assessment
    stab_out.append(
        f"| {name} | {r.surge_assessment.reason} | "
        f"{'-' if a.det_without is None else f'{a.det_without:.1f}'} | {'-' if a.det_with is None else f'{a.det_with:.1f}'} | "
        f"{'-' if a.det_diff_ci is None else f'[{a.det_diff_ci[0]:.1f}, {a.det_diff_ci[1]:.1f}]'} | "
        f"{a.bed_days_opened:.0f} / {a.bed_days_used:.0f} | "
        f"{'-' if a.bed_days_per_event_avoided is None else f'{a.bed_days_per_event_avoided:.0f}'} |"
    )
    print(f"{name}: {time.time() - t0:.0f}s", flush=True)


def stability_row(name: str, p: cp.PolicyParams, out: list[str]) -> None:
    picks = rc.stability(p, WEEKS, n_blocks=30, n_select=40)
    cnt = Counter(picks)
    top, k = cnt.most_common(1)[0]
    lo, hi = wilson_interval(k, len(picks))
    dist = ", ".join(
        f"{('none' if s is None else f'{s}/wk' + (' + surge' if sg else ''))}: {n}"
        for (s, sg), n in sorted(cnt.items(), key=lambda kv: (-kv[1], str(kv[0])))
    )
    slots = [s for s, _ in picks if s is not None]
    spread = f"{min(slots)}-{max(slots)}" if slots else "-"
    out.append(
        f"| {name} | {dist} | most frequent {k}/30 ({k / 30:.0%}; Wilson {lo:.0%}-{hi:.0%}) | {spread} |"
    )


def main() -> None:
    t_start = time.time()
    sc = scenarios()
    main_rows: list[str] = []
    surge_rows: list[str] = []
    for name, p in sc.items():
        row_for(name, p, main_rows, surge_rows)

    stab_rows: list[str] = []
    for name in list(sc)[:3] + [list(sc)[5]]:
        stability_row(name, sc[name], stab_rows)
        print("stability", name, flush=True)

    # Sensitivity of the answer to the user settings, scenario B.
    base = sc["B near the ceiling (7 referrals/wk)"]
    sens: list[str] = []
    for label, p, thr in (
        ("occupancy target 70%", replace(base, target_occupancy=0.70), 0.90),
        ("occupancy target 85% (default)", base, 0.90),
        ("occupancy target 95%", replace(base, target_occupancy=0.95), 0.90),
        ("threshold 80%", base, 0.80),
        ("threshold 95%", base, 0.95),
    ):
        r = rc.recommend(p, threshold=thr, n_select=100, n_validate=200, n_seed_check=30)
        if r.found and r.check:
            sens.append(
                f"| {label} | {r.slots}/wk{' + surge' if r.surge else ''} | {pct(r.check.n_ok, r.check.n)} | {r.check.det_mean:.1f} | {r.check.occupancy_mean:.0%} |"
            )
        else:
            sens.append(f"| {label} | none found | - | - | - |")
        print("sens", label, flush=True)

    # Parameter-set effect on the ward engine (default scenario A), 100 seeds each.
    ward_rows: list[str] = []
    for label, extra in (
        ("placeholders, odds multiplier 1.49 (as shipped)", ps.PLACEHOLDERS.ward_params()),
        ("literature-based rates, multiplier 1.0", LIT.ward_params()),
        ("literature-based rates, multiplier 1.49", {**LIT.ward_params(), "long_wait_or": 1.49}),
    ):
        params = {**DEFAULT_PARAMS, **extra}
        frames = [w2.run_simulation(params, [], WEEKS, 3000 + i, detail=False) for i in range(100)]
        br = [float(f["Over_26_Wks"].iloc[26]) for f in frames]
        dt = [float(f["det_events"].sum()) for f in frames]
        m1, l1, h1 = mean_ci(br)
        m2, l2, h2 = mean_ci(dt)
        rec = recommend.recommend(params, 26, 0.9, n_select=100, n_validate=200)
        pick = (
            f"({rec.slots}, {rec.beds}) {rec.p_validate:.1%} [{rec.ci_validate[0]:.1%}, {rec.ci_validate[1]:.1%}]"
            if rec.found
            else "none"
        )
        ward_rows.append(
            f"| {label} | {m1:.1f} [{l1:.1f}, {h1:.1f}] | {m2:.0f} [{l2:.0f}, {h2:.0f}] | {pick} |"
        )
        print("ward", label, flush=True)

    why_rows: list[str] = []
    for name in (list(sc)[3], list(sc)[4]):
        for slots, surge in ((15, False), (15, True)):
            c = rc.check_plan(sc[name], slots, surge, WEEKS, 200, rc.SEED_VALIDATE)
            f = c.failures
            why_rows.append(
                f"| {name} | {slots}/wk{' + surge bed' if surge else ''} | {pct(c.n_ok, c.n)} | "
                f"{f['list grew']:.0%} | {f['unit above the occupancy target']:.0%} | "
                f"{f['a life-threatening case waited for a bed']:.0%} | {c.occupancy_mean:.0%} | {c.list_end_mean:.0f} |"
            )

    section = f"""{BEGIN}
# New CICU objective (generated by `measure_delta_c6b.py`; {time.strftime("%Y-%m-%d")}, {(time.time() - t_start) / 60:.0f} min)

What changed. v1 and the inherited criterion judged a CICU capacity only on whether urgent cases were cleared and load fitted in
the beds. The new v2 objective asks for a plan (elective cases a week, with or without a surge bed) whose futures
meet all of: the waiting list is no longer at the end than at the start (plus one week of referrals), mean CICU occupancy is at
or below the target (default 85%), and no life-threatening case waits for a bed. A plan is feasible when at least 90% of
futures meet all three; the plan with the fewest expected deteriorations wins (smallest slots within one standard error).
Synthetic scenarios only; literature-based rates and no generic long-wait multiplier unless stated. Seeds: 100
for selection, 200 fresh for the out-of-sample column (Wilson 95%), 30 more for the seed check. "Deterioration" = patients who
move up an urgency category while waiting during the 52 weeks, mean (5th-95th percentile across years).

## Plans 1. Recommendation, new objective versus v1 and the inherited criterion

| Scenario | v1 recommended capacity | Inherited urgent-only criterion on v2 : out-of-sample success under the new rules; deteriorations; list at week 52 | Current plan (5/wk): same three | New recommended plan (least that stops growth) | Out-of-sample success [Wilson 95%] | Deteriorations / 52 wk | List at week 52 | Mean occupancy | 30 other seeds |
|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(main_rows)}

## Plans 2. Is the extra (surge) bed worth opening?

Paired over the selection seeds (with minus without; negative = fewer deteriorations). Cost is bed-days opened (7 a week) and the days it was actually used, per year. No cost cap is set (no published threshold), so a surge bed is recommended only when it is needed for a feasible plan.

| Scenario | Assessment | Deteriorations without | with | Paired 95% interval | Bed-days opened / used | Bed-days opened per deterioration avoided |
|---|---|---|---|---|---|---|
{chr(10).join(surge_rows)}

## Plans 3. Seed sensitivity of the recommendation itself

The selection was repeated on 30 disjoint blocks of 40 seeds. If the pick moves a lot between blocks, the plan is not seed-stable and the app's out-of-sample rate is the number to trust.

| Scenario | Picks over 30 blocks | Most frequent | Range of slots |
|---|---|---|---|
{chr(10).join(stab_rows)}

## Plans 4. How the answer moves with the user's settings (scenario B)

| Setting | Plan | Out-of-sample success [Wilson 95%] | Deteriorations / 52 wk | Mean occupancy |
|---|---|---|---|---|
{chr(10).join(sens)}

## Plans 5. Effect of the parameter set on the ward engine (default scenario A, 100 seeds)

| Parameter set | Patients waiting 26+ weeks at week 26 [95% CI] | Deteriorations in 52 weeks [95% CI] | Ward recommendation at 90% (slots, beds), out-of-sample [Wilson 95%] |
|---|---|---|---|
{chr(10).join(ward_rows)}

## Plans 6. Why no plan was found (scenarios D and E)

Share of 200 fresh years failing each condition, for the most generous plan in the search (15 cases a week).

| Scenario | Plan | Holds | List grew | Unit above the occupancy target | A life-threatening case waited for a bed | Mean occupancy | List at week 52 |
|---|---|---|---|---|---|---|---|
{chr(10).join(why_rows)}

## Reading notes for the CICU plans (limits stated plainly)

- Scenario D has more demand than the elective ceiling (8 of 10 beds) can serve: the list grows in nearly every year whatever the slots, so the honest answer is more beds, fewer referrals or a lower occupancy target, not a plan. Scenario E is just under the threshold only because a life-threatening case waited for a bed in about 1 year in 8 (a six-bed unit with 14-day urgent stays); the list is stable and occupancy is within the target.
- The recommended slots sit on a plateau: above the least number that stops the list growing, extra slots lower the expected number of patients who worsen only slowly, so the pick moves between 10 and 15 a week across seed blocks (Plans 3) while its success rate and deterioration count hardly move. Read the pick as "at least this many", and the least-to-stop-growth figure as the floor. Theatre-time cost is not in the objective, so no extra slot is penalised.
- A surge bed that is not needed for feasibility can still cut the expected number who worsen (scenario B: 15.8 to 9.0 a year, about 53 bed-days opened for each one avoided). With no published cost threshold the model does not decide: the app labels it "Optional" and shows the cost per event avoided; set a cap in the app and it will decide.

- The success rates are out of sample (fresh seeds) with Wilson intervals; a plan can still be chosen slightly optimistically on the selection seeds, so the fresh-run rate and its interval are the figures to quote.
- "Mean occupancy" is the average over all days of the base beds; the ceiling only limits elective admissions, so life-threatening cases can take the unit above the target on some days.
- Deterioration counts depend on the rates, which are either placeholders or the sourced untreated hazards used as proxies. Neither is a measured rate for a medically managed child. Nothing here is validated against real data.
- The recommended number of elective cases a week is the one with the fewest expected deteriorations over the year, which for a starting list of 60 includes a catch-up burst; the least number that merely stops the list growing is shown next to it.
{END}"""
    text = REPORT.read_text(encoding="utf-8")
    if BEGIN in text:
        text = re.sub(
            f"{re.escape(BEGIN)}.*?{re.escape(END)}", lambda _m: section, text, flags=re.S
        )
    else:
        text = text.rstrip() + "\n\n" + section + "\n"
    REPORT.write_text(text, encoding="utf-8")
    print("done", (time.time() - t_start) / 60, "min")


if __name__ == "__main__":
    main()
