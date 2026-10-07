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
from cardiac_capacity import evidence
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
    pset = ui.figures_picker()

base = cp.PolicyParams(
    slots=slots,
    beds=beds,
    target_occupancy=target_pct / 100,
    weekly_referrals=referrals,
    initial_backlog=backlog,
    deterioration_rates=pset.cicu_rates(),
    long_wait_or=pset.long_wait_or,
    long_wait_weeks=pset.long_wait_weeks,
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
    "Scenario planner built on published evidence · 52-week view · not a forecast",
)

# --- What we need to do ------------------------------------------------------------------
if now.stops_growth and now.worsen < 1:
    headline = "No change needed: the list stays flat or shrinks as things are."
    because = f"With {slots} sessions and {beds} CICU beds, the waiting list goes from {now.list_start:.0f} to about {now.list_end:.0f} over 52 weeks."
elif pick is None:
    headline = "None of the changes tested is enough: the list keeps growing."
    because = (
        f"Even the largest change tested (+{step} sessions and +{step} beds) leaves about {outs[3].list_end:.0f} children waiting "
        f"after 52 weeks. Larger changes, or fewer referrals, would be needed."
    )
else:
    headline = f"{pick.option.label}."
    because = (
        f"This is the smallest change tested that stops the list growing without adding cancellations (more than 2 a year) where one exists. The list goes from {pick.list_start:.0f} to about "
        f"<b>{pick.list_end:.0f}</b> over 52 weeks, instead of <b>{now.list_end:.0f}</b> if we do nothing. "
        f"Children who get more urgent while waiting change from about {now.worsen:.0f} to {pick.worsen:.0f}. "
    )
    trade = scenarios.tradeoff(outs, pick)
    because += (
        f"Cancelled operations: {now.cancelled:.0f} now, {pick.cancelled:.0f} with this change. "
    )
    if trade:
        because += f"<b>Trade-off:</b> {trade} "
    if pick.staffing_ok and staffed_sessions <= 0 and staffed_beds <= 0:
        because += "You have not entered a staffing limit, so staffing is not yet shown as a constraint (left panel)."
    elif pick.staffing_ok:
        because += "This is within the staffing limits you entered."
    else:
        because += f"<b>Staffing is the constraint:</b> {pick.staffing.lower()}."
st.markdown(
    f'<div class="ccp-do"><div class="mm-label-sm">What we need to do</div>'
    f'<div class="headline">{escape(headline)}</div><div class="because">{because}</div></div>',
    unsafe_allow_html=True,
)

# --- If we do nothing --------------------------------------------------------------------
ui.section("If we do nothing")
ui.kpis(
    [
        (
            f"{now.list_start:.0f} → {now.list_end:.0f}",
            "Children waiting, now → week 52",
            f"Likely range at week 52: {now.list_end_lo:.0f} to {now.list_end_hi:.0f}",
        ),
        (f"{now.cancelled:.0f}", "Operations cancelled (no bed)", "Over 52 weeks, a typical year"),
        (
            f"{now.worsen:.0f}",
            "Children who get more urgent",
            f"Likely range: {now.worsen_lo:.0f} to {now.worsen_hi:.0f}",
        ),
        (f"{now.over_26_end:.0f}", "Waiting over 26 weeks at week 52", "Typical year"),
        (
            f"{100 * now.occupancy:.0f}%",
            "Average CICU occupancy",
            f"Beds for planned operations ({now.elective_beds} of {beds}) all taken in <b>{100 * now.weeks_at_limit:.0f}%</b> of weeks",
        ),
    ]
)

# --- Levers ------------------------------------------------------------------------------
ui.section("What each lever does, and what staffing allows")
head = (
    "<tr><th>Option</th><th>Children waiting at week 52</th><th>Operations cancelled</th>"
    "<th>Children who get more urgent</th><th>Chance the list is shorter</th>"
    "<th>CICU occupancy (average · weeks planned-surgery beds full)</th><th>Staffing</th></tr>"
)
rows = ""
for o in outs:
    is_pick = pick is not None and o is pick
    cls = ' class="pick"' if is_pick else ""
    mark = " (recommended)" if is_pick else ""
    rows += (
        f"<tr{cls}><td data-label='Option'>{escape(o.option.label)}{mark}</td>"
        f'<td class="num" data-label="Children waiting at week 52">{o.list_end:.0f} <span style="color:#6E7B80">({o.list_end_lo:.0f} to {o.list_end_hi:.0f})</span></td>'
        f'<td class="num" data-label="Operations cancelled">{o.cancelled:.0f}</td><td class="num" data-label="Children who get more urgent">{o.worsen:.0f}</td>'
        f'<td class="num" data-label="Chance the list is shorter">{100 * o.p_list_shrinks:.0f}%</td><td class="num" data-label="CICU occupancy (average · weeks planned-surgery beds full)">{100 * o.occupancy:.0f}% · {100 * o.weeks_at_limit:.0f}%</td>'
        f"<td data-label='Staffing'>{escape(o.staffing)}</td></tr>"
    )
st.markdown(
    f'<table class="ccp-table"><thead>{head}</thead><tbody>{rows}</tbody></table>',
    unsafe_allow_html=True,
)
ui.what_it_means(
    "Each row is a 52-week simulation repeated 60 times; bracketed ranges cover 9 in 10 of the simulated years. "
    "Extra sessions help only if there are beds behind them, and extra beds help only if the theatre can fill them. "
    "Staffing is a limit: an option that needs more staff than you have is not yet available."
)

# --- Charts ------------------------------------------------------------------------------
ui.section("Behind the summary")
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
            [o.worsen for o in outs],
            [o.worsen_lo for o in outs],
            [o.worsen_hi for o in outs],
            "CHILDREN WHO GET MORE URGENT WHILE WAITING (52 WEEKS)",
            "Children",
            highlight=highlight,
        ),
        "Lower is better. Each child who gets more urgent while waiting is a child who needed an operation sooner. "
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
ui.section("What the model assumes because data is missing")
items = "".join(f"<li><b>{escape(d.name)}:</b> {escape(d.gap)}</li>" for d in evidence.gaps())
st.markdown(
    f'<div class="ccp-gaps"><ul style="margin:0;padding-left:20px">{items}</ul></div>',
    unsafe_allow_html=True,
)
ui.what_it_means(
    "The answer is only as good as these assumptions. Where a published figure exists it is used and cited. "
    "Where none does, enter your own figures in the left panel and the whole page recalculates."
)
ui.sources_panel()
ui.footnote(
    "A scenario planner, not a forecast and not validated against real data. It shows a range of "
    "possible years under stated assumptions."
)
