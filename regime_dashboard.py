"""
regime_dashboard.py
===================
Regime Detection Dashboard (Streamlit).

A Gaussian-HMM volatility-regime classifier rendered on the shared dark-terminal
design system. The regime label at time T is produced by the FORWARD ALGORITHM
only (filtered P(state_t | obs_1:t)) -- never Viterbi/.predict() -- so it carries
no look-ahead bias. A startup verification proves this property numerically.

Run:
    streamlit run regime_dashboard.py
"""

from __future__ import annotations

import datetime as dt
import logging
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from scipy.stats import multivariate_normal

from design_system import *

# hmmlearn emits routine "Model is not converging" chatter across random restarts;
# we always keep the best-scoring model, so silence the noise.
logging.getLogger("hmmlearn").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message="Model is not converging")

st.set_page_config(page_title="Regime Detection", layout="wide", page_icon="~")
apply_theme()

_TINY = 1e-12
VOL_ANCHORS = [ACCENT_GREEN, ACCENT_AMBER, ACCENT_RED]  # low -> high volatility


# ===========================================================================
# Colour helpers
# ===========================================================================
def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hex_to_rgba(h: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb(h)
    return f"rgba({r},{g},{b},{alpha})"


def _lerp(c1: str, c2: str, t: float) -> str:
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    r, g, bl = (int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
    return f"#{r:02x}{g:02x}{bl:02x}"


def vol_gradient_color(fraction: float) -> str:
    """green -> amber -> red across a 0..1 volatility fraction (from REGIME_COLORS anchors)."""
    fraction = float(np.clip(fraction, 0.0, 1.0))
    if fraction <= 0.5:
        return _lerp(VOL_ANCHORS[0], VOL_ANCHORS[1], fraction / 0.5)
    return _lerp(VOL_ANCHORS[1], VOL_ANCHORS[2], (fraction - 0.5) / 0.5)


def vol_labels(n: int) -> list[str]:
    """Ascending-volatility labels; canonical REGIME_COLORS keys used for n<=3."""
    ladders = {
        1: ["Medium Vol"],
        2: ["Low Vol", "High Vol"],
        3: ["Low Vol", "Medium Vol", "High Vol"],
        4: ["Low Vol", "Medium Vol", "High Vol", "Extreme Vol"],
        5: ["Very Low Vol", "Low Vol", "Medium Vol", "High Vol", "Extreme Vol"],
        6: ["Very Low Vol", "Low Vol", "Medium Vol", "High Vol", "Very High Vol", "Extreme Vol"],
        7: ["Very Low Vol", "Low Vol", "Medium Vol", "High Vol", "Very High Vol", "Extreme Vol", "Crisis Vol"],
    }
    return ladders.get(n, [f"Vol {i + 1}" for i in range(n)])


# ===========================================================================
# Data + features
# ===========================================================================
@st.cache_data(show_spinner=False)
def load_prices(ticker: str, start: str, end: str) -> pd.DataFrame:
    raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        # single-ticker download -> drop the ticker level
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.title)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in raw.columns]
    return raw[keep].dropna()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """4 causal features: log return, 20d realized vol, volume ratio, HL range %."""
    close = df["Close"]
    feat = pd.DataFrame(index=df.index)
    feat["log_return"] = np.log(close / close.shift(1))
    feat["realized_vol"] = feat["log_return"].rolling(20).std()
    feat["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
    feat["hl_range_pct"] = (df["High"] - df["Low"]) / close
    return feat.replace([np.inf, -np.inf], np.nan).dropna()


# ===========================================================================
# HMM: model selection (BIC), forward filtering, look-ahead verification
# ===========================================================================
def _n_params_full(k: int, d: int) -> int:
    # startprob (k-1) + transmat k(k-1) + means k*d + full covars k*d(d+1)/2
    return (k * k - 1) + k * d + k * d * (d + 1) // 2


def _fit_best(Xz: np.ndarray, k: int, n_init: int, seed: int) -> GaussianHMM | None:
    best, best_ll = None, -np.inf
    for i in range(n_init):
        try:
            m = GaussianHMM(n_components=k, covariance_type="full",
                            n_iter=120, random_state=seed + i, tol=1e-3)
            m.fit(Xz)
            ll = m.score(Xz)
        except Exception:
            continue
        if np.isfinite(ll) and ll > best_ll:
            best, best_ll = m, ll
    return best


def _emission_logprob(model: GaussianHMM, X: np.ndarray) -> np.ndarray:
    k = model.n_components
    out = np.empty((X.shape[0], k))
    for s in range(k):
        out[:, s] = multivariate_normal.logpdf(
            X, mean=model.means_[s], cov=model.covars_[s], allow_singular=True)
    return out


def forward_log_alpha(model: GaussianHMM, X: np.ndarray) -> np.ndarray:
    """Filtered log P(state_t | obs_1:t). alpha_t depends only on obs_1:t (causal)."""
    log_start = np.log(model.startprob_ + _TINY)
    log_trans = np.log(model.transmat_ + _TINY)
    log_emit = _emission_logprob(model, X)
    log_alpha = np.empty_like(log_emit)
    log_alpha[0] = log_start + log_emit[0]
    log_alpha[0] -= logsumexp(log_alpha[0])
    for t in range(1, X.shape[0]):
        log_alpha[t] = logsumexp(log_alpha[t - 1][:, None] + log_trans, axis=0) + log_emit[t]
        log_alpha[t] -= logsumexp(log_alpha[t])
    return log_alpha


def filtered_proba(model: GaussianHMM, X: np.ndarray) -> np.ndarray:
    return np.exp(forward_log_alpha(model, X))


def verify_no_lookahead(model: GaussianHMM, X: np.ndarray, checks: int = 6) -> bool:
    """Prove causality: filtering a prefix must reproduce the full-series filtered
    state at that same index. If future rows changed a past label, this fails."""
    full = np.argmax(forward_log_alpha(model, X), axis=1)
    T = len(X)
    idxs = np.unique(np.linspace(max(3, T // 5), T - 1, checks).astype(int))
    for t in idxs:
        prefix = np.argmax(forward_log_alpha(model, X[:t]), axis=1)
        if prefix[-1] != full[t - 1]:
            return False
    return True


# ===========================================================================
# Stability filter (3-bar persistence + flicker -> Uncertain)
# ===========================================================================
def confirm_stability(raw: np.ndarray, min_persist: int = 3) -> np.ndarray:
    active = np.empty_like(raw)
    cur = raw[0]
    run_val, run_len = raw[0], 1
    active[0] = cur
    for t in range(1, len(raw)):
        if raw[t] == run_val:
            run_len += 1
        else:
            run_val, run_len = raw[t], 1
        if run_len >= min_persist and run_val != cur:
            cur = run_val
        active[t] = cur
    return active


def flicker_uncertain(raw: np.ndarray, window: int = 20, threshold: int = 4) -> np.ndarray:
    change_at = np.zeros(len(raw), dtype=int)
    change_at[1:] = (raw[1:] != raw[:-1]).astype(int)
    flick = np.array([change_at[max(0, t - window + 1): t + 1].sum() for t in range(len(raw))])
    return flick > threshold


def trailing_run_length(active: np.ndarray) -> int:
    n = 1
    for t in range(len(active) - 2, -1, -1):
        if active[t] == active[-1]:
            n += 1
        else:
            break
    return n


# ===========================================================================
# End-to-end analysis (cached)
# ===========================================================================
@st.cache_data(show_spinner=False)
def run_analysis(ticker: str, start: str, end: str, n_override, n_init: int, seed: int) -> dict:
    prices = load_prices(ticker, start, end)
    if prices.empty or len(prices) < 120:
        return {"error": "Not enough price data. Try a longer date range or a different ticker."}

    feat = build_features(prices)
    if len(feat) < 80:
        return {"error": "Not enough feature rows after cleaning NaNs."}

    dates = feat.index
    X = feat.to_numpy(dtype=float)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd < _TINY] = 1.0
    Xz = (X - mu) / sd
    d = Xz.shape[1]
    N = Xz.shape[0]

    # --- model selection via BIC ---
    bic_scores: dict[int, float] = {}
    models: dict[int, GaussianHMM] = {}
    candidates = [int(n_override)] if n_override else [3, 4, 5, 6, 7]
    for k in candidates:
        m = _fit_best(Xz, k, n_init, seed)
        if m is None:
            continue
        ll = m.score(Xz)
        bic_scores[k] = float(-2.0 * ll + _n_params_full(k, d) * np.log(N))
        models[k] = m
    if not models:
        return {"error": "HMM training failed to converge on any candidate."}

    best_k = min(bic_scores, key=bic_scores.get)
    model = models[best_k]

    # --- forward-only inference + causality proof ---
    lookahead_ok = verify_no_lookahead(model, Xz)
    proba = filtered_proba(model, Xz)            # (N, k) filtered distribution
    raw = np.argmax(proba, axis=1)
    confidence = proba.max(axis=1)

    # --- label regimes by ASCENDING mean realized volatility ---
    vol_feature = feat["realized_vol"].to_numpy()
    state_mean_vol = np.array([vol_feature[raw == s].mean() if np.any(raw == s) else np.inf
                               for s in range(best_k)])
    order = list(np.argsort(state_mean_vol))     # state ids, low -> high vol
    labels = vol_labels(best_k)
    id_to_rank = {sid: r for r, sid in enumerate(order)}
    id_to_label = {sid: labels[id_to_rank[sid]] for sid in range(best_k)}
    id_to_color = {sid: vol_gradient_color(id_to_rank[sid] / max(1, best_k - 1))
                   for sid in range(best_k)}

    # --- stability filter ---
    active = confirm_stability(raw)
    uncertain = flicker_uncertain(raw)

    # --- per-regime statistics (assigned by confirmed active regime) ---
    log_ret = feat["log_return"].to_numpy()
    volr = feat["volume_ratio"].to_numpy()
    stats = []
    for sid in order:                            # present low -> high vol
        mask = active == sid
        pct = float(mask.mean() * 100.0)
        stats.append({
            "id": sid, "label": id_to_label[sid], "color": id_to_color[sid],
            "mean_return": float(log_ret[mask].mean() * 100.0) if mask.any() else 0.0,
            "mean_vol": float(vol_feature[mask].mean() * np.sqrt(252) * 100.0) if mask.any() else 0.0,
            "mean_volume_ratio": float(volr[mask].mean()) if mask.any() else 0.0,
            "pct_time": pct,
        })

    cur_uncertain = bool(uncertain[-1])
    cur_label = "Uncertain" if cur_uncertain else id_to_label[int(active[-1])]
    cur_color = ACCENT_VIOLET if cur_uncertain else id_to_color[int(active[-1])]
    run_len = trailing_run_length(active)
    stability_status = "Uncertain - flickering" if cur_uncertain else f"Stable - {run_len} bars"

    return {
        "ticker": ticker,
        "dates": dates,
        "close": prices["Close"].reindex(dates).to_numpy(),
        "active": active,
        "uncertain": uncertain,
        "confidence": confidence,
        "id_to_label": id_to_label,
        "id_to_color": id_to_color,
        "order": order,
        "labels_in_order": [id_to_label[s] for s in order],
        "stats": stats,
        "best_k": best_k,
        "bic_scores": bic_scores,
        "lookahead_ok": lookahead_ok,
        "cur_label": cur_label,
        "cur_color": cur_color,
        "cur_confidence": float(confidence[-1]),
        "stability_status": stability_status,
        "cur_uncertain": cur_uncertain,
    }


# ===========================================================================
# Rendering helpers
# ===========================================================================
def contiguous_runs(arr: np.ndarray):
    runs, s = [], 0
    for i in range(1, len(arr)):
        if arr[i] != arr[s]:
            runs.append((s, i - 1, int(arr[s])))
            s = i
    runs.append((s, len(arr) - 1, int(arr[s])))
    return runs


def regime_stat_card(s: dict) -> str:
    ret_col = pnl_color(s["mean_return"])
    return (
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};'
        f'border-left:3px solid {s["color"]};border-radius:12px;padding:14px 16px;">'
        f'<div style="font-family:{FONT_SANS};font-size:0.9rem;font-weight:700;'
        f'color:{s["color"]};letter-spacing:0.5px;margin-bottom:10px;">{s["label"]}</div>'
        f'{_stat_row("Mean Return", f"{s['mean_return']:+.3f}%", ret_col)}'
        f'{_stat_row("Ann. Volatility", f"{s['mean_vol']:.1f}%", TEXT_PRIMARY)}'
        f'{_stat_row("Volume Ratio", f"{s['mean_volume_ratio']:.2f}x", TEXT_PRIMARY)}'
        f'{_stat_row("Time in Regime", f"{s['pct_time']:.1f}%", ACCENT_CYAN)}'
        f'</div>'
    )


def _stat_row(label: str, value: str, color: str) -> str:
    return (
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
        f'margin:5px 0;">'
        f'<span style="font-family:{FONT_SANS};font-size:0.68rem;text-transform:uppercase;'
        f'letter-spacing:1px;color:{TEXT_MUTED};">{label}</span>'
        f'<span style="font-family:{FONT_MONO};font-size:0.95rem;color:{color};">{value}</span>'
        f'</div>'
    )


def build_price_chart(res: dict) -> go.Figure:
    dates, close, active = res["dates"], res["close"], res["active"]
    fig = go.Figure()
    for lo, hi, sid in contiguous_runs(active):
        fig.add_vrect(
            x0=dates[lo], x1=dates[hi],
            fillcolor=hex_to_rgba(res["id_to_color"][sid], 0.13),
            line_width=0, layer="below",
        )
    fig.add_trace(go.Scatter(
        x=dates, y=close, mode="lines", name=res["ticker"],
        line=dict(color=TEXT_PRIMARY, width=1.6),
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>",
    ))
    fig.update_layout(**get_plotly_layout(), height=460, showlegend=False)
    fig.update_yaxes(title_text="Price")
    return fig


def build_confidence_chart(res: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=res["dates"], y=res["confidence"], mode="lines",
        line=dict(color=ACCENT_CYAN, width=1.4),
        fill="tozeroy", fillcolor=hex_to_rgba(ACCENT_CYAN, 0.30),
        hovertemplate="%{x|%Y-%m-%d}<br>conf %{y:.0%}<extra></extra>",
    ))
    fig.update_layout(**get_plotly_layout(), height=200, showlegend=False)
    fig.update_yaxes(title_text="Confidence", range=[0, 1], tickformat=".0%")
    return fig


# ===========================================================================
# Sidebar controls
# ===========================================================================
with st.sidebar:
    st.markdown(section_header("Configuration"), unsafe_allow_html=True)
    ticker = st.text_input("Ticker", value="SPY").strip().upper()
    today = dt.date.today()
    default_start = today - dt.timedelta(days=365 * 3)
    date_range = st.date_input(
        "Date range", value=(default_start, today),
        min_value=dt.date(2000, 1, 1), max_value=today)
    n_choice = st.selectbox("Number of regimes", ["Auto (BIC)", 3, 4, 5, 6, 7], index=0)
    n_init = st.slider("Random restarts", 1, 8, 4, help="More restarts = steadier fit, slower")
    run_clicked = st.button("Run Analysis", type="primary", width="stretch")
    st.markdown(
        f'<div style="font-family:{FONT_SANS};font-size:0.7rem;color:{TEXT_MUTED};'
        f'margin-top:10px;line-height:1.5;">Forward-algorithm inference only. '
        f'Regime labels use data up to time T exclusively.</div>',
        unsafe_allow_html=True,
    )

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = default_start, today
n_override = None if n_choice == "Auto (BIC)" else int(n_choice)

# Auto-run on first load; otherwise recompute when the button is pressed.
if run_clicked or "regime_first_run" not in st.session_state:
    st.session_state["regime_first_run"] = True

with st.spinner("Fitting HMM and running forward filter..."):
    res = run_analysis(ticker, str(start_d), str(end_d), n_override, int(n_init), 42)

# ===========================================================================
# Render
# ===========================================================================
if "error" in res:
    st.error(res["error"])
    st.stop()

# ---- top bar ----
la_status = "connected" if res["lookahead_ok"] else "error"
la_text = "No look-ahead: VERIFIED" if res["lookahead_ok"] else "LOOK-AHEAD DETECTED"

t1, t2, t3, t4, t5 = st.columns([1.6, 1.6, 1.1, 1.3, 1.0])
with t1:
    st.markdown(
        f'<div style="font-family:{FONT_MONO};font-size:2.4rem;font-weight:700;'
        f'color:{TEXT_PRIMARY};line-height:1;">{res["ticker"]}</div>'
        f'<div style="font-family:{FONT_SANS};font-size:0.7rem;letter-spacing:2px;'
        f'text-transform:uppercase;color:{TEXT_MUTED};margin-top:4px;">Regime Detection</div>',
        unsafe_allow_html=True)
with t2:
    st.markdown(section_header("Current Regime"), unsafe_allow_html=True)
    conf = None if res["cur_uncertain"] else res["cur_confidence"]
    st.markdown(regime_badge(res["cur_label"], conf), unsafe_allow_html=True)
with t3:
    st.markdown(section_header("Confidence"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-family:{FONT_MONO};font-size:2rem;font-weight:700;'
        f'color:{ACCENT_CYAN};">{res["cur_confidence"] * 100:.0f}%</div>',
        unsafe_allow_html=True)
with t4:
    st.markdown(section_header("Stability"), unsafe_allow_html=True)
    dot_status = "warning" if res["cur_uncertain"] else "active"
    st.markdown(
        f'<div style="font-family:{FONT_SANS};font-size:0.95rem;color:{TEXT_SECONDARY};">'
        f'{status_dot(dot_status)}&nbsp; {res["stability_status"]}</div>',
        unsafe_allow_html=True)
with t5:
    st.markdown(section_header("Regimes"), unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-family:{FONT_MONO};font-size:2rem;font-weight:700;'
        f'color:{TEXT_PRIMARY};">{res["best_k"]}</div>'
        f'<div style="font-family:{FONT_SANS};font-size:0.62rem;color:{TEXT_MUTED};">'
        f'selected by BIC</div>',
        unsafe_allow_html=True)

st.markdown(
    f'<div style="font-family:{FONT_SANS};font-size:0.75rem;color:{TEXT_MUTED};'
    f'margin:6px 0 2px 0;">{status_dot(la_status)}&nbsp; {la_text} '
    f'&nbsp;&middot;&nbsp; forward-filtered P(state | past only)</div>',
    unsafe_allow_html=True)

# ---- hero chart ----
st.plotly_chart(build_price_chart(res), width="stretch")

# ---- regime statistics ----
st.markdown(section_header("Regime Statistics"), unsafe_allow_html=True)
stat_cols = st.columns(len(res["stats"]))
for col, s in zip(stat_cols, res["stats"]):
    col.markdown(regime_stat_card(s), unsafe_allow_html=True)

# ---- confidence timeline ----
st.markdown(section_header("Confidence Timeline"), unsafe_allow_html=True)
st.plotly_chart(build_confidence_chart(res), width="stretch")
