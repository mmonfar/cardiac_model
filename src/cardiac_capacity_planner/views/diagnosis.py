# ruff: noqa: E501  (plain-language page text)
"""By diagnosis: what the planner knows about each diagnosis, and where you can enter your own figures.

Each cell shows its status (F published, P nearby published figure, G no figure) and its source. A
blank "your figure" keeps the published value. Entered figures are labelled "yours" on every page and
one button resets them.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from cardiac_capacity import diagnoses
from cardiac_capacity_planner import ui

INPUTS = (
    # key, label, min, max, step, scale (shown unit -> stored)
    ("window", "Operating window ends after (weeks)", 0.0, 520.0, 1.0, 1.0),
    (
        "deterioration",
        "Chance of getting worse each week, once past the window (%)",
        0.0,
        100.0,
        0.5,
        100.0,
    ),
    ("cicu", "CICU stay (days)", 0.5, 60.0, 0.5, 1.0),
    ("ward", "Ward stay (days)", 0.5, 60.0, 0.5, 1.0),
    ("share", "Share of operations (%)", 0.0, 100.0, 0.5, 100.0),
)

ui.band("By diagnosis", "Published figures · enter yours to replace or fill any cell")

mix_now = diagnoses.build_mix(st.session_state.get("yours", {}))
c = diagnoses.counts()
n_in, n_all = len(mix_now.included), len(diagnoses.DIAGNOSES)
st.markdown(
    f'<div class="ccp-do"><div class="mm-label-sm">What this page shows</div>'
    f'<div class="headline">{n_in} of {n_all} diagnoses have the figures to be planned.</div>'
    f'<div class="because">Of {sum(c.values())} cells, <b>{c["F"]}</b> are published for exactly this, '
    f"<b>{c['P']}</b> use a nearby published figure and <b>{c['G']}</b> have no figure. "
    "A diagnosis with no CICU stay is left out of the default recommendation. Enter your figure to include it.</div></div>",
    unsafe_allow_html=True,
)


def _cell(cell: diagnoses.Cell, scale: float = 1.0, unit: str = "") -> str:
    if cell.value is None:
        body = "enter your figures" if cell.status == "G" else "see source"
    else:
        body = f"{round(cell.value * scale, 1):g}{unit}"
    return f"<b>{cell.status}</b> {escape(body)}"


head = (
    "<tr><th>Diagnosis</th><th>Window (weeks)</th><th>CICU stay (days)</th><th>Ward stay (days)</th>"
    "<th>Share of operations</th><th>Weekly deterioration past the window</th><th>In the recommendation</th></tr>"
)
rows = ""
for d in diagnoses.DIAGNOSES:
    inside = d.key in mix_now.included
    det = (
        f"{100 * d.delay.band()[0]:.0f}% to {100 * d.delay.band()[2]:.0f}% (centre {100 * d.delay.band()[1]:.0f}%)"
        if d.delay
        else "enter your figures"
    )
    rows += (
        f"<tr><td data-label='Diagnosis'>{escape(d.label)}</td>"
        f'<td class="num" data-label="Window (weeks)">{_cell(d.window)}</td>'
        f'<td class="num" data-label="CICU stay (days)">{_cell(d.cicu)}</td>'
        f'<td class="num" data-label="Ward stay (days)">{_cell(d.ward)}</td>'
        f'<td class="num" data-label="Share of operations">{_cell(d.share, 100, "%")}</td>'
        f'<td data-label="Weekly deterioration past the window">{det}</td>'
        f"<td data-label='In the recommendation'>{'Yes' if inside else 'No: ' + escape(dict(mix_now.excluded)[d.label])}</td></tr>"
    )
st.markdown(
    f'<table class="ccp-table"><thead>{head}</thead><tbody>{rows}</tbody></table>',
    unsafe_allow_html=True,
)
ui.what_it_means(
    "F means published for exactly this. P means a nearby published figure. G means no figure: enter yours below. "
    "No published figure states a waiting time, so weekly deterioration is blank for every diagnosis. Enter yours to count it."
)

ui.section("Your figures")
saved: dict[str, dict[str, float]] = st.session_state.get("yours", {})


def _reset() -> None:
    for k in list(st.session_state):
        if str(k).startswith("in_"):
            st.session_state[k] = None
    st.session_state["yours"] = {}


st.button("Reset all to published figures", on_click=_reset)
yours: dict[str, dict[str, float]] = {}
for d in diagnoses.DIAGNOSES:
    with st.expander(d.label):
        for name, label, lo, hi, step, scale in INPUTS:
            cell = d.cell(name)
            prev = saved.get(d.key, {}).get(name)
            st.caption(
                f"{label}. Published: {cell.status} · {cell.text}"
                + (f" · {cell.source}" if cell.source else "")
            )
            v = st.number_input(
                label,
                min_value=lo,
                max_value=hi,
                value=None if prev is None else prev * scale,
                step=step,
                key=f"in_{d.key}_{name}",
                placeholder="Blank keeps the published figure"
                if cell.usable
                else "Enter your figure",
                label_visibility="collapsed",
            )
            if v is not None:
                yours.setdefault(d.key, {})[name] = v / scale
st.session_state["yours"] = yours
ui.footnote(
    "Your figures are labelled yours on the Decision summary. They are not checked against any source."
)
