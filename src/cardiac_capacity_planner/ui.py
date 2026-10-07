# ruff: noqa: E501  (plain-language page text)
"""Shared page chrome: app-local CSS on top of the canonical stylesheet, header, cards.

Only brand values appear here (cream ground, white raised panels, hairline borders, zero
radius).
"""

from __future__ import annotations

from html import escape

import streamlit as st

from cardiac_capacity import evidence, parameter_sets
from cardiac_capacity.parameter_sets import ParameterSet
from cardiac_capacity_planner.charts import PLOT_CONFIG
from cardiac_capacity_planner.presentation import INK, StatusView

CSS = """
<style>
  .stApp { background: #FDFBF7; color: #17242B; font-family: var(--mm-font-display); }
  section[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E3E5E4; }
  .ccp-head { padding: 8px 0 28px; border-bottom: 1px solid var(--mm-rule); margin-bottom: 28px; }
  .ccp-head h1 { font: 800 2.4rem/1.05 var(--mm-font-display); letter-spacing: -0.04em;
                 color: #17242B; margin: 10px 0 14px; padding: 0; }
  .ccp-meta { display: flex; flex-wrap: wrap; gap: 8px 28px; }
  .ccp-meta .mm-tick { color: var(--mm-ink-2); font-size: 12px; }
  .ccp-brief { margin-top: 22px; padding: 18px 22px; background: #FFFFFF;
               border: 1px solid #E3E5E4; border-left: 3px solid var(--ccp-state); }
  .ccp-brief .directive { font-size: 1.25rem; font-weight: 700; color: #17242B;
                          letter-spacing: -0.02em; margin-top: 6px; }
  .ccp-card { background: #FFFFFF; border: 1px solid #E3E5E4; padding: 22px 24px;
              min-height: 150px; display: flex; flex-direction: column; margin-bottom: 20px; }
  .ccp-card .value { font: 800 1.9rem/1.1 var(--mm-font-display); letter-spacing: -0.03em;
                     margin: 12px 0 auto; }
  .ccp-card .context { color: var(--mm-ink-2); font-size: 14px; border-top: 1px solid
                       var(--mm-rule); padding-top: 10px; margin-top: 14px; }
  [data-testid="stToolbar"], [data-testid="stDeployButton"], #MainMenu { display: none !important; }
  .ccp-side .mm-wordmark { font-size: 30px; }
  .ccp-band { background: #17242B; color: #FDFBF7; padding: 18px 24px; margin-bottom: 18px;
              display: flex; flex-wrap: wrap; align-items: center; gap: 10px 28px; }
  .ccp-band .mm-wordmark { font-size: 26px; color: #FDFBF7; }
  .ccp-band h1 { font: 800 1.45rem/1.15 var(--mm-font-display); letter-spacing: -0.03em;
                 color: #FDFBF7; margin: 0; padding: 0; }
  .ccp-band .sub { font: 500 11px var(--mm-font-label); letter-spacing: 0.14em;
                   text-transform: uppercase; color: rgba(253,251,247,0.70); }
  .ccp-do { background: #FFFFFF; border: 1px solid #E3E5E4; border-left: 4px solid #008080;
            padding: 20px 24px; margin-bottom: 18px; }
  .ccp-do .headline { font: 800 1.55rem/1.2 var(--mm-font-display); letter-spacing: -0.03em;
                      color: #17242B; margin: 6px 0 10px; }
  .ccp-do .because { color: #17242B; font-size: 15px; line-height: 1.5; }
  .ccp-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
              border: 1px solid #E3E5E4; background: #FFFFFF; margin-bottom: 18px; }
  .ccp-kpi { padding: 14px 18px; border-right: 1px solid #E3E5E4; }
  .ccp-kpi:last-child { border-right: 0; }
  .ccp-kpi .n { font: 800 1.9rem/1.1 var(--mm-font-display); letter-spacing: -0.03em;
                color: #17242B; }
  .ccp-kpi .t { font: 500 10px var(--mm-font-label); letter-spacing: 0.14em;
                text-transform: uppercase; color: #008080; margin-top: 4px; }
  .ccp-kpi .c { font-size: 12.5px; color: #6E7B80; margin-top: 4px; line-height: 1.35; }
  .ccp-table { width: 100%; border-collapse: collapse; background: #FFFFFF;
               border: 1px solid #E3E5E4; font-size: 13.5px; margin-bottom: 8px; }
  .ccp-table th { text-align: left; font: 500 10px var(--mm-font-label); letter-spacing: 0.12em;
                  text-transform: uppercase; color: #008080; padding: 10px 12px;
                  border-bottom: 1px solid #E3E5E4; vertical-align: bottom; }
  .ccp-table td { padding: 10px 12px; border-bottom: 1px solid #E3E5E4; vertical-align: top;
                  color: #17242B; }
  .ccp-table tr.pick td { background: rgba(0,128,128,0.09); font-weight: 700; }
  .ccp-table td.num { white-space: nowrap; }
  .ccp-meaning { color: #17242B; font-size: 14px; line-height: 1.45; margin: 2px 0 22px;
                 padding-left: 12px; border-left: 2px solid #008080; }
  .ccp-meaning b { font: 500 10px var(--mm-font-label); letter-spacing: 0.14em;
                   text-transform: uppercase; color: #008080; margin-right: 6px; }
  .ccp-gaps { background: #FFFFFF; border: 1px solid #E3E5E4; padding: 16px 22px;
              margin-bottom: 18px; }
  .ccp-gaps li { margin: 6px 0; font-size: 14px; line-height: 1.45; }
  @media (max-width: 640px) {
    .ccp-band h1 { font-size: 1.15rem; }
    .ccp-do .headline { font-size: 1.2rem; }
    .ccp-kpi { border-right: 0; border-bottom: 1px solid #E3E5E4; }
    .ccp-table, .ccp-table tbody, .ccp-table tr, .ccp-table td { display: block; width: 100%; }
    .ccp-table thead { display: none; }
    .ccp-table tr { border-bottom: 2px solid #17242B; padding: 6px 0; }
    .ccp-table td { border: 0; padding: 4px 12px; white-space: normal !important; }
    .ccp-table td::before { content: attr(data-label); display: block; font: 500 10px var(--mm-font-label);
                            letter-spacing: 0.12em; text-transform: uppercase; color: #008080; }
    .ccp-head h1 { font-size: 1.6rem; }
  }
</style>
"""


