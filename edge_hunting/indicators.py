"""
edge_hunting/indicators.py
===========================
Causal-only technical indicator primitives for the strategy sweep engine.

Every function here uses ONLY trailing/rolling windows (`.rolling()`,
`.ewm()`, `.shift(positive)`) -- never `center=True`, never a negative
shift, never any operation that reads a future bar. The value at index t
must be computable using only data at or before t.

These are indicator VALUES, not trading signals. `strategy_library.py`
turns these into {-1, 0, 1} signals. The anti-lookahead SHIFT from
signal-day to traded-day happens centrally in `backtest_engine.py`, not
here and not in the strategy functions -- indicators/signals here are
"as of day t", and the backtest engine is responsible for only ever
trading day t's signal starting on day t+1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def hull_ma(series: pd.Series, window: int) -> pd.Series:
    half = max(1, window // 2)
    sqrt_w = max(1, int(np.sqrt(window)))
    wma_half = _wma(series, half)
    wma_full = _wma(series, window)
    raw = 2 * wma_half - wma_full
    return _wma(raw, sqrt_w)


def _wma(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1)

    def _f(x):
        if len(x) < window:
            return np.nan
        return np.dot(x, weights) / weights.sum()

    return series.rolling(window, min_periods=window).apply(_f, raw=True)


def kama(series: pd.Series, window: int = 10, fast: int = 2, slow: int = 30) -> pd.Series:
    change = series.diff(window).abs()
    volatility = series.diff().abs().rolling(window, min_periods=window).sum()
    er = (change / volatility.replace(0, np.nan)).fillna(0)
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

    out = pd.Series(index=series.index, dtype=float)
    valid_start = series.first_valid_index()
    if valid_start is None:
        return out
    started = False
    prev = np.nan
    for idx in series.index:
        val = series.loc[idx]
        sc_val = sc.loc[idx] if idx in sc.index else np.nan
        if not started:
            if not np.isnan(val):
                prev = val
                started = True
            out.loc[idx] = prev
            continue
        if np.isnan(sc_val):
            out.loc[idx] = prev
            continue
        prev = prev + sc_val * (val - prev)
        out.loc[idx] = prev
    return out


def roc(series: pd.Series, window: int) -> pd.Series:
    return series.pct_change(window)


def momentum(series: pd.Series, window: int) -> pd.Series:
    return series.diff(window)


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def connors_rsi(close: pd.Series, rsi_window: int = 3, streak_window: int = 2,
                 rank_window: int = 100) -> pd.Series:
    r1 = rsi(close, rsi_window)

    diff = close.diff()
    sign = np.sign(diff).fillna(0)
    streak = pd.Series(0.0, index=close.index)
    cur = 0
    for i, idx in enumerate(close.index):
        s = sign.iloc[i]
        if s > 0:
            cur = cur + 1 if cur >= 0 else 1
        elif s < 0:
            cur = cur - 1 if cur <= 0 else -1
        else:
            cur = 0
        streak.iloc[i] = cur
    r2 = rsi(streak, streak_window)

    pct_rank = close.pct_change().rolling(rank_window, min_periods=rank_window).apply(
        lambda x: (pd.Series(x).rank(pct=True).iloc[-1]) * 100, raw=False
    )
    return (r1 + r2 + pct_rank.fillna(50)) / 3.0


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = sma(series, window)
    std = series.rolling(window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower


def percent_b(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.Series:
    mid, upper, lower = bollinger_bands(series, window, num_std)
    return (series - lower) / (upper - lower).replace(0, np.nan)


def keltner_channels(high, low, close, window: int = 20, atr_mult: float = 2.0):
    mid = ema(close, window)
    a = atr(high, low, close, window)
    upper = mid + atr_mult * a
    lower = mid - atr_mult * a
    return mid, upper, lower


def donchian_channels(high: pd.Series, low: pd.Series, window: int = 20):
    upper = high.rolling(window, min_periods=window).max()
    lower = low.rolling(window, min_periods=window).min()
    mid = (upper + lower) / 2.0
    return upper, mid, lower


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    m = sma(series, window)
    s = series.rolling(window, min_periods=window).std()
    return (series - m) / s.replace(0, np.nan)


def stochastic(high, low, close, window: int = 14, smooth: int = 3):
    lowest = low.rolling(window, min_periods=window).min()
    highest = high.rolling(window, min_periods=window).max()
    pct_k = 100 * (close - lowest) / (highest - lowest).replace(0, np.nan)
    pct_d = pct_k.rolling(smooth, min_periods=smooth).mean()
    return pct_k, pct_d


def cci(high, low, close, window: int = 20) -> pd.Series:
    tp = (high + low + close) / 3.0
    sma_tp = sma(tp, window)
    mad = tp.rolling(window, min_periods=window).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))


def williams_r(high, low, close, window: int = 14) -> pd.Series:
    highest = high.rolling(window, min_periods=window).max()
    lowest = low.rolling(window, min_periods=window).min()
    return -100 * (highest - close) / (highest - lowest).replace(0, np.nan)


def ultimate_oscillator(high, low, close, w1=7, w2=14, w3=28) -> pd.Series:
    prev_close = close.shift(1)
    bp = close - pd.concat([low, prev_close], axis=1).min(axis=1)
    tr = pd.concat([high, prev_close], axis=1).max(axis=1) - pd.concat(
        [low, prev_close], axis=1).min(axis=1)

    def _avg(w):
        return bp.rolling(w, min_periods=w).sum() / tr.rolling(w, min_periods=w).sum().replace(0, np.nan)

    a1, a2, a3 = _avg(w1), _avg(w2), _avg(w3)
    return 100 * (4 * a1 + 2 * a2 + a3) / 7.0


def vwap(high, low, close, volume, window: int = 20) -> pd.Series:
    tp = (high + low + close) / 3.0
    pv = tp * volume
    return pv.rolling(window, min_periods=window).sum() / volume.rolling(window, min_periods=window).sum()


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def chaikin_money_flow(high, low, close, volume, window: int = 20) -> pd.Series:
    mf_mult = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    mf_vol = mf_mult * volume
    return mf_vol.rolling(window, min_periods=window).sum() / volume.rolling(window, min_periods=window).sum()


def money_flow_index(high, low, close, volume, window: int = 14) -> pd.Series:
    tp = (high + low + close) / 3.0
    raw_mf = tp * volume
    pos_flow = raw_mf.where(tp.diff() > 0, 0.0)
    neg_flow = raw_mf.where(tp.diff() < 0, 0.0)
    pos_sum = pos_flow.rolling(window, min_periods=window).sum()
    neg_sum = neg_flow.rolling(window, min_periods=window).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def force_index(close, volume, window: int = 13) -> pd.Series:
    raw = close.diff() * volume
    return ema(raw, window)


def chaikin_oscillator(high, low, close, volume, fast=3, slow=10) -> pd.Series:
    adl_mult = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
    adl = (adl_mult * volume).cumsum()
    return ema(adl, fast) - ema(adl, slow)


def adx(high, low, close, window: int = 14):
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = atr(high, low, close, window) * window  # unsmoothed proxy sum via ewm scaling
    atr_val = atr(high, low, close, window)
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, min_periods=window, adjust=False).mean() / atr_val.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, min_periods=window, adjust=False).mean() / atr_val.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    return adx_val, plus_di, minus_di


def aroon(high, low, window: int = 25):
    def _up(x):
        return 100 * (window - (window - 1 - np.argmax(x[::-1]))) / window

    def _down(x):
        return 100 * (window - (window - 1 - np.argmin(x[::-1]))) / window

    aroon_up = high.rolling(window + 1, min_periods=window + 1).apply(_up, raw=True)
    aroon_down = low.rolling(window + 1, min_periods=window + 1).apply(_down, raw=True)
    return aroon_up, aroon_down


def vortex(high, low, close, window: int = 14):
    prev_close = close.shift(1)
    prev_low = low.shift(1)
    prev_high = high.shift(1)
    vm_plus = (high - prev_low).abs()
    vm_minus = (low - prev_high).abs()
    tr = pd.concat([
        high - low, (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    vi_plus = vm_plus.rolling(window, min_periods=window).sum() / tr.rolling(window, min_periods=window).sum()
    vi_minus = vm_minus.rolling(window, min_periods=window).sum() / tr.rolling(window, min_periods=window).sum()
    return vi_plus, vi_minus


def trix(series: pd.Series, window: int = 15) -> pd.Series:
    e1 = ema(series, window)
    e2 = ema(e1, window)
    e3 = ema(e2, window)
    return 100 * e3.pct_change()


def parabolic_sar(high, low, close, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    """Simple causal implementation -- each bar's SAR uses only prior bars."""
    n = len(close)
    sar = np.full(n, np.nan)
    if n == 0:
        return pd.Series(sar, index=close.index)

    trend_up = True
    af = step
    ep = high.iloc[0]
    sar[0] = low.iloc[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend_up:
            cur_sar = prev_sar + af * (ep - prev_sar)
            cur_sar = min(cur_sar, low.iloc[i - 1], low.iloc[i - 2] if i >= 2 else low.iloc[i - 1])
            if low.iloc[i] < cur_sar:
                trend_up = False
                cur_sar = ep
                ep = low.iloc[i]
                af = step
            else:
                if high.iloc[i] > ep:
                    ep = high.iloc[i]
                    af = min(af + step, max_step)
        else:
            cur_sar = prev_sar + af * (ep - prev_sar)
            cur_sar = max(cur_sar, high.iloc[i - 1], high.iloc[i - 2] if i >= 2 else high.iloc[i - 1])
            if high.iloc[i] > cur_sar:
                trend_up = True
                cur_sar = ep
                ep = high.iloc[i]
                af = step
            else:
                if low.iloc[i] < ep:
                    ep = low.iloc[i]
                    af = min(af + step, max_step)
        sar[i] = cur_sar

    return pd.Series(sar, index=close.index)


def supertrend(high, low, close, window: int = 10, mult: float = 3.0):
    a = atr(high, low, close, window)
    hl2 = (high + low) / 2.0
    upper_basic = hl2 + mult * a
    lower_basic = hl2 - mult * a

    n = len(close)
    final_upper = upper_basic.copy()
    final_lower = lower_basic.copy()
    trend = pd.Series(1, index=close.index)

    for i in range(1, n):
        if close.iloc[i - 1] > final_upper.iloc[i - 1]:
            final_upper.iloc[i] = max(upper_basic.iloc[i], final_upper.iloc[i - 1]) \
                if close.iloc[i] > final_upper.iloc[i - 1] else upper_basic.iloc[i]
        else:
            final_upper.iloc[i] = min(upper_basic.iloc[i], final_upper.iloc[i - 1])

        if close.iloc[i - 1] < final_lower.iloc[i - 1]:
            final_lower.iloc[i] = min(lower_basic.iloc[i], final_lower.iloc[i - 1]) \
                if close.iloc[i] < final_lower.iloc[i - 1] else lower_basic.iloc[i]
        else:
            final_lower.iloc[i] = max(lower_basic.iloc[i], final_lower.iloc[i - 1])

        if close.iloc[i] > final_upper.iloc[i]:
            trend.iloc[i] = 1
        elif close.iloc[i] < final_lower.iloc[i]:
            trend.iloc[i] = -1
        else:
            trend.iloc[i] = trend.iloc[i - 1]

    return trend, final_upper, final_lower


def linreg_slope(series: pd.Series, window: int = 20) -> pd.Series:
    x = np.arange(window)

    def _f(y):
        if np.any(np.isnan(y)):
            return np.nan
        slope = np.polyfit(x, y, 1)[0]
        return slope

    return series.rolling(window, min_periods=window).apply(_f, raw=True)


def ichimoku(high, low, close, tenkan: int = 9, kijun: int = 26, senkou_b: int = 52):
    tenkan_sen = (high.rolling(tenkan, min_periods=tenkan).max() +
                  low.rolling(tenkan, min_periods=tenkan).min()) / 2.0
    kijun_sen = (high.rolling(kijun, min_periods=kijun).max() +
                 low.rolling(kijun, min_periods=kijun).min()) / 2.0
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2.0)  # NOTE: no forward shift applied
    senkou_span_b = ((high.rolling(senkou_b, min_periods=senkou_b).max() +
                       low.rolling(senkou_b, min_periods=senkou_b).min()) / 2.0)
    return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b


def elder_ray(high, low, close, window: int = 13):
    ema_val = ema(close, window)
    bull_power = high - ema_val
    bear_power = low - ema_val
    return bull_power, bear_power
