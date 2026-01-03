import streamlit as st
import pandas as pd
from engine import run_simulation, find_ai_recommendation
from visuals import render_summary_header, render_triple_charts, render_corridor_map, render_admission_advice

st.set_page_config(layout="wide", page_title="Cardiac Service Decision Support")

# --- 1. SIDEBAR: PARAMETERS (Global) ---
with st.sidebar:
    st.title("🏥 Management Console")
    with st.expander("🌍 Waitlist & Risk Profile", expanded=True):
        b_total = st.number_input("Total Starting Backlog", value=60)
        legacy_p = st.slider("Legacy % (Already Waiting 26wk+)", 0, 100, 20)
        target_wk = st.slider("Stabilization Goal (Target Week)", 4, 24, 12)
        st.write("**Patient Clinical Mix %**")
        d1 = st.slider("Cat 1 (Highest)", 0, 100, 10)
        d2 = st.slider("Cat 2", 0, 100, 15)
        d3 = st.slider("Cat 3", 0, 100, 20)
        d4 = st.slider("Cat 4", 0, 100, 30)
        d5 = max(0, 100 - (d1+d2+d3+d4))
        st.caption(f"Cat 5: {d5}%")

    with st.expander("🛠️ BASELINE Scenario", expanded=True):
        c_s = st.slider("Base Surgery Slots/Wk", 1, 10, 3)
        c_b = st.slider("Base Bed Capacity", 1, 12, 7)
        c_buff = st.slider("Base Safety Buffer", 0, 3, 0)

    with st.expander("🚀 PROPOSED Scenario", expanded=True):
        p_s = st.slider("Prop. Surgery Slots/Wk", 1, 10, 5)
        p_b = st.slider("Prop. Bed Capacity", 1, 12, 7)
        p_buff = st.slider("Prop. Safety Buffer", 0, 3, 1)

# --- 2. ENGINE PREPARATION (Now Global for instant update) ---
common = {'total_backlog': b_total, 'dist_legacy': legacy_p, 'weekly_refs': 5,
          'dist_cat1': d1, 'dist_cat2': d2, 'dist_cat3': d3, 'dist_cat4': d4, 'dist_cat5': d5}

params_c = {**common, 'surg_per_week': c_s, 'total_beds': c_b, 'safety_buffer': c_buff}
params_p = {**common, 'surg_per_week': p_s, 'total_beds': p_b, 'safety_buffer': p_buff}

# AI Logic: recalculates instantly on slider move
ai_surg, ai_beds = find_ai_recommendation(params_c, target_wk)
params_ai = {**common, 'surg_per_week': ai_surg, 'total_beds': ai_beds, 'safety_buffer': p_buff}

# --- 3. THE "AUTO-RUN" ENGINE ---
# This runs every time a slider is moved, allowing for instant dashboard feedback.
# We use an empty ward [] for the Dashboard to show 'strategic' trends.
df_c_strat = run_simulation(params_c, [])
df_p_strat = run_simulation(params_p, [])
df_ai_strat = run_simulation(params_ai, [])

# --- 4. MAIN UI TABS ---
tab1, tab2 = st.tabs(["📊 Strategic Dashboard", "🗓️ Weekly Operations Manager"])

with tab1:
    # Header shows the AI recommendation found above
    render_summary_header(ai_surg, ai_beds, p_buff, target_wk, df_ai_strat)
    
    titles = [
        f"BASELINE: {c_s} Slots / {c_b} Beds",
        f"PROPOSED: {p_s} Slots / {p_b} Beds",
        f"AI TARGET: {ai_surg} Slots / {ai_beds} Beds"
    ]
    
    # Dashboards are now instantly responsive
    render_triple_charts(df_c_strat, df_p_strat, df_ai_strat, titles)

with tab2:
    st.subheader("Hospital Live State & Operational Forecast")
    
    if 'ward_data' not in st.session_state:
        st.session_state.ward_data = pd.DataFrame([
            {"Bed": 1, "Occupied": True, "Cat": 1, "DaysRemaining": 14},
            {"Bed": 2, "Occupied": True, "Cat": 2, "DaysRemaining": 7}
        ] + [{"Bed": i+3, "Occupied": False, "Cat": 3, "DaysRemaining": 0} for i in range(10)])

    with st.form("ward_init"):
        st.write("Edit Current Ward Occupancy (Today)")
        edited_ward = st.data_editor(st.session_state.ward_data, num_rows="fixed")
        run_op_btn = st.form_submit_button("Generate Operational Forecast")

    if run_op_btn:
        st.session_state.ward_data = edited_ward
        active_ward = edited_ward[edited_ward['Occupied']].to_dict('records')
        
        # We run the Proposed scenario specifically for the live forecast
        res_op = run_simulation(params_p, active_ward)
        st.session_state.op_results = res_op

    if 'op_results' in st.session_state:
        res = st.session_state.op_results
        view_wk = st.select_slider("Forecast Timeline (Weeks):", options=range(52))
        st.divider()
        render_admission_advice(res.iloc[view_wk])
        render_corridor_map(res.iloc[view_wk]['ward_state'], p_b)