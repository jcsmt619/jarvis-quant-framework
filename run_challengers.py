import sys

sys.path.append(r'C:/Users/James/jarvis-quant-framework')
from backtest_harness import MultiAssetBacktest

variants = [
    ('strategies.challenger_variants.ChallengerFastRSI', {}),
    ('strategies.challenger_variants.ChallengerMomentum', {}),
    ('strategies.challenger_variants.ChallengerVolatility', {}),
]

for strategy_class, params in variants:
    result = MultiAssetBacktest(['SPY', 'BTC-USD', 'TLT'], 'raw', strategy_class=strategy_class, params=params).run()
    print(strategy_class, result)
