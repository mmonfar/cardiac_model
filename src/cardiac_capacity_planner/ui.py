"""Shared page chrome: app-local CSS on top of the canonical stylesheet, header, cards.

Only brand values appear here (cream ground, white raised panels, hairline borders, zero
radius).
"""

from __future__ import annotations

from html import escape

import streamlit as st

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
  .ccp-side .mm-wordmark { font-size: 30px; }
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


def show(fig: object) -> None:
    # theme=None: keep the mmonfar plotly template instead of Streamlit's own chart theme.
    with st.container(border=True):
        st.plotly_chart(fig, theme=None, config=PLOT_CONFIG)


def footnote(text: str) -> None:
    st.markdown(
        f'<div class="mm-tick" style="margin-top:24px">{escape(text)}</div>',
        unsafe_allow_html=True,
    )
