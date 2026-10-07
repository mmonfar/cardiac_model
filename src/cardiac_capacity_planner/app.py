"""Cardiac capacity planner: one app, two modes (ward referral, CICU) over one protocol.

Run from ``apps/cardiac-capacity-planner`` so ``.streamlit/config.toml`` (light theme, zero
radius) is picked up::

    streamlit run src/cardiac_capacity_planner/app.py

All simulation comes from ``cardiac_capacity``; the views only collect parameters, lay out
and style. Every parameter is synthetic until someone enters their own.
"""

from pathlib import Path

import streamlit as st

from cardiac_capacity_planner import brand, ui

brand.apply(st, page_title="Cardiac waiting list planner", page_icon="◼", layout="wide")
st.markdown(ui.CSS, unsafe_allow_html=True)
ui.sidebar_brand()

VIEWS = Path(__file__).resolve().parent / "views"
page = st.navigation(
    [
        st.Page(VIEWS / "summary.py", title="Decision summary", url_path="summary", default=True),
        st.Page(VIEWS / "ward.py", title="Detail: ward beds", url_path="ward"),
        st.Page(VIEWS / "cicu.py", title="Detail: CICU plan", url_path="cicu"),
    ]
)
page.run()

st.caption(
    "Research and demonstration software. Not a medical device and not intended for "
    'clinical decision-making, diagnosis or treatment. Provided "as is", without warranty '
    "of any kind; the author accepts no liability for any use. Uses synthetic data only. "
    "Personal project · not affiliated with any employer · synthetic data only."
)