def sidebar_brand() -> None:
    st.sidebar.markdown(
        '<div class="ccp-side mm-on-light"><span class="mm-wordmark">mmonfar'
        '<span class="mm-dot"></span></span></div>',
        unsafe_allow_html=True,
    )


def section(label: str) -> None:
    st.markdown(f'<div class="mm-label-sm">{escape(label)}</div>', unsafe_allow_html=True)


def header(eyebrow: str, title: str, meta: list[str], status: StatusView) -> None:
    ticks = "".join(f'<span class="mm-tick">{escape(m)}</span>' for m in meta)
    st.markdown(
        f"""
<div class="mm-on-light ccp-head">
  <div class="mm-label">{escape(eyebrow)}</div>
  <h1>{escape(title)}</h1>
  <div class="ccp-meta">{ticks}</div>
  <div class="ccp-brief" style="--ccp-state:{status.colour}">
    <div class="mm-label-sm" style="color:{status.colour}">
      Status: <b>{escape(status.label)}</b></div>
    <div class="directive">{escape(status.directive)}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def card(label: str, value: str, context: str, colour: str = INK) -> None:
    """``context`` may carry trusted inline markup (<b>); ``label``/``value`` are escaped."""
    st.markdown(
        f"""<div class="mm-on-light ccp-card"><div class="mm-label-sm">{escape(label)}</div>
<div class="value" style="color:{colour}">{escape(value)}</div>
<div class="context">{context}</div></div>""",
        unsafe_allow_html=True,
    )


def show(fig: object, meaning: str = "") -> None:
    """A chart in a bordered box, with a plain-language "what this means" line under it."""
    # theme=None: keep the mmonfar plotly template instead of Streamlit's own chart theme.
    with st.container(border=True):
        st.plotly_chart(fig, theme=None, config=PLOT_CONFIG)
    if meaning:
        what_it_means(meaning)


def what_it_means(text: str) -> None:
    """``text`` may carry trusted inline markup (<b>)."""
    st.markdown(
        f'<div class="ccp-meaning"><b>What this means</b>{text}</div>', unsafe_allow_html=True
    )


def band(title: str, sub: str) -> None:
    st.markdown(
        f"""<div class="ccp-band"><span class="mm-wordmark">mmonfar<span class="mm-dot"></span></span>
<div><h1>{escape(title)}</h1><div class="sub">{escape(sub)}</div></div></div>""",
        unsafe_allow_html=True,
    )


def kpis(items: list[tuple[str, str, str]]) -> None:
    """A strip of (number, label, one-line context) tiles. Context may carry <b>."""
    tiles = "".join(
        f'<div class="ccp-kpi"><div class="n">{escape(n)}</div><div class="t">{escape(t)}</div>'
        f'<div class="c">{c}</div></div>'
        for n, t, c in items
    )
    st.markdown(f'<div class="ccp-kpis">{tiles}</div>', unsafe_allow_html=True)


def figures_picker() -> ParameterSet:
    """Sidebar choice of deterioration figures: published literature (default) or the user's own."""
    section("Which figures to use")
    choice = st.radio(
        "Starting figures",
        ["literature", "custom"],
        index=0,
        format_func=lambda k: (
            "Published literature (default)" if k == "literature" else "Your figures"
        ),
        help="Literature figures are listed with their sources under 'Where the numbers come from'.",
    )
    if choice == "literature":
        return parameter_sets.get("literature")
    st.caption(
        "Your figures. Chance per week that a waiting child becomes more urgent. Not checked against any source."
    )
    r21 = st.number_input("Urgent to life-threatening (% a week)", 0.0, 50.0, 2.34, 0.1)
    r32 = st.number_input("Semi-urgent to urgent (% a week)", 0.0, 50.0, 1.23, 0.1)
    r43 = st.number_input("Routine to semi-urgent (% a week)", 0.0, 50.0, 0.80, 0.1)
    r54 = st.number_input("Stable to routine (% a week; ward model only)", 0.0, 50.0, 0.0, 0.1)
    lw = st.number_input("Extra risk after 26 weeks waiting (multiplier)", 1.0, 5.0, 1.0, 0.05)
    return parameter_sets.custom(r21 / 100, r32 / 100, r43 / 100, r54 / 100, lw)


def sources_panel() -> None:
    """Every default with its source or the gap it stands in for."""
    with st.expander("Where the numbers come from"):
        st.markdown(
            "Every figure the planner starts with is listed here. Rows marked **assumption** "
            "have no published source: they stand in for your own figures."
        )
        st.markdown(evidence.table_markdown())


def footnote(text: str) -> None:
    st.markdown(
        f'<div class="mm-tick" style="margin-top:24px">{escape(text)}</div>',
        unsafe_allow_html=True,
    )
