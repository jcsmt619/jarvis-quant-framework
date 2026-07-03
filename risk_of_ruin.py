"""
risk_of_ruin.py
===============
Monte Carlo "Risk of Ruin" Simulator — Streamlit dashboard.

Takes a CSV of per-trade returns, bootstraps thousands of alternate trade
orderings, and reports the probability of hitting a ruinous drawdown.
Module rule (from the course): Risk of Ruin > 5% at the 20% drawdown line
means the strategy is dead — regardless of its average return.

Deviations from the master prompt (disclosed):
  * plotly instead of matplotlib (house standard; the transparent fan cloud
    actually renders better and stays interactive).
  * Demo fallback: if no CSV is uploaded, the repo's Golden Master trade log
    (data/sample_trades.csv) is used so the dashboard is never empty.

Run:  streamlit run risk_of_ruin.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from design_system import *

st.set_page_config(page_title="Risk of Ruin", layout="wide", page_icon="~")
apply_theme()

ROOT = Path(__file__).resolve().parent
GOLDEN_MASTER = ROOT / "data" / "sample_trades.csv"


# ---------------------------------------------------------------------------
def load_returns(uploaded, demo_capital: float) -> tuple[np.ndarray, str]:
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        col = df.select_dtypes("number").columns[0]
        return df[col].dropna().to_numpy(dtype=float), f"uploaded CSV ({col})"
    if GOLDEN_MASTER.exists():
        pnl = pd.read_csv(GOLDEN_MASTER)["pnl"].dropna().to_numpy(dtype=float)
        return pnl / demo_capital, "Golden Master demo (pnl / $10k account)"
    rng = np.random.default_rng(7)
    return rng.normal(0.003, 0.02, 200), "synthetic demo"


@st.cache_data(show_spinner=False)
def simulate(returns: tuple[float, ...], n_sims: int, n_trades: int,
             ruin_dd: float, seed: int = 42) -> dict:
    r = np.asarray(returns)
    rng = np.random.default_rng(seed)
    draws = rng.choice(r, size=(n_sims, n_trades), replace=True)
    equity = np.cumprod(1.0 + draws, axis=1)                    # (sims, trades)
    peaks = np.maximum.accumulate(equity, axis=1)
    dd = (peaks - equity) / peaks
    max_dd = dd.max(axis=1)
    finals = equity[:, -1]
    return {
        "equity": equity, "finals": finals, "max_dd": max_dd,
        "ruin_prob": float((max_dd >= ruin_dd).mean()),
        "p_loss": float((finals < 1.0).mean()),
        "median_final": float(np.median(finals)),
        "p5": float(np.percentile(finals, 5)), "p95": float(np.percentile(finals, 95)),
        "worst_idx": int(np.argmin(finals)),
        "median_idx": int(np.argsort(finals)[len(finals) // 2]),
        "dd_pcts": {p: float(np.percentile(max_dd, p)) for p in (5, 25, 50, 75, 95)},
    }


def fan_chart(sim: dict, max_lines: int = 400) -> go.Figure:
    eq = sim["equity"]
    n_sims, n_trades = eq.shape
    x = np.arange(n_trades + 1)
    fig = go.Figure()
    step = max(1, n_sims // max_lines)
    for i in range(0, n_sims, step):                     # the glowing cloud
        fig.add_trace(go.Scatter(
            x=x, y=np.concatenate([[1.0], eq[i]]), mode="lines",
            line=dict(color=f"rgba(0,212,255,0.018)", width=1),
            hoverinfo="skip", showlegend=False))
    for idx, color, name, width in (
            (sim["worst_idx"], ACCENT_RED, "Worst case", 2.5),
            (sim["median_idx"], ACCENT_CYAN, "Median", 2.5)):
        fig.add_trace(go.Scatter(
            x=x, y=np.concatenate([[1.0], eq[idx]]), mode="lines",
            name=name, line=dict(color=color, width=width)))
    fig.add_hline(y=1.0, line_dash="dash", line_color=GRID_LINE)
    layout = get_plotly_layout()
    layout["legend"] = dict(orientation="h", y=1.05, bgcolor="rgba(0,0,0,0)",
                            font=dict(family="DM Sans", color=TEXT_SECONDARY, size=11))
    fig.update_layout(**layout, height=460)
    fig.update_yaxes(title_text="Equity multiple", type="log")
    fig.update_xaxes(title_text="Trade #")
    return fig


# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(section_header("Simulation Config"), unsafe_allow_html=True)
    uploaded = st.file_uploader("Trade returns CSV (one numeric column)", type="csv")
    n_sims = st.slider("Simulations", 500, 10_000, 1_000, step=500)
    n_trades = st.slider("Trades per timeline", 50, 1_000, 250, step=50)
    ruin_dd = st.slider("Ruin drawdown threshold", 0.10, 0.50, 0.20, step=0.05)

returns, source = load_returns(uploaded, demo_capital=10_000.0)
sim = simulate(tuple(returns), n_sims, n_trades, ruin_dd)

st.markdown(
    f'<div style="font-family:{FONT_MONO};font-size:2.2rem;font-weight:700;'
    f'color:{TEXT_PRIMARY};">MONTE CARLO RISK OF RUIN'
    f'<span style="font-size:0.85rem;color:{TEXT_MUTED};font-family:{FONT_SANS};'
    f'letter-spacing:2px;"> &nbsp;{len(returns)} trades &middot; {source}</span></div>',
    unsafe_allow_html=True)

ruin = sim["ruin_prob"]
ruin_color = ACCENT_GREEN if ruin < 0.05 else (ACCENT_AMBER if ruin < 0.15 else ACCENT_RED)
verdict = ("SURVIVABLE" if ruin < 0.05 else
           "MARGINAL — size down" if ruin < 0.15 else "DEAD — do not fund")

c1, c2, c3, c4 = st.columns(4)
c1.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {ruin_color}55;border-radius:12px;'
    f'padding:16px 18px;box-shadow:0 0 14px {ruin_color}33;">'
    f'<div style="font-family:{FONT_MONO};font-size:2.4rem;font-weight:700;'
    f'color:{ruin_color};">{ruin:.1%}</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.68rem;text-transform:uppercase;'
    f'letter-spacing:2px;color:{TEXT_MUTED};margin-top:4px;">Risk of Ruin '
    f'({ruin_dd:.0%} DD)</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.8rem;font-weight:700;'
    f'color:{ruin_color};margin-top:6px;">{verdict}</div></div>',
    unsafe_allow_html=True)
c2.markdown(metric_card("P(finish at loss)", f"{sim['p_loss']:.1%}",
                        pnl_color(-sim["p_loss"] + 0.10)), unsafe_allow_html=True)
c3.markdown(metric_card("Median outcome", f"{sim['median_final'] - 1:+.1%}",
                        pnl_color(sim["median_final"] - 1)), unsafe_allow_html=True)
c4.markdown(metric_card("5th–95th pct", f"{sim['p5'] - 1:+.0%} … {sim['p95'] - 1:+.0%}",
                        ACCENT_CYAN), unsafe_allow_html=True)

st.markdown(section_header("1,000 alternate realities — the probability cloud"),
            unsafe_allow_html=True)
st.plotly_chart(fan_chart(sim), width="stretch")

st.markdown(section_header("Max drawdown distribution"), unsafe_allow_html=True)
dd_cols = st.columns(5)
for col, (p, v) in zip(dd_cols, sim["dd_pcts"].items()):
    color = ACCENT_GREEN if v < 0.15 else (ACCENT_AMBER if v < 0.30 else ACCENT_RED)
    col.markdown(metric_card(f"{p}th pct", f"{v:.1%}", color), unsafe_allow_html=True)

st.markdown(section_header("Read before funding"), unsafe_allow_html=True)
st.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-left:3px solid '
    f'{ACCENT_AMBER};border-radius:12px;padding:14px 16px;font-family:{FONT_SANS};'
    f'font-size:0.85rem;color:{TEXT_SECONDARY};line-height:1.7;">'
    f'1. Bootstrap resampling assumes trades are INDEPENDENT — real losing streaks '
    f'cluster (regimes), so true tail risk is somewhat WORSE than shown.<br>'
    f'2. The input trades are one historical sample; if the edge decays, every '
    f'timeline here is too optimistic.<br>'
    f'3. Module rule: Risk of Ruin &gt; 5% at the {ruin_dd:.0%} line = the strategy '
    f'is dead at this size. Sizing down cuts RoR faster than any entry tweak.</div>',
    unsafe_allow_html=True)
