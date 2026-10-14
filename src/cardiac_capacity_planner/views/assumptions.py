# ruff: noqa: E501  (plain-language page text)
"""Assumptions and sources: the whole diagnosis table with a source and DOI on every value."""

from __future__ import annotations

import streamlit as st

from cardiac_capacity import diagnoses, evidence
from cardiac_capacity_planner import ui

ui.band("Assumptions and sources", "Every value has a source and a DOI, or shows as a gap")
c = diagnoses.counts()
st.markdown(
    f'<div class="ccp-gaps"><b>{sum(c.values())} cells:</b> {c["F"]} published for exactly this (F), '
    f"{c['P']} nearby published figure (P), {c['G']} no figure (G). "
    "No value is invented. The data has not been checked by a clinician.</div>",
    unsafe_allow_html=True,
)
ui.section("Limits you should know")
st.markdown(
    "- **Getting worse while waiting:** no diagnosis has a published weekly chance. The only delay odds ratio found (transposition with VSD, repair after day 8) measures complications after surgery and states no waiting time, so it is not used. Enter your own weekly figure to count deterioration. It is used as entered, with no uncertainty band.\n"
    "- **When a source states the waiting time,** the planner can convert its odds ratio: risk ratio (Zhang and Yu 1998), then a constant weekly hazard, with the 95% interval as the band.\n"
    "- **Untreated survival** figures are upper bounds for a child with no treatment. The planner does not use them as waiting risk.\n"
    "- **Shares** are shares of operations in a national audit, not shares of referrals.\n"
    "- **Stays** are published medians used as average stays."
)
ui.section("The full table")
st.markdown(diagnoses.table_markdown())
ui.section("Service size")
st.markdown(evidence.service_table_markdown())
ui.footnote("A scenario planner, not a forecast. Not a medical device.")
