"""Intraday feature engineering for the regime HMM.

These are the observable inputs the HMM clusters into volatility regimes. The
core indicators mirror the stock template (returns, realized vol, volume,
trend, momentum) so the math is familiar. The additions for futures are
session-relative: distance from the session VWAP, normalized intraday range,
and a cyclical time-of-day encoding so the model can tell the quiet overnight
tape apart from the active cash open.

All functions are pure. Every feature is standardised with a rolling z-score so
the HMM sees stationary inputs regardless of the instrument's price level.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Standardisation
# --------------------------------------------------------------------------

def rolling_zscore(series: pd.Series, window: int = 252) -> pd.Series:
    mean = series.rolling(window, min_periods=window // 2).mean()
    std = series.rolling(window, min_periods=window // 2).std()
    z = (series - mean) / std.replace(0.0, np.nan)
    return z.replace([np.inf, -np.inf], np.nan)


# --------------------------------------------------------------------------
# Primitive indicators
# --------------------------------------------------------------------------

def log_returns(close: pd.Series, period: int = 1) -> pd.Series:
    return np.log(close / close.shift(period))


def realized_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    return log_returns(close).rolling(window, min_periods=max(2, window // 2)).std()


def volatility_ratio(close: pd.Series, short_window: int = 5, long_window: int = 20) -> pd.Series:
    short = realized_volatility(close, short_window)
    long = realized_volatility(close, long_window)
    return short / long.replace(0.0, np.nan)


def normalized_volume(volume: pd.Series, window: int = 50) -> pd.Series:
    mean = volume.rolling(window, min_periods=window // 2).mean()
    std = volume.rolling(window, min_periods=window // 2).std()
    return (volume - mean) / std.replace(0.0, np.nan)


def _slope(values: np.ndarray) -> float:
    n = len(values)
    if n < 2 or np.any(~np.isfinite(values)):
        return np.nan
    x = np.arange(n, dtype=float)
    x_mean = x.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return np.nan
    return float(((x - x_mean) * (values - values.mean())).sum() / denom)


def volume_trend(volume: pd.Series, window: int = 10) -> pd.Series:
    sma = volume.rolling(window, min_periods=window).mean()
    return sma.rolling(window, min_periods=window).apply(_slope, raw=True)


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    a = high - low
    b = (high - prev_close).abs()
    c = (low - prev_close).abs()
    return pd.concat([a, b, c], axis=1).max(axis=1)


def atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = _true_range(bars["high"], bars["low"], bars["close"])
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def normalized_atr(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    return atr(bars, period) / bars["close"]


def adx(bars: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = bars["high"], bars["low"], bars["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = _true_range(high, low, close)
    atr_ = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=bars.index).ewm(
        alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr_.replace(0.0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=bars.index).ewm(
        alpha=1.0 / period, adjust=False, min_periods=period).mean() / atr_.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def sma_slope(close: pd.Series, sma_period: int = 50, slope_window: int = 10) -> pd.Series:
    sma = close.rolling(sma_period, min_periods=sma_period).mean()
    return sma.rolling(slope_window, min_periods=slope_window).apply(_slope, raw=True)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - (100 / (1 + rs))


def distance_from_sma(close: pd.Series, sma_period: int = 200) -> pd.Series:
    sma = close.rolling(sma_period, min_periods=sma_period // 2).mean()
    return (close - sma) / sma.replace(0.0, np.nan)


def rate_of_change(close: pd.Series, period: int = 10) -> pd.Series:
    return close.pct_change(period)


# --------------------------------------------------------------------------
# Session-relative features (the futures-specific additions)
# --------------------------------------------------------------------------

def session_vwap(bars: pd.DataFrame) -> pd.Series:
    """Anchored VWAP that resets each calendar day.

    A clean session anchor needs a real session calendar; for feature purposes
    a daily reset on the bar timestamp is a good, look-ahead-free proxy.
    """
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    vol = bars["volume"].replace(0.0, 1e-9)
    day = pd.Index(bars.index).normalize()
    pv = (typical * vol).groupby(day).cumsum()
    cum_vol = vol.groupby(day).cumsum()
    return pv / cum_vol


def distance_from_vwap(bars: pd.DataFrame) -> pd.Series:
    vwap = session_vwap(bars)
    return (bars["close"] - vwap) / vwap.replace(0.0, np.nan)


def time_of_day_sin_cos(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """Cyclical encoding of intraday time so the model treats 23:59 and 00:01 as close."""
    minutes = index.hour * 60 + index.minute
    frac = minutes / (24 * 60)
    s = pd.Series(np.sin(2 * np.pi * frac), index=index)
    c = pd.Series(np.cos(2 * np.pi * frac), index=index)
    return s, c


# --------------------------------------------------------------------------
# Feature engineer
# --------------------------------------------------------------------------

class FeatureEngineer:
    """Builds the standardised HMM feature matrix from OHLCV bars."""

    HMM_FEATURES = [
        "ret_1", "ret_5", "ret_15",
        "rvol_20", "vol_ratio",
        "vol_norm", "vol_trend",
        "adx", "sma_slope",
        "rsi_z", "dist_sma", "dist_vwap",
        "roc_10", "roc_20",
        "natr", "tod_sin", "tod_cos",
    ]

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.zscore_window = int(cfg.get("zscore_window", 252))

    def compute_hmm_features(self, bars: pd.DataFrame) -> pd.DataFrame:
        """Return the standardised feature frame used to fit / query the HMM."""
        self._validate(bars)
        c, v = bars["close"], bars["volume"]
        idx = pd.DatetimeIndex(bars.index)
        tod_sin, tod_cos = time_of_day_sin_cos(idx)

        raw = pd.DataFrame(index=bars.index)
        raw["ret_1"] = log_returns(c, 1)
        raw["ret_5"] = log_returns(c, 5)
        raw["ret_15"] = log_returns(c, 15)
        raw["rvol_20"] = realized_volatility(c, 20)
        raw["vol_ratio"] = volatility_ratio(c, 5, 20)
        raw["vol_norm"] = normalized_volume(v, 50)
        raw["vol_trend"] = volume_trend(v, 10)
        raw["adx"] = adx(bars, 14)
        raw["sma_slope"] = sma_slope(c, 50, 10)
        raw["rsi_z"] = rolling_zscore(rsi(c, 14), self.zscore_window)
        raw["dist_sma"] = distance_from_sma(c, 200)
        raw["dist_vwap"] = distance_from_vwap(bars)
        raw["roc_10"] = rate_of_change(c, 10)
        raw["roc_20"] = rate_of_change(c, 20)
        raw["natr"] = normalized_atr(bars, 14)

        # Standardise everything except the already-cyclical time features.
        feats = pd.DataFrame(index=bars.index)
        for col in raw.columns:
            if col == "rsi_z":
                feats[col] = raw[col]
            else:
                feats[col] = rolling_zscore(raw[col], self.zscore_window)
        feats["tod_sin"] = tod_sin
        feats["tod_cos"] = tod_cos

        feats = feats[self.HMM_FEATURES]
        return feats.dropna()

    def compute_strategy_features(self, bars: pd.DataFrame) -> pd.DataFrame:
        """Un-standardised indicators the scalping strategies read directly."""
        self._validate(bars)
        c = bars["close"]
        out = pd.DataFrame(index=bars.index)
        out["close"] = c
        out["ema_9"] = c.ewm(span=9, adjust=False).mean()
        out["ema_21"] = c.ewm(span=21, adjust=False).mean()
        out["atr"] = atr(bars, 14)
        out["rsi"] = rsi(c, 14)
        out["adx"] = adx(bars, 14)
        out["vwap"] = session_vwap(bars)
        out["roc_5"] = rate_of_change(c, 5)
        return out

    @staticmethod
    def _validate(bars: pd.DataFrame) -> None:
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(bars.columns)
        if missing:
            raise ValueError(f"bars missing required columns: {sorted(missing)}")
        if not isinstance(bars.index, pd.DatetimeIndex):
            raise ValueError("bars must be indexed by a DatetimeIndex")
