"""
pairs_scanner.py
================
Statistical Arbitrage (Pairs Trading) Co-integration Scanner — Streamlit.

OLS hedge ratio -> spread -> ADF co-integration test -> rolling 21d z-score
with +/-2.0 trade bands, on the shared dark-terminal design system.

HONEST FRAMING (built into the UI):
  * The ADF test here is IN-SAMPLE over the chosen lookback. Scanning many
    pairs until one shows p<0.05 is multiple comparisons — at p=0.05, 1 in 20
    random pairs "passes" by luck. Treat this as a research screen, not a
    trade trigger.
  * Co-integration BREAKS (V/MA style relationships drift). The rubber band
    can snap instead of snapping back.
  * No borrow costs / margin / execution frictions are modeled here.

Run:  streamlit run pairs_scanner.py
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import statsmodels.api as sm
import streamlit as st
import yfinance as yf
from statsmodels.tsa.stattools import adfuller

from design_system import *

st.set_page_config(page_title="Pairs Scanner", layout="wide", page_icon="~")
apply_theme()

Z_WINDOW = 21
Z_BAND = 2.0


# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_pair(ticker_a: str, ticker_b: str, years: int) -> pd.DataFrame:
    start = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()
    raw = yf.download([ticker_a, ticker_b], start=start, auto_adjust=True, progress=False)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    return close.dropna()


def analyze(close: pd.DataFrame, a: str, b: str) -> dict:
    ya, yb = close[a], close[b]
    X = sm.add_constant(yb.to_numpy())
    model = sm.OLS(ya.to_numpy(), X).fit()
    hedge_ratio = float(model.params[1])
    spread = ya - hedge_ratio * yb
    adf_stat, p_value, *_ = adfuller(spread.to_numpy())
    mu = spread.rolling(Z_WINDOW).mean()
    sd = spread.rolling(Z_WINDOW).std()
    z = (spread - mu) / sd.replace(0.0, np.nan)
    corr = float(ya.pct_change().corr(yb.pct_change()))
    return {"hedge_ratio": hedge_ratio, "spread": spread, "z": z.dropna(),
            "p_value": float(p_value), "adf_stat": float(adf_stat), "corr": corr}


def zscore_chart(z: pd.Series, a: str, b: str) -> go.Figure:
    fig = go.Figure()
    # Base line in segments colored by band state.
    state = np.where(z > Z_BAND, "short", np.where(z < -Z_BAND, "long", "neutral"))
    colors = {"neutral": TEXT_SECONDARY, "short": ACCENT_RED, "long": ACCENT_GREEN}
    # plot contiguous runs so colors switch exactly at band crossings
    start = 0
    for i in range(1, len(z) + 1):
        if i == len(z) or state[i] != state[start]:
            seg = z.iloc[max(0, start - 1): i]      # overlap 1 pt for continuity
            fig.add_trace(go.Scatter(
                x=seg.index, y=seg.values, mode="lines", showlegend=False,
                line=dict(color=colors[state[start]], width=1.6),
                hovertemplate="%{x|%Y-%m-%d}<br>z=%{y:.2f}<extra></extra>"))
            start = i
    for lvl, col in ((Z_BAND, ACCENT_RED), (-Z_BAND, ACCENT_GREEN), (0.0, GRID_LINE)):
        fig.add_hline(y=lvl, line_dash="dash", line_color=col, line_width=1)
    fig.add_annotation(x=z.index[-1], y=Z_BAND, text=f"SHORT {a} / LONG {b}",
                       showarrow=False, yshift=12, font=dict(color=ACCENT_RED, size=11))
    fig.add_annotation(x=z.index[-1], y=-Z_BAND, text=f"LONG {a} / SHORT {b}",
                       showarrow=False, yshift=-12, font=dict(color=ACCENT_GREEN, size=11))
    fig.update_layout(**get_plotly_layout(), height=420, showlegend=False)
    fig.update_yaxes(title_text=f"Spread z-score ({Z_WINDOW}d)")
    return fig


# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(section_header("Pair Configuration"), unsafe_allow_html=True)
    ticker_a = st.text_input("Ticker A", value="V").strip().upper()
    ticker_b = st.text_input("Ticker B", value="MA").strip().upper()
    years = st.slider("Lookback (years)", 1, 10, 2)
    st.markdown(
        f'<div style="font-family:{FONT_SANS};font-size:0.7rem;color:{TEXT_MUTED};'
        f'line-height:1.5;">ADF is in-sample over this lookback. Screen, don\'t trade it blind.</div>',
        unsafe_allow_html=True)

st.markdown(
    f'<div style="font-family:{FONT_MONO};font-size:2.2rem;font-weight:700;'
    f'color:{TEXT_PRIMARY};">{ticker_a} / {ticker_b}'
    f'<span style="font-size:0.9rem;color:{TEXT_MUTED};font-family:{FONT_SANS};'
    f'letter-spacing:2px;"> &nbsp;PAIRS CO-INTEGRATION SCANNER</span></div>',
    unsafe_allow_html=True)

try:
    close = load_pair(ticker_a, ticker_b, years)
except Exception as exc:
    st.error(f"Data download failed: {exc}")
    st.stop()
if close.empty or len(close) < Z_WINDOW * 3 or ticker_a not in close or ticker_b not in close:
    st.error("Not enough overlapping data for this pair/lookback.")
    st.stop()

res = analyze(close, ticker_a, ticker_b)

# ---- verdict row ----
c1, c2, c3, c4 = st.columns([1.6, 1, 1, 1])
tradeable = res["p_value"] < 0.05
verdict_color = ACCENT_GREEN if tradeable else ACCENT_RED
verdict_text = "CO-INTEGRATED: TRADEABLE PAIR" if tradeable else "WARNING: DO NOT TRADE"
c1.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {verdict_color}55;'
    f'border-radius:12px;padding:16px 18px;box-shadow:0 0 14px {verdict_color}33;">'
    f'<div style="font-family:{FONT_MONO};font-size:2.4rem;font-weight:700;'
    f'color:{verdict_color};">{res["p_value"]:.4f}</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.7rem;text-transform:uppercase;'
    f'letter-spacing:2px;color:{TEXT_MUTED};margin-top:4px;">ADF p-value</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.85rem;font-weight:700;'
    f'color:{verdict_color};margin-top:8px;">{verdict_text}</div></div>',
    unsafe_allow_html=True)
c2.markdown(metric_card("Hedge Ratio", f"{res['hedge_ratio']:.3f}", ACCENT_CYAN), unsafe_allow_html=True)
c3.markdown(metric_card("Return Corr", f"{res['corr']:.2f}", ACCENT_VIOLET), unsafe_allow_html=True)
cur_z = float(res["z"].iloc[-1])
z_col = ACCENT_RED if cur_z > Z_BAND else (ACCENT_GREEN if cur_z < -Z_BAND else TEXT_PRIMARY)
c4.markdown(metric_card("Current Z", f"{cur_z:+.2f}", z_col), unsafe_allow_html=True)

# ---- z-score chart ----
st.markdown(section_header("Spread Z-Score — the rubber band"), unsafe_allow_html=True)
st.plotly_chart(zscore_chart(res["z"], ticker_a, ticker_b), width="stretch")

# ---- honest caveats ----
st.markdown(section_header("Read before trading"), unsafe_allow_html=True)
st.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-left:3px solid '
    f'{ACCENT_AMBER};border-radius:12px;padding:14px 16px;font-family:{FONT_SANS};'
    f'font-size:0.85rem;color:{TEXT_SECONDARY};line-height:1.7;">'
    f'1. The ADF p-value is <b>in-sample</b>: scan 20 random pairs and one will "pass" at '
    f'p&lt;0.05 by luck alone. Demand an economic reason the pair is linked.<br>'
    f'2. Co-integration <b>breaks</b> — the band can snap instead of snapping back. '
    f'Position sizing and a stop on the spread are mandatory.<br>'
    f'3. Nothing here models borrow cost, margin, or slippage on two legs.</div>',
    unsafe_allow_html=True)
