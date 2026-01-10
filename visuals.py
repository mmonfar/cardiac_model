import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Executive Color Palette
COLOR_MAP = {
    'Cat 1': '#D32F2F', 'Cat 2': '#F57C00', 'Cat 3': '#FBC02D', 
    'Cat 4': '#1976D2', 'Cat 5': '#388E3C', 'Empty': '#E0E0E0'
}

def render_executive_kpis(df_base, df_prop, df_ai):
    """High-level metric comparison for the C-Suite."""
    st.markdown("### 📊 Strategic KPI Comparison")
    c1, c2, c3 = st.columns(3)
    
    scenarios = [
        ("Baseline", df_base),
        ("Proposed", df_prop),
        ("AI Target", df_ai)
    ]
    
    for i, (name, df) in enumerate(scenarios):
        total_cancels = int(df['cancellations'].sum())
        risk_end = int(df.iloc[-1]['Over_26_Wks'])
        status = "✅ STABLE" if risk_end == 0 else "⚠️ RISK"
        
        with [c1, c2, c3][i]:
            st.metric(f"{name} Stability", status)
            st.metric("Annual Cancellations", total_cancels)
            st.metric("Year-End Legacy Risk", f"{risk_end} Patients")

def render_triple_charts(df_c, df_p, df_ai, titles):
    """The core side-by-side strategy view."""
    st.divider()
    data = [df_c, df_p, df_ai]
    cols = st.columns(3)
    cats = ['Cat 1', 'Cat 2', 'Cat 3', 'Cat 4', 'Cat 5']
    
    for i, col in enumerate(cols):
        with col:
            st.markdown(f"#### {titles[i]}")
            fig = px.area(data[i], x='week', y=cats, color_discrete_map=COLOR_MAP, height=400)
            fig.add_scatter(x=data[i]['week'], y=data[i]['Over_26_Wks'], 
                            name="Legacy Risk (>26w)", line=dict(color='white', dash='dot', width=2))
            fig.update_layout(showlegend=(i==2), margin=dict(l=10, r=10, t=30, b=10), template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

def render_ward_ops(week_data, total_capacity):
    """The 'Ground Truth' floor map and weekly prescription."""
    st.markdown("---")
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("📋 Weekly Prescription")
        adms = week_data.get('admissions', {})
        for cat in ['Cat 1', 'Cat 2', 'Cat 3', 'Cat 4', 'Cat 5']:
            count = adms.get(cat, 0)
            st.markdown(f"""
                <div style="background-color:{COLOR_MAP[cat]}; padding:10px; border-radius:5px; color:white; margin-bottom:5px;">
                <b>{cat}:</b> {count} Admissions scheduled
                </div>""", unsafe_allow_html=True)
                
    with c2:
        # We assume 10 is the physical baseline of the unit
        PHYSICAL_BEDS = 10
        display_beds = max(PHYSICAL_BEDS, total_capacity)
        
        st.subheader(f"🛌 Floor Map View ({total_capacity} Active Beds)")
        ward_state = week_data.get('ward_state', [])
        
        # High Acuity Warning
        high_acuity = len([p for p in ward_state if p.get('cat', 5) <= 2])
        if high_acuity > (total_capacity * 0.6):
            st.warning(f"🚨 **High Acuity Alert:** {high_acuity} beds are Cat 1/2. Staffing ratio 1:1 required.")
            
        cols = st.columns(5) # 5 columns looks cleaner for 10+ beds
        for i in range(display_beds):
            with cols[i % 5]:
                # CASE 1: Bed is occupied by a patient
                if i < len(ward_state):
                    p = ward_state[i]
                    color = COLOR_MAP.get(f"Cat {p['cat']}", '#E0E0E0')
                    st.markdown(f"""
                        <div style="background-color:{color}; padding:10px; border-radius:5px; color:white; text-align:center; border:2px solid white; height:100px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                        <small>BED {i+1}</small><br><b>C{p['cat']}</b><br><small>{int(p['days_remaining'])}d left</small>
                        </div>""", unsafe_allow_html=True)
                
                # CASE 2: Bed is "Active" (Open) but empty
                elif i < total_capacity:
                    st.markdown(f"""
                        <div style="background-color:#eee; padding:10px; border-radius:5px; color:#aaa; text-align:center; border:1px dashed #ccc; height:100px;">
                        <small>BED {i+1}</small><br><br><b style="color:#388E3C;">OPEN</b>
                        </div>""", unsafe_allow_html=True)
                
                # CASE 3: Bed exists physically but is "Closed" (Unfunded/Unstaffed)
                elif i < PHYSICAL_BEDS:
                    st.markdown(f"""
                        <div style="background-color:#f9f9f9; padding:10px; border-radius:5px; color:#ccc; text-align:center; border:1px solid #eee; height:100px; filter: grayscale(100%);">
                        <small>BED {i+1}</small><br><br><b>CLOSED</b>
                        </div>""", unsafe_allow_html=True)
                
                # CASE 4: Extra beds needed beyond physical footprint
                else:
                    st.markdown(f"""
                        <div style="background-color:#FFF3E0; padding:10px; border-radius:5px; color:#E65100; text-align:center; border:2px solid #FFB74D; height:100px;">
                        <small>BED {i+1}</small><br><br><b>EXTRA</b>
                        </div>""", unsafe_allow_html=True)

def render_variance_analysis(params):
    """Transparency Tab: Comprehensive view of clinical and operational distributions."""
    st.header("🔬 Model Transparency & Clinical Assumptions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("A) Referral Volatility (Poisson)")
        data = np.random.poisson(params['weekly_refs'], 1000)
        fig = px.histogram(data, nbins=15, color_discrete_sequence=['#1E3A8A'])
        fig.update_layout(title="Variation in Weekly Referrals", xaxis_title="New Patients", yaxis_title="Frequency")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Simulates 'Lumpy' demand—planning for the average, but prepared for surges.")

    with col2:
        st.subheader("B) LOS Confidence Map")
        st.markdown("Typical Stay vs. **Outlier Bed-Blocking Risk**.")
        
        all_stays = []
        
        for i in range(1, 6):
            m = params.get(f'los_cat{i}', 5)

            # Standard Patient Distribution
            stays = np.random.gamma(shape=m, scale=params.get('los_scale', 1.0), size=120)

            for s in stays:
                # We label Cat 1/2 as 'High Acuity' to emphasize bed-blocking risk
                acuity_type = "High Acuity" if i <= 2 else "Standard"
                all_stays.append({"Category": f"Cat {i}", "Days": s, "Type": acuity_type})
            
                
        df_stays = pd.DataFrame(all_stays)
        fig = px.box(df_stays, x="Category", y="Days", color="Category", 
                     color_discrete_map=COLOR_MAP, points=False,
                     hover_data=["Type"])

        fig.update_layout(
            showlegend=False, 
            height=350, 
            margin=dict(t=10, b=10),
            yaxis_title="Bed Days (LOS)"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Boxes show the 25th-75th percentile; whiskers capture the clinical outliers.")

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("C) Clinical Risk Matrix (Weekly Transition %)")
        
        # 1. Natural Clinical Decline (Applies to the 100 - x % cohort)
        det_data = {
            "Step": ["Cat 5→4", "Cat 4→3", "Cat 3→2", "Cat 2→1"],
            "Weekly Probability": [params['det_5to4'], params['det_4to3'], params['det_3to2'], params['det_2to1']]
        }
        df_disp = pd.DataFrame(det_data)
        df_disp["Weekly Probability"] = df_disp["Weekly Probability"].map('{:.1%}'.format)
        
        st.table(df_disp)
        
        # 2. The Legacy Diagnosis (The x % cohort)
        legacy_perc = params.get('dist_legacy', 25)
        st.info(f"""
        **Cohort-Specific Logic:**
        * **Standard Cohort ({100 - legacy_perc}%):** Follow the transition probabilities in the table above.
        * **Legacy Diagnosis Cohort ({legacy_perc}%):** Automatic **Cat 1 Escalation** at Week 26 (Hard Breach).
        """)

    with col4:
        st.subheader("D) Deterioration Clusters")
        # Logic for showing how often multiple patients get sicker at once
        avg_det = params.get('det_events_mean', 4.2) 
        data = np.random.poisson(avg_det, 1000)
        
        fig = px.histogram(data, nbins=15, color_discrete_sequence=['#D32F2F'])
        fig.update_layout(
            title=f"Frequency of 'Crisis Weeks' (Avg: {avg_det:.1f}/wk)",
            xaxis_title="Patients Deteriorating in One Week",
            yaxis_title="Frequency (Simulated Weeks)",
            bargap=0.1, height=350
        )
        st.plotly_chart(fig, use_container_width=True)
        st.info("""
        **Executive Insight: The 'Volatility' Buffer**
        * **The Histogram:** Shows how many weeks (out of 1,000) saw a specific number of clinical 'crashes.'
        * **The 'Red Zone':** High-value bars on the right represent **Crisis Weeks**.
        * **Impact:** In these weeks, multiple patients jump to higher clinical priority (Cat 1/2). This forces the system to 'queue-jump' these patients into surgery, causing cancellations for lower-priority cases and requiring a pre-planned bed buffer.
        """)

def render_monte_carlo_cloud(df_mc):
    """Stress test visualization with uncertainty bands."""
    st.header("🚀 Stress Test: 52-Week Projection")
    stats = df_mc.groupby('week')['Over_26_Wks'].agg(['mean', 'min', 'max']).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pd.concat([stats['week'], stats['week'][::-1]]),
        y=pd.concat([stats['max'], stats['min'][::-1]]),
        fill='toself', fillcolor='rgba(30, 58, 138, 0.1)',
        line=dict(color='rgba(255,255,255,0)'), name='Uncertainty Range'
    ))
    fig.add_trace(go.Scatter(x=stats['week'], y=stats['mean'], 
                             line=dict(color='#1E3A8A', width=3), name='Expected Outcome'))
    
    fig.update_layout(title="Legacy Risk Stabilization Horizon", 
                      xaxis_title="Weeks into Future", yaxis_title="Patients in Legacy Breach",
                      template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)