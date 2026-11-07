# ruff: noqa: E501  (plain-language page text)
"""Past what-if consultations: list, open one, export. Local file, append-only."""

from __future__ import annotations

import streamlit as st

from cardiac_capacity import decision_log
from cardiac_capacity_planner import ui, whatif_ui as wu

ui.band("Past what-if consultations", "Saved on this computer only · cannot be edited")
con = decision_log.open_log(wu.log_path())
data = decision_log.rows(con)
if not data:
    st.markdown("### Nothing saved yet")
    st.caption("When you record a decision on the What-if page, it appears here.")
    st.page_link("views/whatif.py", label="Start a what-if test", icon=":material/play_arrow:")
else:
    st.dataframe(
        [
            {"No.": r["id"], "Date (UTC)": r["utc_time"], "Question": r["question"], "Decision": r["decision_choice"], "Decided by": r["decision_by"], "Review on": r["review_date"] or ""}
            for r in reversed(data)
        ],
        hide_index=True,
        use_container_width=True,
        height=min(300, 60 + 35 * len(data)),
    )
    pick = st.selectbox("Open number", [r["id"] for r in reversed(data)])
    st.download_button("Download all as a spreadsheet (CSV)", decision_log.export_csv(con), "what_if_consultations.csv", "text/csv", type="primary")
    with st.expander("One-page print view", expanded=False):
        st.code(wu.print_text(decision_log.get(con, int(pick))), language=None, wrap_lines=True)
