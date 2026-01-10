import streamlit as st
import pandas as pd
import numpy as np
from engine import run_simulation, find_ai_recommendation
from visuals import (
    render_executive_kpis, 
    render_triple_charts, 
    render_ward_ops, 
    render_variance_analysis,
    render_monte_carlo_cloud
)

st.set_page_config(layout="wide", page_title="Cardiac Service Decision Support")

# --- 1. SIDEBAR: PARAMETERS ---
with st.sidebar:
    st.title("🏥 Management Console")
    
    with st.expander("🌍 Waitlist & Referrals", expanded=True):
        b_total = st.number_input("Total Starting Backlog", value=60)
        legacy_p = st.slider("Legacy % (Cohort A: 26wk Clock)", 0, 100, 10)
        target_wk = st.slider("Stabilization Goal (Target Week)", 4, 52, 26)
        weekly_refs = st.slider("Avg. New Referrals / Week", 1, 15, 6)
        
        st.write("**Referral Clinical Mix %**")
        d1 = st.slider("Cat 1 (Highest)", 0, 100, 10)
        d2 = st.slider("Cat 2", 0, 100, 15)
        d3 = st.slider("Cat 3", 0, 100, 20)
        d4 = st.slider("Cat 4", 0, 100, 30)
        d5 = max(0, 100 - (d1+d2+d3+d4))
        st.caption(f"Cat 5: {d5}%")

    with st.expander("⏱️ Category LOS (Avg Days)", expanded=False):
        st.info("Clinical LOS by category. Outliers are handled by Variance slider below.")
        l1 = st.number_input("Cat 1 Stay", value=22)
        l2 = st.number_input("Cat 2 Stay", value=11)
        l3 = st.number_input("Cat 3 Stay", value=5)
        l4 = st.number_input("Cat 4 Stay", value=2)
        l5 = st.number_input("Cat 5 Stay", value=2)

    with st.expander("📉 Deterioration Rates (Weekly %)", expanded=False):
        st.info("Standard Cohort: Stochastic clinical decline. Legacy Cohort: Time-based escalation.")
        d54 = st.slider("Cat 5 → 4", 0.0, 0.1, 0.02)
        d43 = st.slider("Cat 4 → 3", 0.0, 0.1, 0.04)
        d32 = st.slider("Cat 3 → 2", 0.0, 0.2, 0.07)
        d21 = st.slider("Cat 2 → 1", 0.0, 0.3, 0.12)

    with st.expander("🔬 Model Variance Limits", expanded=False):
        st.write("**Statistical Tail (Complexity)**")
        # Removed legacy_penalty slider as it is now redundant
        los_variance = st.slider("LOS Uncertainty Range", 0.5, 2.0, 1.0)
        st.caption("Higher range simulates more frequent complex outlier stays.")

    with st.expander("🛠️ BASELINE Scenario", expanded=True):
        c_s = st.slider("Base Surgery Slots/Wk", 1, 10, 3)
        c_b = st.slider("Base Bed Capacity", 1, 15, 7)
        c_buff = st.slider("Base Safety Buffer", 0, 3, 0)

    with st.expander("🚀 PROPOSED Scenario", expanded=True):
        p_s = st.slider("Prop. Surgery Slots/Wk", 1, 10, 5)
        p_b = st.slider("Prop. Bed Capacity", 1, 15, 8)
        p_buff = st.slider("Prop. Safety Buffer", 0, 3, 0)

# --- 2. ENGINE PREPARATION ---
common = {
    'total_backlog': b_total, 
    'dist_legacy': legacy_p, 
    'weekly_refs': weekly_refs,
    'dist_cat1': d1, 'dist_cat2': d2, 'dist_cat3': d3, 'dist_cat4': d4, 'dist_cat5': d5,
    'det_5to4': d54, 'det_4to3': d43, 'det_3to2': d32, 'det_2to1': d21,
    'los_scale': los_variance,
    'los_cat1': l1, 'los_cat2': l2, 'los_cat3': l3, 'los_cat4': l4, 'los_cat5': l5,
    'surg_per_week': c_s, 
    'total_beds': c_b,
    'safety_buffer': p_buff 
}

