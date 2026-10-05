"""Plotly figures, styled with the bundled mmonfar. plot template.

Sequential teal only, no categorical rainbow; threshold lines dashed at 34 % ink; chart
titles are the template's teal label. Inputs are ``cardiac_capacity`` outputs.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import pandas as pd
import plotly.graph_objects as go

from cardiac_capacity_planner import brand as tokens

tokens.register_plotly()

if TYPE_CHECKING:
    from cardiac_capacity.recommend_cicu import CicuRecommendation

TEMPLATE = "mmonfar"
BAND = "rgba(0, 128, 128, 0.16)"  # brand "band"
THRESHOLD = "rgba(23, 36, 43, 0.34)"  # brand threshold line: canvas at 34 %
INK_LABEL = "rgba(23, 36, 43, 0.62)"  # brand secondary text: canvas at 62 %
# The on-light teal cascade, dark (most urgent) to light: the brand's only tint ramp.
CASCADE = [tokens.TEAL, "#60AFAD", "#89C2C0", "#ACD4D1", "#BBDBD8"]
PLOT_CONFIG = {"displayModeBar": False}
_MARGIN = {"t": 48, "b": 24, "l": 48, "r": 16}


def _threshold(fig: go.Figure, y: float, text: str) -> None:
    fig.add_hline(
        y=y,
        line_dash="5px,5px",
        line_color=THRESHOLD,
        annotation_text=text,
        annotation_font_color=INK_LABEL,
    )


def band_chart(band: pd.DataFrame, title: str, marker_week: int | None = None) -> go.Figure:
    """p5–p95 band and p50 line from ``cardiac_capacity.weekly_band``."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=band["week"], y=band["p95"], line={"width": 0}, hoverinfo="skip", name="p95")
    )
    fig.add_trace(
        go.Scatter(
            x=band["week"],
            y=band["p5"],
            fill="tonexty",
            fillcolor=BAND,
            line={"width": 0},
            name="p5–p95",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=band["week"], y=band["p50"], line={"color": tokens.TEAL, "width": 3}, name="p50"
        )
    )
    if marker_week is not None:
        fig.add_vline(x=marker_week, line_dash="5px,5px", line_color=THRESHOLD)
    fig.update_layout(title=title, height=320, template=TEMPLATE, margin=_MARGIN, showlegend=False)
    return fig


def stacked_backlog(
    weekly: pd.DataFrame, columns: Sequence[str], labels: Sequence[str], title: str
) -> go.Figure:
    fig = go.Figure()
    for col, label, colour in zip(columns, labels, CASCADE, strict=False):
        fig.add_trace(
            go.Scatter(
                x=weekly["week"],
                y=weekly[col],
                name=label,
                stackgroup="backlog",
                line={"color": colour, "width": 1},
                fillcolor=colour,
            )
        )
    fig.update_layout(title=title, height=320, template=TEMPLATE, margin=_MARGIN)
    return fig


def line_vs_limit(
    weekly: pd.DataFrame, column: str, limit: float, title: str, limit_label: str
) -> go.Figure:
    fig = go.Figure(
        go.Scatter(x=weekly["week"], y=weekly[column], line={"color": tokens.TEAL, "width": 3})
    )
    _threshold(fig, limit, limit_label)
    fig.update_layout(title=title, height=300, template=TEMPLATE, margin=_MARGIN, showlegend=False)
    return fig


def capacity_search(table: pd.DataFrame, beds: float) -> go.Figure:
    colours = [tokens.TEAL if ok else "#BBDBD8" for ok in table["meetsCriteria"]]
    fig = go.Figure(go.Bar(x=table["capacity"], y=table["maxCICU"], marker={"color": colours}))
    _threshold(fig, beds, f"CICU BEDS ({beds:g})")
    fig.update_layout(
        title="PEAK CICU LOAD BY WEEKLY CAPACITY",
        height=300,
        template=TEMPLATE,
        margin=_MARGIN,
        showlegend=False,
        xaxis={"dtick": 1},
    )
    return fig


def plan_success(rec: CicuRecommendation, threshold: float) -> go.Figure:
    """Share of simulated futures meeting every condition, by elective cases a week.

    Plans the search stopped early (they could no longer reach the threshold) are drawn as open
    markers at the most they could still have reached, so they are never read as measured rates.
    """
    fig = go.Figure()
    for surge, colour, name in (
        (False, tokens.TEAL, "No surge bed"),
        (True, "#89C2C0", "Surge bed"),
    ):
        rows = [e for e in rec.table if e.surge == surge and e.complete]
        if rows:
            fig.add_trace(
                go.Scatter(
                    x=[e.slots for e in rows],
                    y=[100 * e.p_ok for e in rows],
                    name=name,
                    mode="lines+markers",
                    line={"color": colour, "width": 3},
                )
            )
    stopped = [e for e in rec.table if not e.complete]
    if stopped:
        fig.add_trace(
            go.Scatter(
                x=[e.slots for e in stopped],
                y=[100 * (e.n_ok + rec.n_select - e.n) / rec.n_select for e in stopped],
                name="Stopped early: at most",
                mode="markers",
                marker={"symbol": "circle-open", "size": 8, "color": INK_LABEL},
            )
        )
    fig.add_hline(
        y=100 * threshold,
        line_dash="5px,5px",
        line_color=THRESHOLD,
        annotation_text=f"THRESHOLD ({100 * threshold:.0f}%)",
        annotation_position="bottom right",
        annotation_font_color=INK_LABEL,
    )
    fig.update_layout(
        title="FUTURES MEETING EVERY CONDITION (%) BY CASES / WEEK",
        height=300,
        template=TEMPLATE,
        margin=_MARGIN,
        xaxis={"dtick": 1},
        yaxis={"range": [0, 102]},
        legend={"orientation": "h", "y": -0.25},
    )
    return fig


def plan_harm(rec: CicuRecommendation) -> go.Figure:
    """Expected deteriorations a year for plans that reach the threshold."""
    fig = go.Figure()
    for surge, colour, name in (
        (False, tokens.TEAL, "No surge bed"),
        (True, "#89C2C0", "Surge bed"),
    ):
        rows = [e for e in rec.table if e.surge == surge and e.complete and e.p_ok >= rec.threshold]
        if not rows:
            continue
        fig.add_trace(
            go.Scatter(
                x=[e.slots for e in rows],
                y=[e.det_mean for e in rows],
                name=name,
                mode="lines+markers",
                line={"color": colour, "width": 3},
            )
        )
    fig.update_layout(
        title="PATIENTS WHO WORSEN A YEAR (PLANS THAT REACH THE THRESHOLD)",
        height=300,
        template=TEMPLATE,
        margin=_MARGIN,
        xaxis={"dtick": 1},
        legend={"orientation": "h", "y": -0.2},
    )
    return fig
