"""
kelly_sizer.py
==============
Dynamic "Half-Kelly" Position Sizing Calculator — Streamlit.

Kelly % = W - (1 - W) / R, W = win rate, R = avg win / avg loss.
Full Kelly shown with a strict warning; Half-Kelly is the recommendation
(course-aligned: settings.yaml runs kelly_fraction 0.5).

HONESTY ADDITIONS beyond the master prompt:
  * NEGATIVE KELLY = NO TRADE — the formula's actual answer when W/R imply
    no edge; the draft prompt never mentions this case.
  * Estimation error: a win rate measured over 30 trades carries a ~±9pt
    standard error. The sizer shows Kelly at the LOWER confidence bound too,
    because sizing to the point estimate of a noisy edge is how Kelly blows
    accounts up in practice.
  * Hard cap: risk per trade is clamped to the repo's risk_per_trade (1.5%)
    course rule, and the clamp is shown when it binds.

Run:  streamlit run kelly_sizer.py
"""

from __future__ import annotations

import numpy as np
import streamlit as st

from design_system import *

st.set_page_config(page_title="Kelly Sizer", layout="wide", page_icon="~")
apply_theme()

RISK_CAP = 0.015          # course rule: cap loss per trade at 1-2% (settings.yaml)


def kelly_pct(win_rate: float, rr: float) -> float:
    if rr <= 0:
        return 0.0
    return win_rate - (1.0 - win_rate) / rr


# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(section_header("Your Numbers"), unsafe_allow_html=True)
    balance = st.number_input("Total account balance ($)", 1_000.0, 100_000_000.0,
                              100_000.0, step=1_000.0)
    win_rate = st.slider("Win rate (last N trades)", 0.05, 0.95, 0.55, step=0.01)
    n_trades = st.number_input("Number of trades measured over", 10, 1_000, 30, step=5)
    rr = st.slider("Avg win / avg loss ratio (R)", 0.2, 5.0, 1.5, step=0.1)
    stop_pct = st.slider("Stop loss on THIS trade (%)", 0.5, 20.0, 2.0, step=0.5) / 100.0

full_k = kelly_pct(win_rate, rr)
half_k = full_k / 2.0

# estimation error on the win rate (binomial SE), Kelly at the -1 sigma bound
se = float(np.sqrt(win_rate * (1 - win_rate) / n_trades))
conservative_k = kelly_pct(max(0.0, win_rate - se), rr) / 2.0

st.markdown(
    f'<div style="font-family:{FONT_MONO};font-size:2.2rem;font-weight:700;'
    f'color:{TEXT_PRIMARY};">DYNAMIC HALF-KELLY SIZER'
    f'<span style="font-size:0.85rem;color:{TEXT_MUTED};font-family:{FONT_SANS};'
    f'letter-spacing:2px;"> &nbsp;Kelly %% = W − (1−W)/R</span></div>',
    unsafe_allow_html=True)

# ---- NO TRADE gate ----
if full_k <= 0:
    st.markdown(
        f'<div style="background:{BG_CARD};border:1px solid {ACCENT_RED}66;'
        f'border-radius:12px;padding:22px;box-shadow:0 0 18px {ACCENT_RED}33;">'
        f'<div style="font-family:{FONT_MONO};font-size:2rem;font-weight:700;'
        f'color:{ACCENT_RED};">NO TRADE — KELLY IS {full_k:.1%}</div>'
        f'<div style="font-family:{FONT_SANS};font-size:0.9rem;color:{TEXT_SECONDARY};'
        f'margin-top:8px;">A {win_rate:.0%} win rate at {rr:.1f}R has NO mathematical '
        f'edge. The optimal bet size on a negative-expectancy game is zero. No position '
        f'size fixes a strategy that loses on average.</div></div>',
        unsafe_allow_html=True)
    st.stop()

# ---- sizing math ----
risk_frac = min(half_k, RISK_CAP)
capped = half_k > RISK_CAP
risk_dollars = balance * risk_frac
position_dollars = risk_dollars / stop_pct

c1, c2, c3 = st.columns(3)
c1.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {ACCENT_RED}44;border-radius:12px;'
    f'padding:16px 18px;">'
    f'<div style="font-family:{FONT_MONO};font-size:2rem;font-weight:700;'
    f'color:{ACCENT_RED};">{full_k:.1%}</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.68rem;text-transform:uppercase;'
    f'letter-spacing:2px;color:{TEXT_MUTED};margin-top:4px;">Full Kelly</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.72rem;color:{ACCENT_RED};'
    f'margin-top:6px;">HIGHLY AGGRESSIVE — one estimate error from a brutal drawdown. '
    f'Do not size to this.</div></div>', unsafe_allow_html=True)
c2.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {ACCENT_GREEN}55;border-radius:12px;'
    f'padding:16px 18px;box-shadow:0 0 14px {ACCENT_GREEN}22;">'
    f'<div style="font-family:{FONT_MONO};font-size:2rem;font-weight:700;'
    f'color:{ACCENT_GREEN};">{half_k:.1%}</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.68rem;text-transform:uppercase;'
    f'letter-spacing:2px;color:{TEXT_MUTED};margin-top:4px;">Half Kelly '
    f'(recommended)</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.72rem;color:{TEXT_SECONDARY};'
    f'margin-top:6px;">~75% of optimal growth at half the variance.</div></div>',
    unsafe_allow_html=True)
c3.markdown(metric_card("Half-Kelly @ −1σ win rate", f"{max(conservative_k, 0):.1%}",
                        ACCENT_VIOLET), unsafe_allow_html=True)
st.markdown(
    f'<div style="font-family:{FONT_SANS};font-size:0.75rem;color:{TEXT_MUTED};'
    f'margin-top:4px;">Win rate {win_rate:.0%} over {n_trades} trades = ±{se:.1%} standard '
    f'error. If the true rate is one sigma lower, the right size is the violet number.</div>',
    unsafe_allow_html=True)

st.markdown(section_header("Order ticket"), unsafe_allow_html=True)
d1, d2, d3 = st.columns(3)
d1.markdown(metric_card("Risk this trade", f"${risk_dollars:,.0f}", ACCENT_CYAN),
            unsafe_allow_html=True)
d2.markdown(metric_card("Position size", f"${position_dollars:,.0f}", TEXT_PRIMARY),
            unsafe_allow_html=True)
d3.markdown(metric_card("Risk fraction", f"{risk_frac:.2%}",
                        ACCENT_AMBER if capped else ACCENT_GREEN), unsafe_allow_html=True)
if capped:
    st.markdown(
        f'<div style="font-family:{FONT_SANS};font-size:0.8rem;color:{ACCENT_AMBER};">'
        f'Half-Kelly wanted {half_k:.1%} but the course risk rule caps loss per trade at '
        f'{RISK_CAP:.1%} of equity (settings.yaml risk_per_trade). The cap wins.</div>',
        unsafe_allow_html=True)
if position_dollars > balance:
    st.markdown(
        f'<div style="font-family:{FONT_SANS};font-size:0.8rem;color:{ACCENT_AMBER};">'
        f'Position exceeds account balance (implies {position_dollars / balance:.1f}x '
        f'leverage) because the stop is tight. Confirm your broker allows it — and that '
        f'a gap through the stop at that size is survivable.</div>',
        unsafe_allow_html=True)
