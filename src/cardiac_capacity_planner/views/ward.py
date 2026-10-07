# ruff: noqa: E501  (plain-language page text)
"""Ward-referral mode: stochastic waiting list, Monte Carlo across seeds."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from cardiac_capacity import (
    Distribution,
    WardReferralSimulator,
    monte_carlo,
    recommend,
    summarize,
    ward_referral,
    weekly_band,
)
from cardiac_capacity.recommend import Recommendation
from cardiac_capacity.ward_referral import DEFAULT_PARAMS
from cardiac_capacity_planner import charts, presentation, ui

WEEKS = 52


START_MODES = {
    "today": "From today's waiting list",
    "settled": "From a settled state (warm-up first)",
}


@st.cache_data(show_spinner=False)
def run_ensemble(
    params: dict[str, Any], n: int, seed: int, version: str, start_mode: str
) -> tuple[list[pd.DataFrame], Any]:
    sim = WardReferralSimulator(params, model_version=version, start_mode=start_mode)
    return monte_carlo(sim, WEEKS, n=n, seed=seed)


@st.cache_data(show_spinner="Searching beds and slots across simulated futures…")
def search(
    params: dict[str, Any], target: int, threshold: float, start_mode: str, n_select: int
) -> Recommendation:
    return recommend.recommend(
        params, target, threshold, n_select=n_select, n_validate=200, start_mode=start_mode
    )


@st.cache_data(show_spinner=False)
def v1_solver(params: dict[str, Any], target: int) -> tuple[int, int]:
    return ward_referral.find_recommendation(params, target)


@st.cache_data(show_spinner=False)
def success_under_v2(
    params: dict[str, Any], target: int, slots: int, beds: int, start_mode: str
) -> tuple[int, int]:
    """Fresh-seed (n=200) count of futures with no 26+ week waits under the v2 model."""
    cfg = {**params, "surg_per_week": slots, "total_beds": beds}
    return recommend.success_count(cfg, target, 200, 70_000, (), start_mode), 200


with st.sidebar:
    ui.section("Waiting list")
    backlog = st.number_input("Starting backlog", min_value=0, max_value=400, value=60, step=5)
    legacy = st.slider("Legacy cohort (%)", 0, 100, int(DEFAULT_PARAMS["dist_legacy"]))
    refs = st.slider("New referrals / week", 1, 15, int(DEFAULT_PARAMS["weekly_refs"]))
    target = st.slider("Stabilisation goal (week)", 4, WEEKS - 1, 26)
    with st.expander("Referral mix (%)"):
        d1 = st.slider("Cat 1 (most urgent)", 0, 100, 10)
        d2 = st.slider("Cat 2", 0, 100, 15)
        d3 = st.slider("Cat 3", 0, 100, 20)
        d4 = st.slider("Cat 4", 0, 100, 30)
        d5 = max(0, 100 - (d1 + d2 + d3 + d4))
        st.caption(f"Cat 5 (stable): {d5} %")
    ui.section("Capacity")
    slots = st.slider("Surgery slots / week", 1, 12, int(DEFAULT_PARAMS["surg_per_week"]))
    beds = st.slider("Ward beds", 1, 16, int(DEFAULT_PARAMS["total_beds"]))
    buffer = st.slider(
        "Spare beds kept free (safety buffer)", 0, 3, int(DEFAULT_PARAMS["safety_buffer"])
    )
    pset = ui.figures_picker()
    ui.section("Recommendation")
    threshold_pct = st.slider("Success threshold (%)", 50, 99, 90)
    start_label = st.radio("Start from", list(START_MODES.values()), index=0)
    show_v1 = st.checkbox("Show the v1 comparison", value=False)
    start_mode = next(k for k, v in START_MODES.items() if v == start_label)
    if start_mode == "settled":
        st.caption("Settled: the starting list above is ignored; 52 warm-up weeks run first.")
    n_select = int(
        st.select_slider("Futures simulated per setup", options=[60, 100, 200], value=60)
    )
    ui.section("Simulation")
    n_runs = st.select_slider("Runs", options=[10, 20, 50, 100], value=20)
    seed = int(st.number_input("Base seed", min_value=0, max_value=100_000, value=0))
    ui.footnote("Prototype · synthetic parameters")

params = {
    **DEFAULT_PARAMS,
    "total_backlog": int(backlog),
    "dist_legacy": legacy,
    "weekly_refs": refs,
    "dist_cat1": d1,
    "dist_cat2": d2,
    "dist_cat3": d3,
    "dist_cat4": d4,
    "dist_cat5": d5,
    "surg_per_week": slots,
    "total_beds": beds,
    "safety_buffer": buffer,
    **pset.ward_params(),
}

if d1 + d2 + d3 + d4 > 100:
    st.error("The referral mix exceeds 100 %. Lower one of the category sliders.")
    st.stop()

runs, final_breach = run_ensemble(params, n_runs, seed, "v2", start_mode)
at_target: Distribution = summarize(float(r["Over_26_Wks"].iloc[target]) for r in runs)
cancellations = summarize(float(r["cancellations"].to_numpy().sum()) for r in runs)
rec = search(params, target, threshold_pct / 100, start_mode, n_select)
status = presentation.breach_status(at_target, target)

ui.header(
    "Detail · ward beds",
    f"{slots} operations a week · {beds} ward beds",
    [
        f"{n_runs} simulated years",
        pset.label + " · " + START_MODES[start_mode].lower(),
        f"{refs} referrals / week",
    ],
    status,
)

k1, k2, k3 = st.columns(3)
with k1:
    ui.card(
        f"Waiting more than 26 weeks at week {target}",
        presentation.band_text(at_target),
        f"Typical year (range across simulated years). At week {WEEKS - 1}: "
        f"<b>{presentation.band_text(final_breach)}</b>",
        status.colour,
    )
with k2:
    ui.card(
        f"Operations cancelled over {WEEKS} weeks",
        presentation.band_text(cancellations),
        "Typical year (range): operations with no free bed",
    )
with k3:
    if rec.found:
        lo, hi = rec.ci_validate
        ui.card(
            "Recommended set-up",
            f"{rec.slots} operations a week · {rec.beds} beds",
            f"Smallest setup where at least {threshold_pct}% of simulated futures have no "
            f"26+ week waits at week {target}. On {rec.n_validate} fresh runs it did so in "
            f"<b>{100 * rec.p_validate:.0f}%</b> (95% CI {100 * lo:.0f}–{100 * hi:.0f}%)."
            + (" The answer sits at the edge of the search range." if rec.boundary else ""),
        )
    else:
        ui.card(
            "Recommended configuration",
            "None found",
            f"No setup up to 24 beds and 12 slots reaches {threshold_pct}% of futures with "
            f"no 26+ week waits at week {target}.",
            presentation.RED,
        )

left, right = st.columns(2, gap="large")
with left:
    ui.show(
        charts.band_chart(
            weekly_band(runs, "Over_26_Wks"),
            "PATIENTS WAITING MORE THAN 26 WEEKS",
            marker_week=target,
            y_title="Patients",
        ),
        "The line is a typical year and the shaded band covers 9 in 10 simulated years. "
        "The dashed line marks your goal week. The aim is for the line to reach zero by then.",
    )
with right:
    first = runs[0]
    ui.show(
        charts.stacked_backlog(
            first,
            presentation.WARD_CATEGORIES,
            presentation.WARD_CATEGORIES,
            "WAITING LIST BY URGENCY, ONE SIMULATED YEAR",
        ),
        "Darker bands are the most urgent children. A growing dark band means the most urgent "
        "cases are not being operated on fast enough. This is one example year, not an average.",
    )
ui.show(
    charts.line_vs_limit(
        runs[0],
        "occupancy",
        beds - buffer,
        "WARD BEDS IN USE, ONE SIMULATED YEAR",
        f"USABLE BEDS ({beds - buffer})",
        y_title="Beds in use",
    ),
    "When the line touches the dashed limit there is no free bed, so an operation is cancelled. "
    "Repeated touches mean the ward, not the theatre, is the bottleneck.",
)

if show_v1:
    ui.section("Compare with the previous version (v1)")
    with st.container(border=True):
        runs1, _ = run_ensemble(params, n_runs, seed, "v1", "today")
        v1_target = summarize(float(r["Over_26_Wks"].iloc[target]) for r in runs1)
        s1, b1 = v1_solver(params, target)
        k1, n1 = success_under_v2(params, target, s1, b1, start_mode)
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.card(
                f"v1: Waiting more than 26 weeks at week {target}",
                presentation.band_text(v1_target),
                f"Median (p5–p95), same inputs. v2: <b>{presentation.band_text(at_target)}</b>",
            )
        with c2:
            ui.card(
                "v1 recommendation",
                f"{s1} operations a week · {b1} beds",
                "From a single simulated run (seed 42); beds were released once a week",
            )
        with c3:
            ui.card(
                "v1 recommendation under v2",
                f"{100 * k1 / n1:.0f}% of futures clear",
                f"No 26+ week waits at week {target} in {k1} of {n1} fresh v2 runs. "
                "v2 frees beds on the discharge day and follows each patient's own category.",
            )
ui.sources_panel()
ui.footnote(
    "Prototype on synthetic parameters, not validated against real data. The model shows a "
    "range of outcomes, not a forecast. The figures behind patients getting more urgent are published rates "
    "awaiting a clinician's check, or your own."
)
