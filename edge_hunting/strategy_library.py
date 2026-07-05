"""
edge_hunting/strategy_library.py
==================================
Strategy family functions for the sweep engine.

CONTRACT for every function in this module:
  def strategy_xxx(df: pd.DataFrame, params: dict) -> pd.Series
    - `df` has columns Open, High, Low, Close, Volume, DatetimeIndex ascending.
    - Returns a signal series aligned to df.index, values in {-1, 0, 1}.
    - The signal at index t is computed using ONLY df.loc[:t] (data at or
      before t) -- no negative shifts, no center=True, no peeking.
    - This function does NOT shift the signal forward. The caller
      (backtest_engine.run_backtest) is solely responsible for shifting
      signal -> position by one bar before multiplying by next-day return.
      This centralizes the anti-lookahead boundary in one place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from edge_hunting import indicators as ind


def _sign_signal(cond_long: pd.Series, cond_short: pd.Series) -> pd.Series:
    sig = pd.Series(0, index=cond_long.index, dtype=float)
    sig[cond_long.fillna(False)] = 1
    sig[cond_short.fillna(False)] = -1
    return sig


# ---------------------------------------------------------------------------
# TREND
# ---------------------------------------------------------------------------
def strategy_ma_crossover(df, params):
    fast = ind.sma(df["Close"], params["fast"])
    slow = ind.sma(df["Close"], params["slow"])
    return _sign_signal(fast > slow, fast < slow)


def strategy_ts_momentum(df, params):
    ret = ind.roc(df["Close"], params["window"])
    return _sign_signal(ret > 0, ret < 0)


def strategy_roc_momentum(df, params):
    r = ind.roc(df["Close"], params["window"])
    thresh = params.get("threshold", 0.0)
    return _sign_signal(r > thresh, r < -thresh)


def strategy_macd(df, params):
    macd_line, signal_line, _ = ind.macd(df["Close"], params["fast"], params["slow"], params["signal"])
    return _sign_signal(macd_line > signal_line, macd_line < signal_line)


def strategy_donchian_breakout(df, params):
    upper, _, lower = ind.donchian_channels(df["High"], df["Low"], params["window"])
    long_cond = df["Close"] > upper.shift(1)
    short_cond = df["Close"] < lower.shift(1)
    return _sign_signal(long_cond, short_cond)


def strategy_bollinger_breakout(df, params):
    _, upper, lower = ind.bollinger_bands(df["Close"], params["window"], params.get("num_std", 2.0))
    return _sign_signal(df["Close"] > upper, df["Close"] < lower)


def strategy_supertrend(df, params):
    trend, _, _ = ind.supertrend(df["High"], df["Low"], df["Close"], params["window"], params["mult"])
    return trend.astype(float)


def strategy_parabolic_sar(df, params):
    sar = ind.parabolic_sar(df["High"], df["Low"], df["Close"], params.get("step", 0.02), params.get("max_step", 0.2))
    return _sign_signal(df["Close"] > sar, df["Close"] < sar)


def strategy_adx_trend(df, params):
    adx_val, plus_di, minus_di = ind.adx(df["High"], df["Low"], df["Close"], params["window"])
    thresh = params.get("adx_threshold", 20)
    long_cond = (adx_val > thresh) & (plus_di > minus_di)
    short_cond = (adx_val > thresh) & (minus_di > plus_di)
    return _sign_signal(long_cond, short_cond)


def strategy_ichimoku(df, params):
    tenkan, kijun, span_a, span_b = ind.ichimoku(df["High"], df["Low"], df["Close"],
                                                  params.get("tenkan", 9), params.get("kijun", 26),
                                                  params.get("senkou_b", 52))
    cloud_top = pd.concat([span_a, span_b], axis=1).max(axis=1)
    cloud_bottom = pd.concat([span_a, span_b], axis=1).min(axis=1)
    long_cond = (tenkan > kijun) & (df["Close"] > cloud_top)
    short_cond = (tenkan < kijun) & (df["Close"] < cloud_bottom)
    return _sign_signal(long_cond, short_cond)


def strategy_linreg_slope(df, params):
    slope = ind.linreg_slope(df["Close"], params["window"])
    return _sign_signal(slope > 0, slope < 0)


def strategy_aroon(df, params):
    up, down = ind.aroon(df["High"], df["Low"], params["window"])
    return _sign_signal(up > down, down > up)


def strategy_vortex(df, params):
    vi_plus, vi_minus = ind.vortex(df["High"], df["Low"], df["Close"], params["window"])
    return _sign_signal(vi_plus > vi_minus, vi_minus > vi_plus)


def strategy_trix(df, params):
    t = ind.trix(df["Close"], params["window"])
    return _sign_signal(t > 0, t < 0)


def strategy_hull_ma(df, params):
    h = ind.hull_ma(df["Close"], params["window"])
    return _sign_signal(df["Close"] > h, df["Close"] < h)


def strategy_kama(df, params):
    k = ind.kama(df["Close"], params.get("window", 10), params.get("fast", 2), params.get("slow", 30))
    return _sign_signal(df["Close"] > k, df["Close"] < k)


def strategy_turtle_breakout(df, params):
    upper, _, lower = ind.donchian_channels(df["High"], df["Low"], params["entry_window"])
    exit_upper, _, exit_lower = ind.donchian_channels(df["High"], df["Low"], params["exit_window"])
    long_entry = df["Close"] > upper.shift(1)
    short_entry = df["Close"] < lower.shift(1)
    sig = _sign_signal(long_entry, short_entry)
    return sig.replace(0, np.nan).ffill().fillna(0)


def strategy_dual_momentum(df, params):
    abs_mom = ind.roc(df["Close"], params["window"])
    rel_mom = ind.roc(df["Close"], params.get("rel_window", params["window"]))
    long_cond = (abs_mom > 0) & (rel_mom > 0)
    return _sign_signal(long_cond, pd.Series(False, index=df.index))


def strategy_elder_ray(df, params):
    bull, bear = ind.elder_ray(df["High"], df["Low"], df["Close"], params["window"])
    return _sign_signal(bull > 0, bear < 0)


# ---------------------------------------------------------------------------
# MEAN REVERSION
# ---------------------------------------------------------------------------
def strategy_rsi_revert(df, params):
    r = ind.rsi(df["Close"], params["window"])
    return _sign_signal(r < params.get("oversold", 30), r > params.get("overbought", 70))


def strategy_bollinger_revert(df, params):
    _, upper, lower = ind.bollinger_bands(df["Close"], params["window"], params.get("num_std", 2.0))
    return _sign_signal(df["Close"] < lower, df["Close"] > upper)


def strategy_zscore_revert(df, params):
    z = ind.zscore(df["Close"], params["window"])
    thresh = params.get("threshold", 1.5)
    return _sign_signal(z < -thresh, z > thresh)


def strategy_stochastic_revert(df, params):
    k, d = ind.stochastic(df["High"], df["Low"], df["Close"], params["window"], params.get("smooth", 3))
    return _sign_signal(k < params.get("oversold", 20), k > params.get("overbought", 80))


def strategy_cci_revert(df, params):
    c = ind.cci(df["High"], df["Low"], df["Close"], params["window"])
    thresh = params.get("threshold", 100)
    return _sign_signal(c < -thresh, c > thresh)


def strategy_williams_r_revert(df, params):
    w = ind.williams_r(df["High"], df["Low"], df["Close"], params["window"])
    return _sign_signal(w < params.get("oversold", -80), w > params.get("overbought", -20))


def strategy_keltner_revert(df, params):
    _, upper, lower = ind.keltner_channels(df["High"], df["Low"], df["Close"], params["window"], params.get("atr_mult", 2.0))
    return _sign_signal(df["Close"] < lower, df["Close"] > upper)


def strategy_vwap_revert(df, params):
    v = ind.vwap(df["High"], df["Low"], df["Close"], df["Volume"], params["window"])
    dev = (df["Close"] - v) / v
    thresh = params.get("threshold", 0.02)
    return _sign_signal(dev < -thresh, dev > thresh)


def strategy_percent_b_revert(df, params):
    pb = ind.percent_b(df["Close"], params["window"], params.get("num_std", 2.0))
    return _sign_signal(pb < params.get("lower", 0.05), pb > params.get("upper", 0.95))


def strategy_connors_rsi_revert(df, params):
    c = ind.connors_rsi(df["Close"], params.get("rsi_window", 3), params.get("streak_window", 2),
                         params.get("rank_window", 100))
    return _sign_signal(c < params.get("oversold", 10), c > params.get("overbought", 90))


def strategy_ultimate_oscillator_revert(df, params):
    u = ind.ultimate_oscillator(df["High"], df["Low"], df["Close"],
                                 params.get("w1", 7), params.get("w2", 14), params.get("w3", 28))
    return _sign_signal(u < params.get("oversold", 30), u > params.get("overbought", 70))


def strategy_gap_fade(df, params):
    prev_close = df["Close"].shift(1)
    gap = (df["Open"] - prev_close) / prev_close
    thresh = params.get("threshold", 0.02)
    return _sign_signal(gap < -thresh, gap > thresh)


# ---------------------------------------------------------------------------
# VOLUME
# ---------------------------------------------------------------------------
def strategy_obv_trend(df, params):
    o = ind.obv(df["Close"], df["Volume"])
    o_ma = ind.sma(o, params["window"])
    return _sign_signal(o > o_ma, o < o_ma)


def strategy_chaikin_money_flow(df, params):
    cmf = ind.chaikin_money_flow(df["High"], df["Low"], df["Close"], df["Volume"], params["window"])
    thresh = params.get("threshold", 0.0)
    return _sign_signal(cmf > thresh, cmf < -thresh)


def strategy_money_flow_index(df, params):
    mfi = ind.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], params["window"])
    return _sign_signal(mfi < params.get("oversold", 20), mfi > params.get("overbought", 80))


def strategy_volume_surge(df, params):
    vol_ma = ind.sma(df["Volume"], params["window"])
    surge = df["Volume"] > vol_ma * params.get("mult", 2.0)
    ret = df["Close"].pct_change()
    return _sign_signal(surge & (ret > 0), surge & (ret < 0))


def strategy_force_index(df, params):
    f = ind.force_index(df["Close"], df["Volume"], params["window"])
    return _sign_signal(f > 0, f < 0)


def strategy_chaikin_oscillator(df, params):
    c = ind.chaikin_oscillator(df["High"], df["Low"], df["Close"], df["Volume"],
                                params.get("fast", 3), params.get("slow", 10))
    return _sign_signal(c > 0, c < 0)


# ---------------------------------------------------------------------------
# VOLATILITY
# ---------------------------------------------------------------------------
def strategy_atr_breakout(df, params):
    a = ind.atr(df["High"], df["Low"], df["Close"], params["window"])
    ma = ind.sma(df["Close"], params["window"])
    long_cond = df["Close"] > ma + params.get("mult", 1.5) * a
    short_cond = df["Close"] < ma - params.get("mult", 1.5) * a
    return _sign_signal(long_cond, short_cond)


def strategy_volatility_breakout(df, params):
    ret_std = df["Close"].pct_change().rolling(params["window"], min_periods=params["window"]).std()
    ret = df["Close"].pct_change()
    thresh = ret_std * params.get("mult", 2.0)
    return _sign_signal(ret > thresh, ret < -thresh)


def strategy_squeeze_breakout(df, params):
    _, bb_upper, bb_lower = ind.bollinger_bands(df["Close"], params["window"], params.get("num_std", 2.0))
    _, kc_upper, kc_lower = ind.keltner_channels(df["High"], df["Low"], df["Close"], params["window"], params.get("atr_mult", 1.5))
    squeeze = (bb_upper < kc_upper) & (bb_lower > kc_lower)
    was_squeezed = squeeze.shift(1).fillna(False)
    breakout_up = was_squeezed & (df["Close"] > bb_upper)
    breakout_down = was_squeezed & (df["Close"] < bb_lower)
    return _sign_signal(breakout_up, breakout_down)


# ---------------------------------------------------------------------------
# PATTERN
# ---------------------------------------------------------------------------
def strategy_engulfing(df, params):
    o, c = df["Open"], df["Close"]
    prev_o, prev_c = o.shift(1), c.shift(1)
    bullish = (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)
    bearish = (c < o) & (prev_c > prev_o) & (c < prev_o) & (o > prev_c)
    return _sign_signal(bullish, bearish)


def strategy_three_bar_reversal(df, params):
    c = df["Close"]
    down3 = (c.shift(2) > c.shift(1)) & (c.shift(1) > c.shift(0).shift(1)) & (c.shift(1) > c)
    up_reversal = (c.diff() > 0) & (c.shift(1).diff() < 0) & (c.shift(2).diff() < 0)
    down_reversal = (c.diff() < 0) & (c.shift(1).diff() > 0) & (c.shift(2).diff() > 0)
    return _sign_signal(up_reversal, down_reversal)


def strategy_higher_highs_lower_lows(df, params):
    window = params["window"]
    hh = df["High"] > df["High"].rolling(window, min_periods=window).max().shift(1)
    ll = df["Low"] < df["Low"].rolling(window, min_periods=window).min().shift(1)
    return _sign_signal(hh, ll)


def strategy_pivot_bounce(df, params):
    window = params.get("window", 5)
    pivot_high = df["High"].rolling(window, min_periods=window).max().shift(1)
    pivot_low = df["Low"].rolling(window, min_periods=window).min().shift(1)
    near_low = df["Close"] <= pivot_low * (1 + params.get("tolerance", 0.01))
    near_high = df["Close"] >= pivot_high * (1 - params.get("tolerance", 0.01))
    return _sign_signal(near_low, near_high)


# ---------------------------------------------------------------------------
# COMPOSITE
# ---------------------------------------------------------------------------
def strategy_macd_rsi_confirm(df, params):
    macd_line, signal_line, _ = ind.macd(df["Close"], params.get("fast", 12), params.get("slow", 26), params.get("signal", 9))
    r = ind.rsi(df["Close"], params.get("rsi_window", 14))
    long_cond = (macd_line > signal_line) & (r > 50)
    short_cond = (macd_line < signal_line) & (r < 50)
    return _sign_signal(long_cond, short_cond)


def strategy_triple_screen(df, params):
    trend_ma = ind.ema(df["Close"], params.get("trend_window", 50))
    r = ind.rsi(df["Close"], params.get("rsi_window", 14))
    long_cond = (df["Close"] > trend_ma) & (r < params.get("oversold", 40))
    short_cond = (df["Close"] < trend_ma) & (r > params.get("overbought", 60))
    return _sign_signal(long_cond, short_cond)


def strategy_chandelier_exit(df, params):
    window = params.get("window", 22)
    mult = params.get("mult", 3.0)
    a = ind.atr(df["High"], df["Low"], df["Close"], window)
    highest = df["High"].rolling(window, min_periods=window).max()
    lowest = df["Low"].rolling(window, min_periods=window).min()
    long_stop = highest - mult * a
    short_stop = lowest + mult * a
    trend_ma = ind.ema(df["Close"], params.get("trend_window", 50))
    long_cond = (df["Close"] > trend_ma) & (df["Close"] > long_stop)
    short_cond = (df["Close"] < trend_ma) & (df["Close"] < short_stop)
    return _sign_signal(long_cond, short_cond)


# ---------------------------------------------------------------------------
# Registry: family name -> (function, category, description)
# ---------------------------------------------------------------------------
STRATEGY_REGISTRY = {
    # TREND
    "ma_crossover": (strategy_ma_crossover, "TREND", "Fast/slow SMA crossover"),
    "ts_momentum": (strategy_ts_momentum, "TREND", "Time-series momentum sign"),
    "roc_momentum": (strategy_roc_momentum, "TREND", "Rate-of-change momentum with threshold"),
    "macd": (strategy_macd, "TREND", "MACD line vs signal line"),
    "donchian_breakout": (strategy_donchian_breakout, "TREND", "Donchian channel breakout"),
    "bollinger_breakout": (strategy_bollinger_breakout, "TREND", "Bollinger band breakout"),
    "supertrend": (strategy_supertrend, "TREND", "Supertrend ATR trailing bands"),
    "parabolic_sar": (strategy_parabolic_sar, "TREND", "Parabolic SAR trend flip"),
    "adx_trend": (strategy_adx_trend, "TREND", "ADX-confirmed directional trend"),
    "ichimoku": (strategy_ichimoku, "TREND", "Ichimoku cloud + tenkan/kijun cross"),
    "linreg_slope": (strategy_linreg_slope, "TREND", "Rolling linear regression slope sign"),
    "aroon": (strategy_aroon, "TREND", "Aroon up/down cross"),
    "vortex": (strategy_vortex, "TREND", "Vortex indicator VI+/VI- cross"),
    "trix": (strategy_trix, "TREND", "TRIX zero-line cross"),
    "hull_ma": (strategy_hull_ma, "TREND", "Hull moving average trend"),
    "kama": (strategy_kama, "TREND", "Kaufman adaptive moving average trend"),
    "turtle_breakout": (strategy_turtle_breakout, "TREND", "Turtle-style dual-window breakout"),
    "dual_momentum": (strategy_dual_momentum, "TREND", "Absolute + relative dual momentum"),
    "elder_ray": (strategy_elder_ray, "TREND", "Elder Ray bull/bear power"),
    # MEAN REVERSION
    "rsi_revert": (strategy_rsi_revert, "MEAN_REVERSION", "RSI oversold/overbought reversion"),
    "bollinger_revert": (strategy_bollinger_revert, "MEAN_REVERSION", "Bollinger band mean reversion"),
    "zscore_revert": (strategy_zscore_revert, "MEAN_REVERSION", "Rolling z-score reversion"),
    "stochastic_revert": (strategy_stochastic_revert, "MEAN_REVERSION", "Stochastic oscillator reversion"),
    "cci_revert": (strategy_cci_revert, "MEAN_REVERSION", "CCI extreme reversion"),
    "williams_r_revert": (strategy_williams_r_revert, "MEAN_REVERSION", "Williams %R reversion"),
    "keltner_revert": (strategy_keltner_revert, "MEAN_REVERSION", "Keltner channel reversion"),
    "vwap_revert": (strategy_vwap_revert, "MEAN_REVERSION", "VWAP deviation reversion"),
    "percent_b_revert": (strategy_percent_b_revert, "MEAN_REVERSION", "Bollinger %B extreme reversion"),
    "connors_rsi_revert": (strategy_connors_rsi_revert, "MEAN_REVERSION", "Connors RSI composite reversion"),
    "ultimate_oscillator_revert": (strategy_ultimate_oscillator_revert, "MEAN_REVERSION", "Ultimate Oscillator reversion"),
    "gap_fade": (strategy_gap_fade, "MEAN_REVERSION", "Overnight gap fade"),
    # VOLUME
    "obv_trend": (strategy_obv_trend, "VOLUME", "On-balance volume trend"),
    "chaikin_money_flow": (strategy_chaikin_money_flow, "VOLUME", "Chaikin Money Flow sign"),
    "money_flow_index": (strategy_money_flow_index, "VOLUME", "Money Flow Index reversion"),
    "volume_surge": (strategy_volume_surge, "VOLUME", "Volume surge with directional confirmation"),
    "force_index": (strategy_force_index, "VOLUME", "Force Index sign"),
    "chaikin_oscillator": (strategy_chaikin_oscillator, "VOLUME", "Chaikin Oscillator sign"),
    # VOLATILITY
    "atr_breakout": (strategy_atr_breakout, "VOLATILITY", "ATR-band breakout"),
    "volatility_breakout": (strategy_volatility_breakout, "VOLATILITY", "Rolling-vol-normalized return breakout"),
    "squeeze_breakout": (strategy_squeeze_breakout, "VOLATILITY", "Bollinger/Keltner squeeze breakout"),
    # PATTERN
    "engulfing": (strategy_engulfing, "PATTERN", "Bullish/bearish engulfing candle"),
    "three_bar_reversal": (strategy_three_bar_reversal, "PATTERN", "Three-bar reversal pattern"),
    "higher_highs_lower_lows": (strategy_higher_highs_lower_lows, "PATTERN", "Rolling higher-high/lower-low breakout"),
    "pivot_bounce": (strategy_pivot_bounce, "PATTERN", "Pivot high/low bounce"),
    # COMPOSITE
    "macd_rsi_confirm": (strategy_macd_rsi_confirm, "COMPOSITE", "MACD direction + RSI confirmation"),
    "triple_screen": (strategy_triple_screen, "COMPOSITE", "Trend filter + oscillator entry (Elder triple screen)"),
    "chandelier_exit": (strategy_chandelier_exit, "COMPOSITE", "Trend filter + ATR chandelier trailing stop system"),
}
