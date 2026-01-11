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

# --- 1. CACHING ENGINE (Speed Optimization) ---
@st.cache_data
def get_cached_ai(params, target):
    return find_ai_recommendation(params, target)

@st.cache_data
def get_cached_sim(params, ward, seed=42):
    return run_simulation(params, ward, seed=seed)

# --- 2. SIDEBAR: PARAMETERS ---
with st.sidebar:
    st.title("🏥 Management Console")
    
    # We wrap inputs in a form to prevent "Double-Toggle" lag
    with st.form("main_input_form"):
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
            st.info(f"🟢 **Cat 5 (Stable/Routine): {d5}%**")
            if (d1+d2+d3+d4) > 100:
                st.error("Total mix exceeds 100%! Please adjust sliders.")

        with st.expander("⏱️ Category LOS (Avg Days)", expanded=False):
            l1 = st.number_input("Cat 1 Stay", value=22)
            l2 = st.number_input("Cat 2 Stay", value=11)
            l3 = st.number_input("Cat 3 Stay", value=5)
            l4 = st.number_input("Cat 4 Stay", value=2)
            l5 = st.number_input("Cat 5 Stay", value=2)

        with st.expander("📉 Deterioration Rates", expanded=False):
            d54 = st.slider("Cat 5 → 4", 0.0, 0.1, 0.02)
            d43 = st.slider("Cat 4 → 3", 0.0, 0.1, 0.04)
            d32 = st.slider("Cat 3 → 2", 0.0, 0.2, 0.07)
            d21 = st.slider("Cat 2 → 1", 0.0, 0.3, 0.12)

        with st.expander("🔬 Model Variance Limits", expanded=False):
            los_variance = st.slider("LOS Uncertainty Range", 0.5, 2.0, 1.0)

        with st.expander("🛠️ BASELINE Scenario", expanded=True):
            c_s = st.slider("Base Surgery Slots/Wk", 1, 10, 3)
            c_b = st.slider("Base Bed Capacity", 1, 15, 7)
            c_buff = st.slider("Base Safety Buffer", 0, 3, 0)

        with st.expander("🚀 PROPOSED Scenario", expanded=True):
            p_s = st.slider("Prop. Surgery Slots/Wk", 1, 10, 5)
            p_b = st.slider("Prop. Bed Capacity", 1, 15, 8)
            p_buff = st.slider("Prop. Safety Buffer", 0, 3, 0)
        
        submit_btn = st.form_submit_button("📊 RUN ANALYSIS", use_container_width=True)

# --- 3. ENGINE PREPARATION & EXECUTION ---
# Initialize session state so the app doesn't look empty on load
if 'init' not in st.session_state:
    st.session_state.init = True

