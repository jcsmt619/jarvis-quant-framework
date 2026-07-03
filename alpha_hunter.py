"""
alpha_hunter.py
===============
Random Forest Feature Hunter — Streamlit "Predictive Alpha Ranking" dashboard.

~40 technical indicators (momentum / volatility / trend / volume, all strictly
causal) -> RandomForestClassifier -> which features carry next-day predictive
power for a given ticker.

DELIBERATE DEVIATIONS from the master prompt (both are upgrades):
  * pandas_ta is NOT used — it is incompatible with NumPy 2.x (np.NaN removal).
    The indicator set is generated from this repo's own causal helpers instead.
  * feature_importances_ (impurity gain) is shown BUT the ranking headline uses
    PERMUTATION importance on the untouched test set — impurity importance is
    biased toward high-cardinality noise, per the course's own ML module.

HONEST FRAMING (in the UI): next-day direction is ~coin-flip territory.
Accuracy is shown AGAINST the majority-class baseline; beating 50% is not
edge, beating the baseline out-of-sample repeatedly might be.

Run:  streamlit run alpha_hunter.py
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance

from design_system import *

st.set_page_config(page_title="Alpha Hunter", layout="wide", page_icon="~")
apply_theme()


# ---------------------------------------------------------------------------
# Feature factory (all rolling/causal; ~40 features)
# ---------------------------------------------------------------------------
def build_indicators(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    f = pd.DataFrame(index=df.index)
    r = c.pct_change()

    # momentum
    for p in (2, 5, 10, 20, 60):
        f[f"roc_{p}"] = c.pct_change(p)
    delta = c.diff()
    for p in (7, 14, 28):
        up = delta.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
        f[f"rsi_{p}"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    f["macd"] = macd / c
    f["macd_signal"] = (macd - macd.ewm(span=9, adjust=False).mean()) / c
    lo14, hi14 = l.rolling(14).min(), h.rolling(14).max()
    f["stoch_k"] = 100 * (c - lo14) / (hi14 - lo14).replace(0, np.nan)
    f["stoch_d"] = f["stoch_k"].rolling(3).mean()
    f["williams_r"] = -100 * (hi14 - c) / (hi14 - lo14).replace(0, np.nan)

    # volatility
    prev = c.shift(1)
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    for p in (7, 14, 28):
        f[f"atr_{p}"] = tr.ewm(alpha=1 / p, adjust=False).mean() / c
    for p in (5, 20, 60):
        f[f"vol_{p}"] = r.rolling(p).std()
    f["vol_ratio_5_20"] = f["vol_5"] / f["vol_20"].replace(0, np.nan)
    sma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()
    f["bb_width"] = 4 * sd20 / sma20
    f["bb_pos"] = (c - sma20) / (2 * sd20).replace(0, np.nan)
    f["downside_dev_20"] = np.sqrt(r.clip(upper=0).pow(2).rolling(20).mean())
    f["vol_asym_20"] = f["downside_dev_20"] / f["vol_20"].replace(0, np.nan)

    # trend
    for p in (10, 20, 50, 200):
        sma = c.rolling(p).mean()
        f[f"dist_sma_{p}"] = (c - sma) / c
    f["ema9_21"] = (c.ewm(span=9, adjust=False).mean() - c.ewm(span=21, adjust=False).mean()) / c
    up_m, dn_m = h.diff(), -l.diff()
    plus_dm = pd.Series(np.where((up_m > dn_m) & (up_m > 0), up_m, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn_m > up_m) & (dn_m > 0), dn_m, 0.0), index=df.index)
    atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr14
    mdi = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False).mean() / atr14
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    f["adx_14"] = dx.ewm(alpha=1 / 14, adjust=False).mean()
    f["di_diff"] = pdi - mdi
    f["hi52_prox"] = c / c.rolling(252).max()
    f["lo52_prox"] = c / c.rolling(252).min()

    # volume
    f["vol_z_20"] = (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan)
    f["vol_trend_10"] = v.rolling(10).mean() / v.rolling(50).mean().replace(0, np.nan)
    f["obv_slope"] = (np.sign(r).fillna(0) * v).cumsum().diff(10) / v.rolling(50).mean().replace(0, np.nan)

    return f


@st.cache_data(show_spinner=False)
def run_hunt(ticker: str, start: str, end: str, n_trees: int) -> dict:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty or len(df) < 400:
        return {"error": "Not enough data (need 400+ bars)."}

    feats = build_indicators(df)
    # Target: 1 if TOMORROW's close > today's close. shift(-1) on the TARGET
    # only — features at t predict t+1. The final row (unknown future) is dropped.
    target = (df["Close"].shift(-1) > df["Close"]).astype(int)
    data = feats.join(target.rename("target")).replace([np.inf, -np.inf], np.nan).dropna()

    X, y = data.drop(columns="target"), data["target"]
    split = int(len(X) * 0.80)                    # chronological, shuffle=False
    X_tr, X_te, y_tr, y_te = X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]

    rf = RandomForestClassifier(n_estimators=n_trees, min_samples_leaf=20,
                                random_state=42, n_jobs=-1)
    rf.fit(X_tr, y_tr)

    acc = float(rf.score(X_te, y_te))
    baseline = float(max(y_te.mean(), 1 - y_te.mean()))   # majority class on test

    perm = permutation_importance(rf, X_te, y_te, n_repeats=10, random_state=42, n_jobs=-1)
    return {
        "n_features": X.shape[1], "n_train": len(X_tr), "n_test": len(X_te),
        "accuracy": acc, "baseline": baseline,
        "impurity": pd.Series(rf.feature_importances_, index=X.columns),
        "permutation": pd.Series(perm.importances_mean, index=X.columns),
        "test_span": f"{X_te.index[0]:%Y-%m-%d} → {X_te.index[-1]:%Y-%m-%d}",
    }


def ranking_chart(imp: pd.Series, title: str) -> go.Figure:
    s = imp.sort_values()
    colors = [TEXT_MUTED] * len(s)
    for i in range(max(0, len(s) - 5), len(s)):
        colors[i] = ACCENT_GREEN
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index, orientation="h", marker_color=colors,
        hovertemplate="%{y}: %{x:.4f}<extra></extra>"))
    fig.update_layout(**get_plotly_layout(), height=max(500, 16 * len(s)),
                      title=dict(text=title, font=dict(size=13, color=TEXT_SECONDARY)))
    return fig


# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(section_header("Hunt Configuration"), unsafe_allow_html=True)
    ticker = st.text_input("Ticker", value="SPY").strip().upper()
    today = dt.date.today()
    dr = st.date_input("Date range", value=(today - dt.timedelta(days=365 * 8), today))
    n_trees = st.slider("Number of Trees", 50, 500, 100, step=50)

start_d, end_d = (dr if isinstance(dr, (tuple, list)) and len(dr) == 2
                  else (today - dt.timedelta(days=365 * 8), today))

st.markdown(
    f'<div style="font-family:{FONT_MONO};font-size:2.2rem;font-weight:700;'
    f'color:{TEXT_PRIMARY};">{ticker}'
    f'<span style="font-size:0.9rem;color:{TEXT_MUTED};font-family:{FONT_SANS};'
    f'letter-spacing:2px;"> &nbsp;RANDOM FOREST FEATURE HUNTER</span></div>',
    unsafe_allow_html=True)

with st.spinner("Growing the forest..."):
    res = run_hunt(ticker, str(start_d), str(end_d), int(n_trees))
if "error" in res:
    st.error(res["error"])
    st.stop()

edge = res["accuracy"] - res["baseline"]
c1, c2, c3, c4 = st.columns(4)
c1.markdown(metric_card("Test Accuracy", f"{res['accuracy']:.1%}",
                        pnl_color(edge)), unsafe_allow_html=True)
c2.markdown(metric_card("Majority Baseline", f"{res['baseline']:.1%}", TEXT_SECONDARY),
            unsafe_allow_html=True)
c3.markdown(metric_card("Edge vs Baseline", f"{edge:+.1%}", pnl_color(edge)),
            unsafe_allow_html=True)
c4.markdown(metric_card("Features Tested", f"{res['n_features']}", ACCENT_CYAN),
            unsafe_allow_html=True)
st.markdown(
    f'<div style="font-family:{FONT_SANS};font-size:0.75rem;color:{TEXT_MUTED};'
    f'margin-top:4px;">blind test: {res["n_test"]} bars ({res["test_span"]}), '
    f'chronological split, no shuffle</div>', unsafe_allow_html=True)

st.markdown(section_header("Predictive Alpha Ranking — permutation importance (test set)"),
            unsafe_allow_html=True)
st.plotly_chart(ranking_chart(res["permutation"],
                "Positive = shuffling this feature HURTS out-of-sample accuracy"),
                width="stretch")

with st.expander("Impurity importance (the misleading default — for comparison)"):
    st.plotly_chart(ranking_chart(res["impurity"], "In-sample gain importance"),
                    width="stretch")

st.markdown(section_header("Read before believing"), unsafe_allow_html=True)
st.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-left:3px solid '
    f'{ACCENT_AMBER};border-radius:12px;padding:14px 16px;font-family:{FONT_SANS};'
    f'font-size:0.85rem;color:{TEXT_SECONDARY};line-height:1.7;">'
    f'1. Next-day direction is near coin-flip; judge the model against the '
    f'<b>{res["baseline"]:.1%} majority baseline</b>, not 50%.<br>'
    f'2. One test window = one sample. A feature that ranks top-5 here must repeat '
    f'across tickers and periods before it means anything.<br>'
    f'3. Ranking features is a hypothesis generator — any strategy built on them still '
    f'owes the full walk-forward + deflated-Sharpe validation gauntlet.</div>',
    unsafe_allow_html=True)
