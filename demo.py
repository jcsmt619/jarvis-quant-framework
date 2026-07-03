"""
demo.py
=======
Component gallery for the shared trading-dashboard design system.

Run:
    streamlit run demo.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from design_system import *

st.set_page_config(page_title="Design System - Demo", layout="wide", page_icon="+")
apply_theme()

# --------------------------------------------------------------------------
st.markdown("## Trading Dashboard - Design System")
st.markdown(
    f'<span style="color:{TEXT_SECONDARY};font-family:{FONT_SANS};">'
    f'A shared dark-terminal aesthetic for all 8 dashboards.</span>',
    unsafe_allow_html=True,
)

# --- Metric cards (native st.metric + custom metric_card) -----------------
st.markdown(section_header("Metrics"), unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Portfolio Equity", "$128,450", "+2.4%")
c2.metric("Daily P&L", "+$3,021", "+2.4%")
c3.metric("Sharpe (60d)", "1.82", "-0.11")
c4.metric("Max Drawdown", "-8.4%")

st.write("")
d1, d2, d3, d4 = st.columns(4)
d1.markdown(metric_card("Win Rate", "58.3%", ACCENT_GREEN), unsafe_allow_html=True)
d2.markdown(metric_card("Gross Exposure", "142%", ACCENT_CYAN), unsafe_allow_html=True)
d3.markdown(metric_card("Open Risk", "-$1,240", ACCENT_RED), unsafe_allow_html=True)
d4.markdown(metric_card("Leverage", "2.1x", ACCENT_AMBER), unsafe_allow_html=True)

# --- Regime badges --------------------------------------------------------
st.markdown(section_header("Regime Badges"), unsafe_allow_html=True)
badges = "&nbsp;&nbsp;".join([
    regime_badge("Bull", 0.82),
    regime_badge("Low Vol", 0.74),
    regime_badge("Neutral", 0.55),
    regime_badge("Medium Vol"),
    regime_badge("Bear", 0.91),
    regime_badge("High Vol", 0.88),
    regime_badge("Uncertain", 0.40),
])
st.markdown(badges, unsafe_allow_html=True)

# --- Status dots ----------------------------------------------------------
st.markdown(section_header("Connection Status"), unsafe_allow_html=True)
dots = (
    f'{status_dot("connected")} <span style="color:{TEXT_SECONDARY}">Broker feed</span>'
    f'&nbsp;&nbsp;&nbsp;{status_dot("warning")} <span style="color:{TEXT_SECONDARY}">Data latency</span>'
    f'&nbsp;&nbsp;&nbsp;{status_dot("error")} <span style="color:{TEXT_SECONDARY}">Backup node</span>'
)
st.markdown(f'<div style="font-family:{FONT_SANS};font-size:0.9rem;">{dots}</div>',
            unsafe_allow_html=True)

# --- Plotly chart ---------------------------------------------------------
st.markdown(section_header("Equity Curve"), unsafe_allow_html=True)

rng = np.random.default_rng(7)
idx = pd.date_range("2024-01-01", periods=180, freq="D")
equity = 100000 * np.cumprod(1 + rng.normal(0.0008, 0.012, 180))
benchmark = 100000 * np.cumprod(1 + rng.normal(0.0004, 0.010, 180))

fig = go.Figure()
fig.add_trace(go.Scatter(x=idx, y=equity, name="Strategy", line=dict(color=ACCENT_CYAN, width=2)))
fig.add_trace(go.Scatter(x=idx, y=benchmark, name="Benchmark", line=dict(color=TEXT_MUTED, width=1.5, dash="dot")))
fig.update_layout(**get_plotly_layout(), height=340)
st.plotly_chart(fig, width="stretch")

# --- Styled dataframe -----------------------------------------------------
st.markdown(section_header("Open Positions"), unsafe_allow_html=True)

positions = pd.DataFrame({
    "Symbol": ["SPY", "QQQ", "SOXL", "TLT", "BTC-USD"],
    "Side": ["LONG", "LONG", "LONG", "SHORT", "LONG"],
    "Qty": [120, 85, 300, 60, 2],
    "Entry": [512.40, 438.10, 41.85, 92.30, 61250.0],
    "Last": [518.90, 441.20, 39.60, 91.10, 63400.0],
    "P&L %": [1.27, 0.71, -5.38, 1.30, 3.51],
})
st.dataframe(style_dataframe(positions), width="stretch", hide_index=True)

# --- pnl_color example ----------------------------------------------------
st.markdown(section_header("P&L Colour Helper"), unsafe_allow_html=True)
pnls = [+3021.0, -1240.0, +512.0, -88.0]
row = "&nbsp;&nbsp;&nbsp;".join(
    f'<span style="font-family:{FONT_MONO};font-size:1.1rem;color:{pnl_color(v)};">'
    f'{"+" if v >= 0 else ""}{v:,.0f}</span>'
    for v in pnls
)
st.markdown(row, unsafe_allow_html=True)