if submit_btn or st.session_state.init:
    common = {
        'total_backlog': b_total, 'dist_legacy': legacy_p, 'weekly_refs': weekly_refs,
        'dist_cat1': d1, 'dist_cat2': d2, 'dist_cat3': d3, 'dist_cat4': d4, 'dist_cat5': d5,
        'det_5to4': d54, 'det_4to3': d43, 'det_3to2': d32, 'det_2to1': d21,
        'los_scale': los_variance,
        'los_cat1': l1, 'los_cat2': l2, 'los_cat3': l3, 'los_cat4': l4, 'los_cat5': l5,
        'surg_per_week': c_s, 'total_beds': c_b, 'safety_buffer': p_buff 
    }

    with st.spinner("Analyzing Clinical Pathways..."):
        # 1. Get AI Recommendation (CACHED)
        ai_surg, ai_beds = get_cached_ai(common, target_wk)
        
        # 2. Define parameters
        params_c = {**common, 'surg_per_week': c_s, 'total_beds': c_b, 'safety_buffer': c_buff}
        params_p = {**common, 'surg_per_week': p_s, 'total_beds': p_b, 'safety_buffer': p_buff}
        params_ai = {**common, 'surg_per_week': ai_surg, 'total_beds': ai_beds, 'safety_buffer': p_buff}

        # 3. Run simulations (CACHED)
        df_c_strat = get_cached_sim(params_c, [])
        df_p_strat = get_cached_sim(params_p, [])
        df_ai_strat = get_cached_sim(params_ai, [])

        common['det_events_mean'] = df_ai_strat['det_events'].mean()

    # --- 4. MAIN UI ---
    st.title("Cardiac Service Strategy: Executive Decision Suite")
    st.success(f"**AI Recommendation:** To achieve stability by Week {target_wk}, allocate **{ai_surg} Slots** and **{ai_beds} Beds**.")

    with st.expander("💡 Strategic Rationale", expanded=False):
        time_rationale = "immediate stabilization" if target_wk < 20 else "long-term sustainable flow"
        st.write(f"The AI determined that **{ai_beds} beds** are required for **{time_rationale}**.")
        c1, c2, c3 = st.columns(3)
        c1.markdown("**1. Clinical Safety** \nZero-tolerance for patients exceeding the 26-week threshold.")
        c2.markdown("**2. Financial Resilience** \nPrioritizes preventing theater cancellations (Est. AED 15,000 cost/event).")
        c3.markdown("**3. Patient Experience** \nMaintains a 'Safety Buffer' to protect facility reputation and honor surgical dates.")
        st.info(f"**Operational Insight:** The AI prioritizes 'Safety Buffer' over occupancy because the cost of an idle bed is 10x lower than the cost of a cancelled theater slot.")

    tab1, tab2, tab3 = st.tabs(["📊 Strategy Comparison", "🛌 Operations & Floor Map", "🔬 Model Transparency"])

    with tab1:
        render_executive_kpis(df_c_strat, df_p_strat, df_ai_strat)
        titles = [f"BASELINE: {c_s}S / {c_b}B", f"PROPOSED: {p_s}S / {p_b}B", f"AI TARGET: {ai_surg}S / {ai_beds}B"]
        render_triple_charts(df_c_strat, df_p_strat, df_ai_strat, titles, key="strategy_comparison")
        
        if st.button("🚀 Run 52-Week Stress Test"):
            st.markdown("### Stress Test: 20 Parallel Simulation Runs")
            runs = [run_simulation(params_ai, [], seed=i) for i in range(20)]
            render_monte_carlo_cloud(pd.concat(runs))

    with tab2:
        st.subheader("Operational Forecast & Live Ward State")

        # 1. Initialize data if not present
        if 'ward_data' not in st.session_state:
            st.session_state.ward_data = pd.DataFrame([
                {"Bed": 1, "Occupied": True, "cat": 1, "days_remaining": 14},
                {"Bed": 2, "Occupied": True, "cat": 2, "days_remaining": 7},
                {"Bed": 3, "Occupied": True, "cat": 3, "days_remaining": 3}
            ] + [{"Bed": i+4, "Occupied": False, "cat": 3, "days_remaining": 0} for i in range(12)])


        # 2. The Form for input
        with st.form("ward_init"):
            st.write("Current Ward Status (Input live occupancy for forecasting)")
            edited_ward = st.data_editor(st.session_state.ward_data, num_rows="fixed")
            run_op_btn = st.form_submit_button("Generate Operational Forecast")

        if run_op_btn:
            # 1. SAVE: Capture the live ward state
            st.session_state.ward_data = edited_ward
            # 2. FILTER: Only send the patients actually in beds
            active_ward = edited_ward[edited_ward['Occupied']].to_dict('records')
            # 3. CONSTRAIN: Run the model using your PROPOSED params and LIVE ward
            # This is where the 'Third Graph' data is created
            st.session_state.op_results = run_simulation(params_p, active_ward, seed=42)
            # 4. RESET: Ensure the slider starts at Week 0 for the new forecast
            st.session_state.op_week_slider = 0
            # Force a rerun to ensure the results are visible to the code below
            st.rerun()

        # --- 3. The Display Logic (OUTSIDE the form) ---
        if 'op_results' in st.session_state:
            res = st.session_state.op_results
    
            # 1. Timeline Control
            view_wk = st.select_slider("Forecast Timeline (Week):", options=range(len(res)), key="op_week_slider")
    
            # 2. Extract specific week (This is the 'Who' is in the beds)
            # We take the 'ward_state' list we created in the engine
            current_ward_list = res.iloc[view_wk]['ward_state'] 
    
            # 3. Create a snapshot dict for the visualizer
            current_snapshot = {'ward_state': current_ward_list}
    
            # 4. Render (This is the 'Where' - total beds)
            # This solves the TypeError by providing BOTH arguments
            render_ward_ops(current_snapshot, params_p['total_beds'])
    
            # 5. The "Third Graph" - Prove the impact of your manual table
            st.divider()
            st.subheader("Operational Impact on Throughput")
            titles = [
                f"BASELINE: {c_s}S / {c_b}B", 
                f"PROPOSED: {p_s}S / {p_b}B", 
                f"AI TARGET: {ai_surg}S / {ai_beds}B"
            ]
            render_triple_charts(res, res, res, titles, key="operational_forecast")

    with tab3:
        st.subheader("🤖 Intelligence Engine: The 'Friction' Model")
        col1, col2, col3 = st.columns(3)
        col1.metric("Clinical Breach Penalty", "High Risk", "Weight: 5,000")
        col2.metric("Cancellation Friction", "AED 15,000", "Weight: 100")
        col3.metric("Idle Capacity Cost", "AED 1,500", "Weight: 20")
        st.markdown("> **Decision Logic:** The AI chooses to have a spare bed ready rather than risk a cancellation, as the financial and reputational friction of a cancelled slot is 10x higher.")
        st.divider()
        render_variance_analysis(common)