# --- 3. AUTO-RUN STRATEGIC TRENDS ---
with st.spinner("Analyzing Clinical Pathways..."):
    # 1. Get AI Recommendation
    ai_surg, ai_beds = find_ai_recommendation(common, target_wk)
    
    # 2. Define parameters for simulations
    params_c = {**common, 'surg_per_week': c_s, 'total_beds': c_b, 'safety_buffer': c_buff}
    params_p = {**common, 'surg_per_week': p_s, 'total_beds': p_b, 'safety_buffer': p_buff}
    params_ai = {**common, 'surg_per_week': ai_surg, 'total_beds': ai_beds, 'safety_buffer': p_buff}

    # 3. Run strategic simulations
    df_c_strat = run_simulation(params_c, [], seed=42)
    df_p_strat = run_simulation(params_p, [], seed=42)
    df_ai_strat = run_simulation(params_ai, [], seed=42)

    # 4. Update data for transparency tab
    common['det_events_mean'] = df_ai_strat['det_events'].mean()

# --- 4. MAIN UI ---
st.title("Cardiac Service Strategy: Executive Decision Suite")
st.success(f"**AI Recommendation:** To achieve stability by Week {target_wk}, allocate **{ai_surg} Slots** and **{ai_beds} Beds**.")

tab1, tab2, tab3 = st.tabs(["📊 Strategy Comparison", "🛌 Operations & Floor Map", "🔬 Model Transparency"])

with tab1:
    render_executive_kpis(df_c_strat, df_p_strat, df_ai_strat)
    
    titles = [
        f"BASELINE: {c_s}S / {c_b}B",
        f"PROPOSED: {p_s}S / {p_b}B",
        f"AI TARGET: {ai_surg}S / {ai_beds}B"
    ]
    render_triple_charts(df_c_strat, df_p_strat, df_ai_strat, titles)
    
    if st.button("🚀 Run 52-Week Stress Test"):
        st.markdown("### Stress Test: 20 Parallel Simulation Runs")
        runs = [run_simulation(params_ai, [], seed=i) for i in range(20)]
        df_mc = pd.concat(runs)
        render_monte_carlo_cloud(df_mc)

with tab2:
    st.subheader("Operational Forecast & Live Ward State")
    
    # Static ward snapshot for initialization
    if 'ward_data' not in st.session_state:
        st.session_state.ward_data = pd.DataFrame([
            {"Bed": 1, "Occupied": True, "Cat": 1, "DaysRemaining": 14},
            {"Bed": 2, "Occupied": True, "Cat": 2, "DaysRemaining": 7},
            {"Bed": 3, "Occupied": True, "Cat": 3, "DaysRemaining": 3}
        ] + [{"Bed": i+4, "Occupied": False, "Cat": 3, "DaysRemaining": 0} for i in range(12)])

    with st.form("ward_init"):
        st.write("Current Ward Status (Input current bed occupancy for live forecasting)")
        edited_ward = st.data_editor(st.session_state.ward_data, num_rows="fixed")
        run_op_btn = st.form_submit_button("Generate Operational Forecast")

    if run_op_btn:
        st.session_state.ward_data = edited_ward
        active_ward = edited_ward[edited_ward['Occupied']].to_dict('records')
        # Use Proposed params for the operational drill-down
        st.session_state.op_results = run_simulation(params_p, active_ward, seed=42)

    if 'op_results' in st.session_state:
        res = st.session_state.op_results
        view_wk = st.select_slider("Forecast Timeline (Week):", options=range(52))
        st.divider()
        render_ward_ops(res.iloc[view_wk], p_b)

with tab3:
    render_variance_analysis(common)