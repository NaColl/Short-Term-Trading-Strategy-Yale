"""
L8 APEX Analyst Terminal — Home Page.
Streamlit application for the analyst-in-the-loop workflow.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Page config
st.set_page_config(
    page_title="APEX Analyst Terminal",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for "Bloomberg meets Blade Runner" aesthetic
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .stMetric {
        background: #1a1c24;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #00ff41;
    }
    .main-header {
        font-family: 'Courier New', Courier, monospace;
        color: #00ff41;
        font-size: 2.5rem;
        text-shadow: 0 0 10px #00ff41;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">APEX // SOVEREIGN TERMINAL v3.0</h1>', unsafe_allow_html=True)

# Sidebar
st.sidebar.title("Navigation")
st.sidebar.markdown("---")
page = st.sidebar.radio("Module", ["Dashboard", "Event Queue", "Portfolio", "Risk Radar", "Execution Logs"])

if page == "Dashboard":
    st.header("Executive Summary")
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total NAV", "$12.4M", "+1.2%")
    with col2:
        st.metric("Gross Exposure", "114%", "-2%")
    with col3:
        st.metric("Daily P&L", "+$42k", "+0.34%")
    with col4:
        st.metric("VaR (95%)", "1.8%", "Safe")

    # Main charts
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Portfolio Performance")
        chart_data = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=30),
            "nav": [10 + i*0.1 for i in range(30)]
        })
        fig = px.line(chart_data, x="date", y="nav", template="plotly_dark", color_discrete_sequence=["#00ff41"])
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("Sector Exposure")
        df_sector = pd.DataFrame({
            "Sector": ["Tech", "Mining", "Energy", "Financials"],
            "Value": [35, 25, 20, 20]
        })
        fig_pie = px.pie(df_sector, values="Value", names="Sector", hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_pie, use_container_width=True)

elif page == "Event Queue":
    st.header("Corporate Event Queue")
    st.info("Pending Analyst Review")
    
    # Dummy data for demonstration
    events = pd.DataFrame([
        {"Ticker": "BHP", "Event": "Mine Expansion", "Confidence": 0.92, "Signal": "Strong Buy"},
        {"Ticker": "XOM", "Event": "Acquisition", "Confidence": 0.85, "Signal": "Medium Buy"},
        {"Ticker": "PLTR", "Event": "Contract Renewal", "Confidence": 0.78, "Signal": "Hold"},
    ])
    st.table(events)
    
    selected_ticker = st.selectbox("Select Event for Inspection", events["Ticker"].tolist())
    if st.button("Open Thesis Inspector"):
        st.write(f"Displaying deep-dive for {selected_ticker}...")
        # Link to details page or modal logic here

# Footer
st.markdown("---")
st.caption(f"APEX System // Connected to IBKR // Environment: {st.secrets.get('APEX_ENV', 'paper')}")
