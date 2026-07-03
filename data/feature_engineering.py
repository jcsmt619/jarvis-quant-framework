"""
data/feature_engineering.py
===========================
Pure, vectorized feature functions that turn OHLCV into the observable inputs
for the HMM volatility classifier (STEP 2 of the AI Pathways Automated Trading
Foundations track).

Design rules:
  * Every function is PURE: it takes a frame/series and returns a new series,
    with NO in-place mutation and NO dependence on global state.
  * Everything is causal (uses only trailing windows), so building features on
    a growing slice never rewrites past values -- a prerequisite for the
    no-look-ahead guarantee enforced in the HMM layer.
  * 14 features are produced, then standardized with a 252-period rolling
    z-score so the Gaussian HMM sees comparable, roughly-stationary inputs.

Expected input columns (case-insensitive): open, high, low, close, volume.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Ordered list of the 16 feature columns produced by build_features().
FEATURE_COLUMNS: list[str] = [
    "logret_1",
    "logret_5",
    "logret_20",
    "realized_vol_20",
    "vol_ratio_5_20",
    "downside_dev_20",
    "vol_asymmetry_20",
    "volume_z_50",
    "volume_trend_10",
    "adx_14",
    "sma_slope_50",
    "rsi_z_14",
    "dist_from_sma_200",
    "roc_10",
    "roc_20",
    "atr_norm_14",
]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(f"feature engineering requires columns {required}; missing {missing}")
    return out


def log_returns(close: pd.Series, period: int = 1) -> pd.Series:
    """Log return over `period` bars: ln(P_t / P_{t-period})."""
    return np.log(close / close.shift(period))


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling standard deviation of 1-bar log returns (realized volatility)."""
    r = log_returns(close, 1)
    return r.rolling(window).std()


def vol_ratio(close: pd.Series, fast: int = 5, slow: int = 20) -> pd.Series:
    """Ratio of short-window vol to long-window vol (vol regime accelerator)."""
    r = log_returns(close, 1)
    fast_vol = r.rolling(fast).std()
    slow_vol = r.rolling(slow).std()
    return fast_vol / slow_vol.replace(0.0, np.nan)


def downside_deviation(close: pd.Series, window: int = 20) -> pd.Series:
    """Sortino-style downside deviation: rolling RMS of NEGATIVE returns only.
    Distinguishes crash volatility from rally volatility -- a violent up-move
    has high realized_vol but LOW downside deviation."""
    r = log_returns(close, 1)
    neg_sq = r.clip(upper=0.0).pow(2)
    return np.sqrt(neg_sq.rolling(window).mean())


def vol_asymmetry(close: pd.Series, window: int = 20) -> pd.Series:
    """Downside share of total volatility: downside_dev / realized_vol in (0, ~1.4).
    ~0.7 = symmetric; <0.5 = upside-dominated (rally); >0.9 = crash-dominated."""
    dd = downside_deviation(close, window)
    rv = realized_vol(close, window)
    return dd / rv.replace(0.0, np.nan)


def volume_zscore(volume: pd.Series, window: int = 50) -> pd.Series:
    """Z-score of volume vs its trailing `window` mean/std."""
    mean = volume.rolling(window).mean()
    std = volume.rolling(window).std()
    return (volume - mean) / std.replace(0.0, np.nan)


def volume_trend(volume: pd.Series, window: int = 10) -> pd.Series:
    """Slope of the `window`-period SMA of volume (per-bar change), scaled."""
    sma = volume.rolling(window).mean()
    slope = sma.diff()
    # Scale by the rolling mean so the feature is unit-free across assets.
    return slope / sma.replace(0.0, np.nan)


def _wilder_smma(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed moving average (used by ADX / RSI)."""
    return series.ewm(alpha=1.0 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (Wilder), trend-strength feature."""
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = _wilder_smma(tr, period)
    plus_di = 100.0 * _wilder_smma(plus_dm, period) / atr.replace(0.0, np.nan)
    minus_di = 100.0 * _wilder_smma(minus_dm, period) / atr.replace(0.0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return _wilder_smma(dx, period)


def sma_slope(close: pd.Series, window: int = 50) -> pd.Series:
    """Per-bar slope of the `window`-SMA, normalized by price."""
    sma = close.rolling(window).mean()
    return sma.diff() / close


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI(period)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = _wilder_smma(gain, period)
    avg_loss = _wilder_smma(loss, period)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def rsi_zscore(close: pd.Series, period: int = 14, window: int = 252) -> pd.Series:
    """Z-score of RSI(period) over a trailing `window`."""
    r = rsi(close, period)
    mean = r.rolling(window).mean()
    std = r.rolling(window).std()
    return (r - mean) / std.replace(0.0, np.nan)


def distance_from_sma(close: pd.Series, window: int = 200) -> pd.Series:
    """Distance of price from its `window`-SMA, as a fraction of price."""
    sma = close.rolling(window).mean()
    return (close - sma) / close


def roc(close: pd.Series, period: int = 10) -> pd.Series:
    """Rate of change over `period` bars (simple percentage momentum)."""
    return close.pct_change(period)


def atr_normalized(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR(period) divided by close -> unit-free range/volatility feature."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = _wilder_smma(tr, period)
    return atr / close


# ---------------------------------------------------------------------------
# Assembly + standardization
# ---------------------------------------------------------------------------
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all 14 raw observable features from an OHLCV frame."""
    data = _normalize_columns(df)
    close, volume = data["close"], data["volume"]

    features = pd.DataFrame(index=data.index)
    features["logret_1"] = log_returns(close, 1)
    features["logret_5"] = log_returns(close, 5)
    features["logret_20"] = log_returns(close, 20)
    features["realized_vol_20"] = realized_vol(close, 20)
    features["vol_ratio_5_20"] = vol_ratio(close, 5, 20)
    features["downside_dev_20"] = downside_deviation(close, 20)
    features["vol_asymmetry_20"] = vol_asymmetry(close, 20)
    features["volume_z_50"] = volume_zscore(volume, 50)
    features["volume_trend_10"] = volume_trend(volume, 10)
    features["adx_14"] = adx(data, 14)
    features["sma_slope_50"] = sma_slope(close, 50)
    features["rsi_z_14"] = rsi_zscore(close, 14, 252)
    features["dist_from_sma_200"] = distance_from_sma(close, 200)
    features["roc_10"] = roc(close, 10)
    features["roc_20"] = roc(close, 20)
    features["atr_norm_14"] = atr_normalized(data, 14)

    return features[FEATURE_COLUMNS]


def standardize_features(features: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """
    Rolling z-score standardization (trailing `window`). Causal by construction:
    the z-score at bar t uses only bars [t-window+1 .. t], so appending future
    bars never changes past standardized values.
    """
    mean = features.rolling(window).mean()
    std = features.rolling(window).std()
    standardized = (features - mean) / std.replace(0.0, np.nan)
    return standardized


def build_standardized_features(df: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """
    Convenience pipeline: raw features -> rolling z-score -> drop warmup rows.
    Returns only fully-populated rows (no NaNs), ready for the HMM.
    """
    raw = build_features(df)
    std = standardize_features(raw, window)
    return std.replace([np.inf, -np.inf], np.nan).dropna()
