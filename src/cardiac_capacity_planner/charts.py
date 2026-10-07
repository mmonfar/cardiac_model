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


def _axes(fig: go.Figure, x: str, y: str) -> None:
    """Labelled units on both axes, and room for them."""
    fig.update_xaxes(title_text=x)
    fig.update_yaxes(title_text=y)
    fig.update_layout(margin={**_MARGIN, "b": 56, "l": 64})


def list_compare(
    nothing: tuple[list[int], ...], other: tuple[list[int], ...] | None, other_label: str
) -> go.Figure:
    """Waiting list by week: do nothing against the recommended change (median and range)."""
    fig = go.Figure()
    for data, name, colour, fill in (
        (nothing, "If we do nothing", INK_LABEL, "rgba(23, 36, 43, 0.10)"),
        (other, other_label, tokens.TEAL, BAND),
    ):
        if data is None:
            continue
        w, med, lo, hi = data
        fig.add_trace(go.Scatter(x=w, y=hi, line={"width": 0}, hoverinfo="skip", showlegend=False))
        fig.add_trace(
            go.Scatter(
                x=w, y=lo, fill="tonexty", fillcolor=fill, line={"width": 0},
                hoverinfo="skip", showlegend=False,
            )
        )  # fmt: skip
        fig.add_trace(go.Scatter(x=w, y=med, name=name, line={"color": colour, "width": 3}))
    fig.update_layout(
        title="PATIENTS ON THE WAITING LIST, WEEK BY WEEK",
        height=460, template=TEMPLATE, margin=_MARGIN,
        legend={"orientation": "h", "y": -0.45},
    )  # fmt: skip
    _axes(fig, "Week from today", "Patients waiting")
    fig.update_layout(margin={**_MARGIN, "b": 110, "l": 64})
    return fig


def option_bars(
    labels: list[str], values: list[float], lo: list[float], hi: list[float], title: str,
    y_title: str, highlight: int | None = None, limit: float | None = None, limit_label: str = "",
) -> go.Figure:  # fmt: skip
    """One bar per option (median), with the 5th-95th range as a line."""
    colours = [tokens.TEAL if i == highlight else "#BBDBD8" for i in range(len(values))]
    fig = go.Figure(
        go.Bar(
            x=labels, y=values, marker={"color": colours},
            error_y={
                "type": "data", "symmetric": False, "visible": True, "color": INK_LABEL,
                "array": [h - v for h, v in zip(hi, values, strict=True)],
                "arrayminus": [v - lo_ for v, lo_ in zip(values, lo, strict=True)],
            },
        )
    )  # fmt: skip
    fig.add_trace(
        go.Scatter(
            x=labels, y=hi, mode="text", hoverinfo="skip", textposition="top center",
            text=[f"{v:.0f}" for v in values], textfont={"size": 12, "color": "#17242B"},
        )
    )  # fmt: skip
    fig.update_yaxes(rangemode="tozero")
    if limit is not None:
        _threshold(fig, limit, limit_label)
    fig.update_layout(title=title, height=320, template=TEMPLATE, margin=_MARGIN, showlegend=False)
    _axes(fig, "", y_title)
    return fig


def _threshold(fig: go.Figure, y: float, text: str) -> None:
    fig.add_hline(
        y=y,
        line_dash="5px,5px",
        line_color=THRESHOLD,
        annotation_text=text,
        annotation_font_color=INK_LABEL,
    )


def band_chart(
    band: pd.DataFrame, title: str, marker_week: int | None = None, y_title: str = "Patients"
) -> go.Figure:
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
    _axes(fig, "Week", y_title)
    return fig


def stacked_backlog(
    weekly: pd.DataFrame,
    columns: Sequence[str],
    labels: Sequence[str],
    title: str,
    y_title: str = "Patients waiting",
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
    fig.update_layout(
        title=title, height=340, template=TEMPLATE, margin=_MARGIN,
        legend={"orientation": "h", "y": -0.28},
    )  # fmt: skip
    _axes(fig, "Week", y_title)
    return fig


def line_vs_limit(
    weekly: pd.DataFrame,
    column: str,
    limit: float,
    title: str,
    limit_label: str,
    y_title: str = "Beds in use",
) -> go.Figure:
    fig = go.Figure(
        go.Scatter(x=weekly["week"], y=weekly[column], line={"color": tokens.TEAL, "width": 3})
    )
    _threshold(fig, limit, limit_label)
    fig.update_layout(title=title, height=300, template=TEMPLATE, margin=_MARGIN, showlegend=False)
    _axes(fig, "Week", y_title)
    return fig


def capacity_search(table: pd.DataFrame, beds: float) -> go.Figure:
    colours = [tokens.TEAL if ok else "#BBDBD8" for ok in table["meetsCriteria"]]
    fig = go.Figure(go.Bar(x=table["capacity"], y=table["maxCICU"], marker={"color": colours}))
    _threshold(fig, beds, f"CICU BEDS ({beds:g})")
    fig.update_layout(
        title="PEAK CICU BEDS IN USE FOR EACH WEEKLY SURGERY RATE",
        height=300,
        template=TEMPLATE,
        margin=_MARGIN,
        showlegend=False,
        xaxis={"dtick": 1},
    )
    _axes(fig, "Operations a week", "Peak beds in use")
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
        title="HOW OFTEN EACH PLAN WORKS, BY OPERATIONS A WEEK",
        height=300,
        template=TEMPLATE,
        margin=_MARGIN,
        xaxis={"dtick": 1},
        yaxis={"range": [0, 102]},
        legend={"orientation": "h", "y": -0.62},
    )
    _axes(fig, "Operations a week", "Simulated years where the plan works (%)")
    fig.update_layout(margin={**_MARGIN, "b": 130, "l": 64}, height=360)
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
        title="PATIENTS WHO GET MORE URGENT IN A YEAR, BY OPERATIONS A WEEK",
        height=300,
        template=TEMPLATE,
        margin=_MARGIN,
        xaxis={"dtick": 1},
        legend={"orientation": "h", "y": -0.62},
    )
    _axes(fig, "Operations a week", "Patients who get more urgent")
    fig.update_layout(margin={**_MARGIN, "b": 130, "l": 64}, height=360)
    return fig
