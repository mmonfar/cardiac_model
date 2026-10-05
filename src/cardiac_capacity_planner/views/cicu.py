# ruff: noqa: E501  (plain-language card text)
"""CICU mode: a plan that clears the list, keeps the unit at a safe occupancy, life-threatening first.

The top panel is the v2 recommendation (stochastic); below it the deterministic v2 view of the
chosen capacity (load from operated patients) and the v1 comparison.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cardiac_capacity import CicuParams, CicuSimulator, cicu, parameter_sets
from cardiac_capacity import casemix as cm
from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import recommend_cicu as rc
from cardiac_capacity_planner import charts, presentation, ui

WEEKS = 52
LABELS = presentation.CICU_CATEGORIES
DEFAULTS = CicuParams()
START_MODES = {
    "today": "From today's waiting list",
    "settled": "From a settled state (warm-up first)",
}
RATE_SETS = {
    "placeholders": "Placeholders (v1 category rates, not sourced), the default",
    "literature": "Literature-based (sourced hazards, awaiting clinical check)",
}


@st.cache_data(show_spinner="Searching plans across simulated futures…")
def search(
    policy: cp.PolicyParams, threshold: float, n_select: int, surge: bool, cap: float | None
) -> rc.CicuRecommendation:
    return rc.recommend(
        policy,
        WEEKS,
        threshold,
        n_select=n_select,
        n_validate=200,
        n_seed_check=30,
        consider_surge=surge,
        max_bed_days_per_event=cap,
    )


@st.cache_data(show_spinner=False)
def current_plan(policy: cp.PolicyParams, slots: int) -> rc.Check:
    return rc.check_plan(policy, slots, False, WEEKS, 100, rc.SEED_VALIDATE)


with st.sidebar:
    ui.section("Operations")
    capacity = st.slider("Weekly OR capacity", 3, 15, 5)
    beds = int(st.number_input("CICU beds", min_value=1, max_value=50, value=10, step=1))
    occupied_now = int(
        st.number_input("Beds occupied today", min_value=0, max_value=50, value=0, step=1)
    )
    scheduling = st.selectbox("Scheduling mode", list(cicu.SCHEDULING_MODES), index=0)
    rounding = st.radio(
        "Rounding", list(cicu.ROUNDING_METHODS), index=0, format_func=str.capitalize
    )
    ui.section("Waiting list")
    backlog = int(st.number_input("Initial backlog", min_value=0, value=60, step=1))
    referrals = int(st.number_input("Weekly referrals", min_value=0, value=5, step=1))
    with st.expander("Category mix and length of stay"):
        mix = [
            st.number_input(f"{label} share", 0.0, 1.0, float(p), 0.01, format="%.2f")
            for label, p in zip(LABELS, DEFAULTS.category_distribution, strict=True)
        ]
        los = [
            st.number_input(f"{label} CICU stay (days)", 1, 30, int(d), 1)
            for label, d in zip(LABELS, DEFAULTS.los_days, strict=True)
        ]
    use_casemix = st.checkbox("Use the lesion case mix", value=False)
    mix_shares: list[float] = []
    if use_casemix:
        with st.expander("Arrival share by lesion (synthetic)"):
            st.caption(
                "No population shares are published for these lesions: these are your inputs. "
                "The category mix above is ignored while the case mix is on."
            )
            for g in cm.GROUPS:
                if g.share > 0:
                    mix_shares.append(
                        st.number_input(f"{g.label} share", 0.0, 1.0, float(g.share), 0.01)
                    )
                else:
                    mix_shares.append(0.0)
    ui.section("Recommendation")
    rate_key = st.selectbox(
        "Deterioration rates",
        list(RATE_SETS),
        index=0,
        format_func=lambda k: RATE_SETS[k],
    )
    target_pct = st.slider("Occupancy target (%)", 50, 100, 85)
    threshold_pct = st.slider("Success threshold (%)", 50, 99, 90)
    consider_surge = st.checkbox("Consider an extra (surge) bed", value=True)
    with st.expander("Surge bed settings"):
        surge_los = st.number_input("Short stay: up to (days)", 1.0, 10.0, 3.0, 0.5)
        cap_text = st.number_input(
            "Most bed-days I would open per deterioration avoided (0 = no cap)",
            0, 5000, 0, 10,
        )  # fmt: skip
    start_label = st.radio("Start from", list(START_MODES.values()), index=0)
    show_v1 = st.checkbox("Show the v1 comparison", value=False)
    start_mode = next(k for k, v in START_MODES.items() if v == start_label)
    n_select = int(st.select_slider("Futures simulated per plan", options=[40, 60, 100], value=60))
    ui.footnote("Prototype · synthetic parameters")

total = sum(mix)
if total <= 0:
    st.error("The category mix must have at least one non-zero share.")
    st.stop()
if total != 1.0:  # normalise, as the original app did
    mix = [x / total for x in mix]
if use_casemix and sum(mix_shares) <= 0:
    st.error("The lesion case mix must have at least one non-zero share.")
    st.stop()

pset = parameter_sets.get(rate_key)
params = CicuParams(
    rounding_method=str(rounding),
    initial_backlog=backlog,
    weekly_referrals=referrals,
    category_distribution=tuple(mix),
    deterioration_rates=pset.cicu_rates(),
    los_days=tuple(int(x) for x in los),
    cicu_beds=beds,
    scheduling_mode=str(scheduling),
)
policy = cp.PolicyParams(
    slots=capacity,
    beds=beds,
    target_occupancy=target_pct / 100,
    surge_max_los_days=float(surge_los),
    weekly_referrals=float(referrals),
    initial_backlog=backlog,
    category_distribution=tuple(mix),
    los_days=tuple(float(x) for x in los),
    deterioration_rates=pset.cicu_rates(),
    long_wait_or=pset.long_wait_or,
    long_wait_weeks=pset.long_wait_weeks,
    occupied_now=tuple([3.0] * occupied_now),
    start_mode=start_mode,
    casemix=cm.CaseMix(shares=tuple(mix_shares)) if use_casemix else None,
)
cap = float(cap_text) if cap_text and cap_text > 0 else None
rec = search(policy, threshold_pct / 100, n_select, consider_surge, cap)
now = current_plan(policy, capacity)

sim = CicuSimulator(capacity, params, model_version="v2")
weekly = sim.simulate(WEEKS)
summary = sim.summary(WEEKS)
table = sim.capacity_table(WEEKS)
recommended = cicu.recommended_capacity(table)
peak = float(weekly["cicu_peak_daily"].to_numpy().max())
final_urgent = float(summary["finalState"][0])
det_status = presentation.cicu_status(peak, beds, final_urgent)
status = presentation.plan_status(rec, target_pct / 100)

ui.header(
    "Cardiac capacity · CICU",
    f"{capacity} cases / week · {beds} CICU beds",
    [
        f"Occupancy target {target_pct}%",
        f"Rates: {pset.label}",
        "Model v2 · " + START_MODES[start_mode].lower(),
        f"{WEEKS}-week horizon",
    ],
    status,
)

ui.section("Recommended plan")
k1, k2, k3 = st.columns(3)
with k1:
    if rec.found and rec.check is not None:
        ui.card(
            "Recommended plan",
            f"{rec.slots} cases / week" + (" + surge bed" if rec.surge else ""),
            "Life-threatening cases are always operated first. "
            + (
                f"At least <b>{rec.min_slots_feasible}</b> a week is needed just to stop the list growing."
                if rec.min_slots_feasible
                else ""
            ),
            presentation.TEAL,
        )
    else:
        ui.card(
            "Recommended plan",
            "None found",
            f"No plan up to {max(e.slots for e in rec.table)} cases a week reaches {threshold_pct}% of "
            "futures meeting every condition.",
            presentation.RED,
        )
with k2:
    if rec.check is not None:
        lo, hi = rec.check.ci
        ui.card(
            "Chance the plan holds",
            f"{100 * rec.check.p_ok:.0f}%",
            f"List not growing, unit at or below {target_pct}% on average, no life-threatening case "
            f"waiting for a bed. {rec.check.n} fresh simulated years, 95% interval "
            f"<b>{100 * lo:.0f}–{100 * hi:.0f}%</b> (Wilson).",
        )
    else:
        be = rec.best_effort
        ui.card(
            "Closest plan",
            "-" if be is None else f"{100 * be.p_ok:.0f}% hold",
            "Share of futures meeting every condition for the closest plan in the search.",
        )
with k3:
    if rec.check is not None:
        ui.card(
            "Patients who worsen in a year",
            f"{rec.check.det_mean:.0f}",
            f"Middle 90% of years: {rec.check.det_p5:.0f}–{rec.check.det_p95:.0f}. Your "
            f"{capacity}-a-week plan: <b>{now.det_mean:.0f}</b>, holding in "
            f"<b>{100 * now.p_ok:.0f}%</b> of years.",
        )
    else:
        ui.card(
            "Your current plan",
            f"{100 * now.p_ok:.0f}% hold",
            f"{capacity} cases a week: {now.det_mean:.0f} patients worsen a year on average.",
        )

with st.container(border=True):
    st.markdown(rc.plain_words(rec, policy))

a = rec.surge_assessment
if consider_surge:
    s1, s2 = st.columns(2)
    with s1:
        ui.card(
            "Extra (surge) bed",
            "Open it"
            if rec.surge
            else "Optional: your call"
            if rec.found and a.det_diff_ci is not None and a.det_diff_ci[1] < 0
            else "Not needed"
            if rec.found
            else "Does not rescue",
            a.reason,
            presentation.TEAL if rec.surge else presentation.INK,
        )
    with s2:
        if a.det_without is not None and a.det_with is not None:
            diff = (
                ""
                if a.det_diff_ci is None
                else f" (paired 95% interval {a.det_diff_ci[0]:.1f} to {a.det_diff_ci[1]:.1f})"
            )
            per = (
                ""
                if a.bed_days_per_event_avoided is None
                else f" About <b>{a.bed_days_per_event_avoided:.0f}</b> bed-days opened per deterioration avoided."
            )
            ui.card(
                "Cost against harm avoided",
                f"{a.bed_days_opened:.0f} bed-days a year",
                f"Opened, and used on about {a.bed_days_used:.0f} days. Worsening a year: "
                f"{a.det_without:.1f} without, {a.det_with:.1f} with{diff}.{per}",
            )
        else:
            ui.card(
                "Cost against harm avoided",
                f"{a.bed_days_opened:.0f} bed-days a year",
                "Bed-days the surge bed is open if used in the recommended plan; the comparison "
                "needs a feasible plan without it.",
            )

left, right = st.columns(2, gap="large")
with left:
    ui.show(charts.plan_success(rec, threshold_pct / 100))
with right:
    ui.show(charts.plan_harm(rec))

with st.expander("Seed check: the plan on 30 other seeds"):
    if rec.seed_check is not None:
        sc = rec.seed_check
        st.markdown(
            f"On {sc.n} further seeds the plan met every condition in **{100 * sc.p_ok:.0f}%** "
            f"(95% interval {100 * sc.ci[0]:.0f}–{100 * sc.ci[1]:.0f}%). "
            f"Worsening a year: mean {sc.det_mean:.1f}, 5th–95th percentile {sc.det_p5:.0f}–{sc.det_p95:.0f}."
        )
        st.dataframe(
            pd.DataFrame(
                sc.per_seed,
                columns=["Seed", "Patients who worsen", "List change", "Mean occupancy", "Holds"],
            ),
            hide_index=True,
        )
        fails = {k: v for k, v in rec.check.failures.items()} if rec.check else {}
        if fails:
            st.caption(
                "Share of the 200 fresh years failing each condition: "
                + "; ".join(f"{k} {100 * v:.0f}%" for k, v in fails.items())
            )
    else:
        st.caption("No plan to check.")

with st.expander("Where the numbers come from"):
    st.markdown(
        f"- **Deterioration rates ({pset.label}):** "
        + ", ".join(
            f"{n} {r * 100:.2f}% a week"
            for n, r in zip(("2 to 1", "3 to 2", "4 to 3"), pset.cicu_rates()[1:], strict=True)
        )
        + f". {pset.notes}\n"
        "- **Occupancy target:** the default is 85%. No published source for a safe "
        "level was found (awaiting source); it is yours to change.\n"
        "- **Surge bed:** takes only elective cases whose usual stay is at most the short-stay limit; "
        "it sits outside the occupancy target and is counted in bed-days.\n"
        "- **Not validated against real data.** Every input is synthetic until you enter your own."
    )

ui.section("Your current plan, deterministic view (v2)")
c1, c2, c3 = st.columns(3)
with c1:
    ui.card(
        "Inherited urgent-only test",
        "None in 3–14" if recommended is None else f"{recommended} / week",
        "The v1 criterion: clears urgent cases and keeps load within beds. It does not look at the "
        "routine backlog, so it is no longer the recommendation",
        presentation.INK,
    )
with c2:
    ui.card(
        "Peak CICU load",
        f"{peak:.1f}",
        f"Beds taken on the busiest day, from operated patients; <b>{beds}</b> available",
        det_status.colour,
    )
with c3:
    ui.card(
        "Final backlog",
        f"{float(summary['finalBacklog']):g}",
        f"Cumulative backlog cost: <b>{float(summary['totalCost']):,.0f} cost units</b>",
    )

left, right = st.columns(2, gap="large")
with left:
    ui.show(
        charts.stacked_backlog(
            weekly,
            [f"cat{i}_closing" for i in range(1, 5)],
            LABELS,
            "WAITING LIST BY CATEGORY",
        )
    )
with right:
    ui.show(
        charts.line_vs_limit(
            weekly,
            "cicu_peak_daily",
            beds,
            "CICU LOAD · BUSIEST DAY OF EACH WEEK",
            f"CICU BEDS ({beds})",
        )
    )
ui.show(charts.capacity_search(table, beds))

ui.section("Final backlog per category")
final = weekly.iloc[-1]
st.dataframe(
    pd.DataFrame(
        {
            "Category": LABELS,
            "Final backlog": [float(final[f"cat{i}_closing"]) for i in range(1, 5)],
            "CICU stay (days)": list(params.los_days),
        }
    ),
    hide_index=True,
)
if show_v1:
    ui.section("Compare with v1 (previous model)")
    with st.container(border=True):
        sim1 = CicuSimulator(capacity, params)
        peak1 = float(sim1.simulate(WEEKS)["cicu_occupancy"].to_numpy().max())
        rec1 = cicu.recommended_capacity(sim1.capacity_table(WEEKS))
        d1, d2 = st.columns(2)
        with d1:
            ui.card(
                "v1 peak CICU load",
                f"{peak1:.1f}",
                f"Counted from the waiting list (backlog × stay / 7). v2: <b>{peak:.1f}</b>, "
                "counted from patients who had surgery",
            )
        with d2:
            ui.card(
                "v1 recommended capacity",
                "None in 3–14" if rec1 is None else f"{rec1} / week",
                "In v1 more surgery shrank the backlog and so lowered the reported load, "
                "which is why no capacity ever passed",
            )
ui.footnote(
    "CICU load in the deterministic view is estimated from patients who have had surgery: weekly "
    "cases spread over five theatre days, each holding a bed for its stay and freed on the "
    "discharge day. The recommended plan comes from a seeded simulation with per-patient "
    "deterioration. Prototype on synthetic parameters, not validated."
)
