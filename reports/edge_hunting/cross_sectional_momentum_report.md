# Cross-Sectional Momentum Report

lookback  full_sharpe  full_max_drawdown  in_sample_sharpe  oos_sharpe  oos_max_drawdown  turnover  trade_count
      3m     0.291244          -0.319342          0.361352    0.124139         -0.306943     930.0          465
      6m     0.311642          -0.360407          0.493895   -0.152586         -0.371450     918.0          459
    12_1     0.554040          -0.400483          0.735298    0.114848         -0.358894     894.0          447

## Comparison vs Single-Asset Momentum (from main sweep)
- Cross-sectional mean OOS Sharpe: 0.03
- Single-asset momentum mean OOS Sharpe: 0.10
- Cross-sectional ranking does not beat single-asset momentum on mean OOS Sharpe (reported as-is, not tuned to look good).

### Drawdowns (as-is)
- Cross-sectional worst OOS max drawdown: -37.14%
- Single-asset momentum worst OOS max drawdown: -93.38%