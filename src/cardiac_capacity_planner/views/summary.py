# ruff: noqa: E501  (plain-language page text)
"""Decision summary: the first screen. What to do, what happens if we do nothing, the levers,
staffing as a constraint, and what the model assumes because data is missing.

Built on the CICU planning engine (``cardiac_capacity.cicu_policy``): theatre sessions, CICU beds
and a waiting list that gets more urgent over time. Every number is the median of 60 simulated
years; ranges are the 5th to 95th percentile.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from cardiac_capacity import cicu_policy as cp
from cardiac_capacity import diagnoses
from cardiac_capacity_planner import charts, scenarios, ui

with st.sidebar:
    ui.section("Your service today")
    slots = int(st.number_input("Theatre sessions a week (operations)", 1, 20, 5, 1))
    beds = int(st.number_input("CICU beds", 1, 40, 10, 1))
    backlog = int(st.number_input("Children on the waiting list now", 0, 400, 60, 5))
    referrals = float(st.number_input("New referrals a week", 0.0, 30.0, 6.0, 0.5))
    ui.section("Staffing limits")
    st.caption("Enter what your staff can cover. 0 means not entered (staffing not limiting).")
    staffed_sessions = int(st.number_input("Theatre sessions staff can cover a week", 0, 40, 0, 1))
    staffed_beds = int(st.number_input("CICU beds nurses can staff", 0, 60, 0, 1))
    ui.section("Options to compare")
    step = int(st.slider("Size of each change", 1, 4, 2))
    target_pct = st.slider("Highest comfortable CICU occupancy (%)", 50, 100, 85)

mix = diagnoses.build_mix(st.session_state.get("yours", {}))

base = cp.PolicyParams(
    slots=slots,
    beds=beds,
    target_occupancy=target_pct / 100,
    weekly_referrals=referrals,
    initial_backlog=backlog,
    deterioration_rates=(0.0, 0.0, 0.0, 0.0),
    casemix=mix.casemix,
)


@st.cache_data(show_spinner="Simulating 60 possible years for each option…")
def compare(
    base: cp.PolicyParams, step: int, ss: int, sb: int
) -> tuple[list[scenarios.Outcome], dict[str, tuple[list[int], ...]]]:
    opts = scenarios.options(base.slots, base.beds, step)
    outs = [scenarios.evaluate(base, o, ss, sb) for o in opts]
    bands = {o.key: scenarios.weekly_list(base, o) for o in opts}
    return outs, bands


outs, bands = compare(base, step, staffed_sessions, staffed_beds)
now = outs[0]
pick = scenarios.recommend(outs)
SHORT = {
    "nothing": "Do nothing",
    "sessions": f"+{step} sessions",
    "beds": f"+{step} beds",
    "both": f"+{step} sessions<br>+{step} beds",
}
labels = [SHORT[o.option.key] for o in outs]
highlight = outs.index(pick) if pick else None

ui.band(
    "Cardiac surgery waiting list: what to do",
    "Scenario planner by diagnosis · published figures · 52-week view · not a forecast",
    f"Do: {pick.option.label if pick else 'no option is enough'} · If nothing changes: list "
    f"{now.list_start:.0f} → {now.list_end:.0f}, {now.past_window:.0f} past their window",
)

has_det = any(g.delay is not None for g in mix.casemix.groups)  # only from "your figures"

# --- What we need to do ------------------------------------------------------------------
if now.stops_growth and now.clears and now.occupancy_ok and now.past_window < 1:
    headline = "No change needed: the list is cleared as things are."
    because = f"With {slots} sessions and {beds} CICU beds, the list goes from {now.list_start:.0f} to about {now.list_end:.0f} in 52 weeks."
    why = ""
elif pick is None:
    headline = "None of the changes tested clears the list."
    because = (
        f"Even +{step} sessions and +{step} beds leave about {outs[3].list_end:.0f} children waiting "
        "after 52 weeks, or the beds run above your comfortable level. Larger changes, or fewer referrals, are needed."
    )
    why = ""
else:
    headline = f"{pick.option.label}."
    because = (
        f"Waiting list in 52 weeks: <b>{pick.list_end:.0f}</b> (do nothing: <b>{now.list_end:.0f}</b>). "
        f"Cancelled operations: {now.cancelled:.0f} to {pick.cancelled:.0f}. "
        f"Children past their window: {now.past_window:.0f} to {pick.past_window:.0f}. "
    )
    trade = scenarios.tradeoff(outs, pick)
    if trade:
        because += f"<b>Trade-off:</b> {trade} "
    if pick.staffing_ok and staffed_sessions <= 0 and staffed_beds <= 0:
        because += "Staffing is not set. Enter limits in Your service today."
    elif pick.staffing_ok:
        because += "Within the staffing limits you entered."
    else:
        because += f"<b>Staffing is the constraint:</b> {pick.staffing.lower()}."
    why = (
        "This is the smallest change tested that clears the list (at most one week of new referrals waiting at week 52, "
        f"in 9 of 10 simulated years), adds no more than 2 cancellations a year and keeps average CICU occupancy at or below {target_pct}%."
    )
st.markdown(
    f'<div class="ccp-do"><div class="mm-label-sm">What we need to do</div>'
    f'<div class="headline">{escape(headline)}</div><div class="because">{because}</div></div>',
    unsafe_allow_html=True,
)
reasons = sorted({why_ for _, why_ in mix.excluded})
left_out = ", ".join(lbl for lbl, _ in mix.excluded)
n_unpub = diagnoses.unpublished_inputs(mix)
n_left = len(mix.excluded)
st.markdown(
    f'<div class="ccp-gaps"><b>Left out of this recommendation:</b> {n_left} of {len(diagnoses.DIAGNOSES)} '
    f"diagnoses ({escape('; '.join(reasons)) if reasons else 'none'}). "
    f"<b>{n_unpub}</b> inputs used here are not from published data (proxies).</div>",
    unsafe_allow_html=True,
)
left_out_md = (
    (f"**Left out:** {escape(left_out)}. " if left_out else "Nothing is left out. ")
    + "Enter your figures on the **By diagnosis** page to include them."
    + (f" **Yours:** {escape('; '.join(mix.yours))}." if mix.yours else "")
)

# --- If we do nothing --------------------------------------------------------------------
ui.section("If we do nothing")
tiles = [
    (
        f"{now.list_start:.0f} → {now.list_end:.0f}",
        "Children waiting, now → week 52",
        f"Range: {now.list_end_lo:.0f} to {now.list_end_hi:.0f}",
    ),
    (f"{now.cancelled:.0f}", "Operations cancelled", "No bed free, 52 weeks"),
    (
        f"{now.past_window:.0f}",
        "Children past their window",
        f"Range: {now.past_window_lo:.0f} to {now.past_window_hi:.0f}",
    ),
]
if has_det:
    tiles.append(
        (
            f"{now.worsen:.0f}",
            "Got worse after the window",
            "Uses your weekly figure",
        )
    )
tiles += [
    (f"{now.over_26_end:.0f}", "Waiting over 26 weeks", "At week 52"),
    (
        f"{100 * now.occupancy:.0f}%",
        "Average CICU occupancy",
        f"Planned beds full {100 * now.weeks_at_limit:.0f}% of weeks",
    ),
]
ui.kpis(tiles)
numbers_md = (
    "Typical year of 60 simulated years. A child is **past the window** when the wait is longer than the "
    "published safe time for that diagnosis. Ranges cover 9 in 10 simulated years. "
    f"Planned beds are the beds open to planned operations ({now.elective_beds} of {beds}); the rest stay free for emergencies."
    + (
        " **Got worse after the window** counts children who deteriorated, using the weekly chance you entered."
        if has_det
        else " No published weekly chance of getting worse exists for these diagnoses, so none is counted."
    )
)

with st.expander("If we do nothing, by diagnosis"):
    names = {d.key: d.label for d in diagnoses.DIAGNOSES} | {
        "hlhs2": "HLHS, second operation (planned)"
    }
    dx_rows = "".join(
        f"<tr><td data-label='Diagnosis'>{escape(names[k])}</td>"
        f'<td class="num" data-label="Operated in 52 weeks">{done:.0f}</td>'
        f'<td class="num" data-label="Past their operating window">{late:.0f}</td></tr>'
        for k, done, late in now.by_diagnosis
    )
    st.markdown(
        '<table class="ccp-table"><thead><tr><th>Diagnosis</th><th>Operated in 52 weeks</th>'
        f"<th>Past their operating window</th></tr></thead><tbody>{dx_rows}</tbody></table>",
        unsafe_allow_html=True,
    )

    st.markdown(left_out_md)

# --- Levers ------------------------------------------------------------------------------
ui.section("What each lever does, and what staffing allows")
head = (
    "<tr><th>Option</th><th>Children waiting at week 52</th><th>Operations cancelled</th>"
    "<th>Children past their operating window</th><th>Chance the list is cleared</th>"
    "<th>CICU occupancy (average · weeks planned-surgery beds full)</th><th>Staffing</th></tr>"
)
rows = ""
for o in outs:
    is_pick = pick is not None and o is pick
    cls = ' class="pick"' if is_pick else ""
    mark = " (recommended)" if is_pick else ""
    rows += (
        f"<tr{cls}><td data-label='Option' class='opt'>{escape(o.option.label)}{mark}</td>"
        f'<td class="num" data-label="Children waiting at week 52">{o.list_end:.0f} <span style="color:#6E7B80">({o.list_end_lo:.0f} to {o.list_end_hi:.0f})</span></td>'
        f'<td class="num" data-label="Operations cancelled">{o.cancelled:.0f}</td><td class="num" data-label="Children past their operating window">{o.past_window:.0f}</td>'
        f'<td class="num" data-label="Chance the list is cleared">{100 * o.p_cleared:.0f}%</td><td class="num" data-label="CICU occupancy (average · weeks planned-surgery beds full)">{100 * o.occupancy:.0f}% · {100 * o.weeks_at_limit:.0f}%</td>'
        f"<td data-label='Staffing'>{escape(o.staffing.replace(' (not limiting)', ''))}</td></tr>"
    )
st.markdown(
    f'<table class="ccp-table"><thead>{head}</thead><tbody>{rows}</tbody></table>',
    unsafe_allow_html=True,
)
with st.expander("What this means"):
    st.markdown(
        (why + "\n\n" if why else "")
        + numbers_md
        + "\n\nEach row is a 52-week simulation repeated 60 times; bracketed ranges cover 9 in 10 of the simulated years. "
        "Extra sessions help only if there are beds behind them, and extra beds help only if the theatre can fill them. "
        "Staffing is a limit: an option that needs more staff than you have is not yet available."
    )

# --- Charts ------------------------------------------------------------------------------
with st.expander("Charts behind the summary"):
    left, right = st.columns(2, gap="large")
    with left:
        other = bands[pick.option.key] if pick else None
        ui.show(
            charts.list_compare(bands["nothing"], other, pick.option.label if pick else ""),
            "The grey line is the waiting list if nothing changes; the teal line is the list with the recommended change. "
            "Shaded areas cover 9 in 10 simulated years. Where the lines separate, the change is making a difference.",
        )
    with right:
        ui.show(
            charts.option_bars(
                labels,
                [o.past_window for o in outs],
                [o.past_window_lo for o in outs],
                [o.past_window_hi for o in outs],
                "CHILDREN PAST THEIR OPERATING WINDOW (52 WEEKS)",
                "Children",
                highlight=highlight,
            ),
            "Lower is better. Each child past the window waited longer than the published safe time for that diagnosis. "
            "Bars show a typical year; lines show the range across simulated years.",
        )
    left, right = st.columns(2, gap="large")
    with left:
        over = [100 * o.weeks_at_limit for o in outs]
        ui.show(
            charts.option_bars(
                labels,
                over,
                over,
                over,
                "WEEKS WHEN THE BEDS FOR PLANNED OPERATIONS WERE ALL TAKEN (%)",
                "Weeks (%)",
                highlight=highlight,
            ),
            f"The unit keeps {100 - target_pct}% of its beds free for emergencies, so planned operations can use only "
            f"{now.elective_beds} of {beds}. When those are taken an operation is cancelled even though the average "
            "occupancy looks low. Read this chart next to the cancellations chart.",
        )
    with right:
        can = [o.cancelled for o in outs]
        ui.show(
            charts.option_bars(
                labels,
                can,
                can,
                can,
                "OPERATIONS CANCELLED BECAUSE NO BED WAS FREE (52 WEEKS)",
                "Operations",
                highlight=highlight,
            ),
            "Cancellations show where the beds, not the theatre, are the limit. If extra sessions raise this number, the beds behind the theatre need to grow too.",
        )

# --- Data gaps ---------------------------------------------------------------------------
n_in, n_all = len(mix.included), len(diagnoses.DIAGNOSES)
with st.expander("What the model assumes because data is missing"):
    st.markdown(
        f"- **{n_in} of {n_all} diagnoses** have the figures to be planned. The rest are left out, not guessed.\n"
        "- **Getting worse while waiting:** no diagnosis has a published weekly chance. "
        "The planner counts children past their window and adds no deterioration unless you enter a figure.\n"
        "- **Referrals:** your referrals a week are spread over the planned diagnoses only, by each diagnosis's "
        "share of operations. These are shares of operations, not of referrals.\n"
        "- **Stays:** published medians are used as average stays. Real stays vary more.\n\n"
        "Where a published figure exists it is used and cited. Where none does, enter your own on the "
        "By diagnosis page and the whole page recalculates."
    )
ui.sources_panel()
ui.footnote(
    "A scenario planner, not a forecast and not validated against real data. It shows a range of "
    "possible years under stated assumptions."
)
