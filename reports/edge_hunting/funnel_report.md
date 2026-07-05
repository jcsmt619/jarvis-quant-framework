# Funnel Report

- Total backtests run: 2697
- Positive OOS Sharpe: 1326 (49.2%)
- Cleared 0.5 OOS Sharpe: 384 (14.2%)
- Survived all six filters: 35 (1.30%)

## Survival Rate by Category
- MEAN_REVERSION: 2.5%
- COMPOSITE: 1.1%
- TREND: 1.0%
- PATTERN: 0.6%
- VOLATILITY: 0.6%
- VOLUME: 0.0%

## Survival Rate by Strategy Family
- dual_momentum: 20.7%
- percent_b_revert: 6.9%
- keltner_revert: 6.9%
- rsi_revert: 4.7%
- macd_rsi_confirm: 3.4%
- ultimate_oscillator_revert: 3.4%
- cci_revert: 1.7%
- donchian_breakout: 1.7%
- bollinger_revert: 1.7%
- pivot_bounce: 1.7%
- zscore_revert: 0.9%
- atr_breakout: 0.9%
- chaikin_money_flow: 0.0%
- aroon: 0.0%
- adx_trend: 0.0%
- force_index: 0.0%
- engulfing: 0.0%
- elder_ray: 0.0%
- connors_rsi_revert: 0.0%
- chaikin_oscillator: 0.0%
- chandelier_exit: 0.0%
- bollinger_breakout: 0.0%
- ichimoku: 0.0%
- ma_crossover: 0.0%
- linreg_slope: 0.0%
- kama: 0.0%
- macd: 0.0%
- obv_trend: 0.0%
- gap_fade: 0.0%
- hull_ma: 0.0%
- higher_highs_lower_lows: 0.0%
- roc_momentum: 0.0%
- parabolic_sar: 0.0%
- money_flow_index: 0.0%
- squeeze_breakout: 0.0%
- three_bar_reversal: 0.0%
- triple_screen: 0.0%
- stochastic_revert: 0.0%
- supertrend: 0.0%
- ts_momentum: 0.0%
- trix: 0.0%
- volatility_breakout: 0.0%
- turtle_breakout: 0.0%
- volume_surge: 0.0%
- vortex: 0.0%
- vwap_revert: 0.0%
- williams_r_revert: 0.0%

## Mean OOS Sharpe by Category
- MEAN_REVERSION: 0.14
- TREND: -0.05
- PATTERN: -0.08
- VOLUME: -0.15
- COMPOSITE: -0.16
- VOLATILITY: -0.21

## Failure Counts by Filter
- min_oos_sharpe: 1293
- max_drawdown: 1112
- oos_over_is_ratio: 145
- positive_in_sample: 84
- min_trade_count: 28

## Top Survivors
  asset                                  strategy_name       category  oos_sharpe  oos_max_drawdown  trade_count
   NVDA          dual_momentum__window60_rel_window126          TREND    0.977326         -0.270581           62
   AMZN          dual_momentum__window60_rel_window126          TREND    0.976734         -0.237468           59
   AAPL          dual_momentum__window60_rel_window126          TREND    0.945010         -0.227486           58
BTC-USD                 atr_breakout__window14_mult1.5     VOLATILITY    0.879694         -0.310694          138
    XLK percent_b_revert__window20_lower0.05_upper0.95 MEAN_REVERSION    0.839239         -0.083581          168
   AAPL         dual_momentum__window126_rel_window126          TREND    0.768342         -0.338995           30
    QQQ              cci_revert__window20_threshold150 MEAN_REVERSION    0.725119         -0.084144          136
   MSFT           keltner_revert__window20_atr_mult2.0 MEAN_REVERSION    0.714340         -0.073841          121
   MSFT         dual_momentum__window126_rel_window126          TREND    0.711087         -0.241950           49
    TLT    rsi_revert__window7_oversold25_overbought70 MEAN_REVERSION    0.695947         -0.070671          160
    EFA    rsi_revert__window7_oversold25_overbought70 MEAN_REVERSION    0.693469         -0.079595          165
   AMZN           keltner_revert__window20_atr_mult2.0 MEAN_REVERSION    0.661421         -0.172112          126
    XLF         dual_momentum__window126_rel_window126          TREND    0.656790         -0.224326           36
    XLF          dual_momentum__window60_rel_window126          TREND    0.654104         -0.133895           54
    EEM   rsi_revert__window14_oversold30_overbought70 MEAN_REVERSION    0.651540         -0.099146           52
    TLT            pivot_bounce__window5_tolerance0.01        PATTERN    0.638751         -0.117840          396
    SPY          dual_momentum__window60_rel_window126          TREND    0.637223         -0.159890           66
    EFA    rsi_revert__window7_oversold30_overbought70 MEAN_REVERSION    0.634829         -0.086199          203
ETH-USD                    donchian_breakout__window55          TREND    0.631664         -0.175789           56
   MSFT percent_b_revert__window20_lower0.05_upper0.95 MEAN_REVERSION    0.627186         -0.189378          162