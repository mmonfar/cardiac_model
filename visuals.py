import streamlit as st
import plotly.express as px
import pandas as pd

COLOR_MAP = {
    'Cat 1': '#D32F2F', 'Cat 2': '#F57C00', 'Cat 3': '#FBC02D', 
    'Cat 4': '#1976D2', 'Cat 5': '#388E3C', 'Empty': '#E0E0E0'
}

def render_summary_header(ai_surg, ai_beds, buffer, target_wk, df_prop):
    st.markdown(f"## 🤖 Strategic Analysis: Stabilization by Week {target_wk}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("AI Target Ops/Week", f"{ai_surg}")
    c2.metric("AI Target Beds", f"{ai_beds}")
    c3.metric("Safety Buffer", f"{buffer} Bed", help="Beds reserved for emergency admissions")
    
    total_cancels = int(df_prop['cancellations'].sum())
    c4.metric("Annual 'Bed-Choke' Cancels", total_cancels, delta_color="inverse")

def render_triple_charts(df_c, df_p, df_ai, titles):
    st.divider()
    data = [df_c, df_p, df_ai]
    cols = st.columns(3)
    cats = ['Cat 1', 'Cat 2', 'Cat 3', 'Cat 4', 'Cat 5']
    
    for i, col in enumerate(cols):
        with col:
            st.markdown(f"### {titles[i]}")
            
            # The Chart
            fig = px.area(data[i], x='week', y=cats, color_discrete_map=COLOR_MAP, height=450)
            fig.add_scatter(x=data[i]['week'], y=data[i]['Over_26_Wks'], 
                            name="26wk+ Risk", line=dict(color='white', dash='dot', width=3))
            fig.update_layout(showlegend=(i==2), margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            # IMPACT CARDS (Specific to this scenario)
            cancels = int(data[i]['cancellations'].sum())
            risk_end = data[i].iloc[-1]['Over_26_Wks']
            
            c1, c2 = st.columns(2)
            c1.metric("Annual 'Bed-Choke' Cancels", cancels, delta_color="inverse")
            c2.metric("Year-End 26wk+ Risk", risk_end, delta_color="inverse")

            if risk_end > 0:
                st.error(f"Status: FAILED. {risk_end} legacy cases remain.")
            else:
                st.success("Status: STABILIZED. Legacy cleared.")

def render_admission_advice(week_data):
    st.markdown("### 📋 Weekly Admission Prescription (The Theater List)")
    adms = week_data.get('admissions', {})
    cols = st.columns(5)
    for i, cat in enumerate(['Cat 1', 'Cat 2', 'Cat 3', 'Cat 4', 'Cat 5']):
        count = adms.get(cat, 0)
        cols[i].markdown(f"""
            <div style="background-color:{COLOR_MAP[cat]}; padding:20px; border-radius:10px; text-align:center; color:white; border: 2px solid white; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);">
                <small style="text-transform: uppercase; font-weight: bold;">{cat}</small><br>
                <span style="font-size:32px; font-weight:bold;">{count}</span><br>
                <small>Admissions</small>
            </div>
        """, unsafe_allow_html=True)

def render_corridor_map(ward_state, total_capacity):
    st.subheader(f"🛌 CICU Corridor View ({total_capacity} Bed Capacity)")
    
    # Acuity Alert Logic
    high_acuity = len([p for p in ward_state if p['cat'] <= 2])
    if high_acuity > (total_capacity * 0.6):
        st.error(f"🚨 STAFFING CRISIS: {high_acuity} beds are High Acuity (Cat 1/2). Requires 1:1 Nursing Staffing.")
    
    # Grid Layout for Beds
    mid = (total_capacity + 1) // 2
    for row in [range(mid), range(mid, total_capacity)]:
        cols = st.columns(mid)
        for idx, b_idx in enumerate(row):
            if idx < len(cols):
                with cols[idx]:
                    if b_idx < len(ward_state):
                        p = ward_state[b_idx]
                        color = COLOR_MAP[f"Cat {p['cat']}"]
                        st.markdown(f"""
                            <div style="background-color:{color}; padding:15px; border-radius:10px; color:white; height:140px; text-align:center; border:3px solid white; box-shadow: 3px 3px 10px rgba(0,0,0,0.2);">
                                <small>BED {b_idx+1}</small><br>
                                <b style="font-size:22px;">Cat {p['cat']}</b><br>
                                <hr style="margin:8px 0; border:0; border-top:1px solid rgba(255,255,255,0.3);">
                                <small>Projected Exit:<br><b>{int(p['days_remaining'])} Days</b></small>
                            </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div style="background-color:{COLOR_MAP['Empty']}; padding:15px; border-radius:10px; color:#999; height:140px; text-align:center; border:2px dashed #bbb;">
                                <small>BED {b_idx+1}</small><br><br>
                                <b style="font-size:18px; color:#aaa;">VACANT</b>
                            </div>""", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)