"""Minimal bundled theme for the planner: colour constants, one stylesheet, a Plotly template.

Everything here is self-contained. The two fonts (SIL Open Font License 1.1, see
``fonts/OFL.txt``) are embedded in the page stylesheet, so the app never calls an external
font service and needs no other local folder.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

_DIR = Path(__file__).resolve().parent

CANVAS = "#17242B"  # ink / dark ground
CREAM = "#FDFBF7"  # light ground
TEAL = "#008080"  # the one accent
TEAL_BRIGHT = "#00A3A3"
SERIES = [TEAL, TEAL_BRIGHT, "#60AFAD", "#89C2C0", "#ACD4D1", "#BBDBD8"]

DISPLAY_FONT_STACK = "'Plus Jakarta Sans', 'Segoe UI', system-ui, sans-serif"
LABEL_FONT_STACK = "'Space Grotesk', 'Segoe UI', system-ui, sans-serif"

_FONTS = (
    ("Plus Jakarta Sans", "PlusJakartaSans-Variable.woff2", "200 800"),
    ("Space Grotesk", "SpaceGrotesk-Variable.woff2", "300 700"),
)


@lru_cache(maxsize=1)
def css_text() -> str:
    """The stylesheet with the bundled fonts embedded as ``@font-face`` rules."""
    faces = []
    for family, name, weights in _FONTS:
        data = base64.b64encode((_DIR / "fonts" / name).read_bytes()).decode("ascii")
        faces.append(
            f"@font-face{{font-family:'{family}';font-weight:{weights};font-style:normal;"
            f"font-display:swap;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
        )
    return "".join(faces) + (_DIR / "mmonfar-brand.css").read_text(encoding="utf-8")


def apply(
    st_module: Any,
    *,
    page_title: str | None = None,
    page_icon: str | None = None,
    layout: str = "wide",
) -> None:
    """Set the page config, then inject the stylesheet. Call first in the script."""
    kwargs: dict[str, Any] = {"layout": layout}
    if page_title is not None:
        kwargs["page_title"] = page_title
    if page_icon is not None:
        kwargs["page_icon"] = page_icon
    st_module.set_page_config(**kwargs)
    st_module.markdown(f"<style>{css_text()}</style>", unsafe_allow_html=True)


def _template(bg: str, ink: str, ink_2: str, grid: str) -> go.layout.Template:
    return go.layout.Template(
        layout={
            "colorway": SERIES,
            "paper_bgcolor": bg,
            "plot_bgcolor": bg,
            "font": {"family": DISPLAY_FONT_STACK, "size": 13, "color": ink},
            "title": {
                "font": {"family": LABEL_FONT_STACK, "size": 11, "color": TEAL},
                "x": 0,
                "xanchor": "left",
                "pad": {"b": 16},
            },
            "xaxis": {
                "showgrid": False,
                "zeroline": False,
                "linecolor": grid,
                "linewidth": 1,
                "ticks": "outside",
                "ticklen": 4,
                "tickfont": {"family": LABEL_FONT_STACK, "size": 10, "color": ink_2},
                "title": {"font": {"family": LABEL_FONT_STACK, "size": 10, "color": ink_2}},
            },
            "yaxis": {
                "showgrid": True,
                "gridcolor": grid,
                "gridwidth": 1,
                "zeroline": False,
                "linecolor": grid,
                "linewidth": 0,
                "tickfont": {"family": LABEL_FONT_STACK, "size": 10, "color": ink_2},
                "title": {"font": {"family": LABEL_FONT_STACK, "size": 10, "color": ink_2}},
            },
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "x": 0,
                "font": {"family": LABEL_FONT_STACK, "size": 10, "color": ink_2},
                "bgcolor": "rgba(0,0,0,0)",
            },
            "margin": {"l": 56, "r": 24, "t": 64, "b": 48},
            "colorscale": {"sequential": [[0, "#E4EFEB"], [1, TEAL]]},
            "hoverlabel": {
                "bgcolor": bg,
                "bordercolor": TEAL,
                "font": {"family": LABEL_FONT_STACK, "size": 11, "color": ink},
            },
        },
        data={"scatter": [go.Scatter(line={"width": 2}, marker={"size": 0})]},
    )


def register_plotly() -> None:
    """Register the light ("mmonfar") plotly template and make it the default."""
    pio.templates["mmonfar"] = _template(CREAM, CANVAS, "#6E7B80", "#E3E5E4")
    pio.templates.default = "mmonfar"
