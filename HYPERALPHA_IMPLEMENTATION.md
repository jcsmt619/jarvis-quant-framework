# Hyper-Alpha Instructions Implementation Summary

**Status**: ✓ CREATED & READY FOR INTEGRATION  
**Date**: 2026-07-02  
**Framework**: Jarvis Quantitative Research Framework

---

## What Was Created

### 1. **Hyper-Alpha Instructions File**
📍 Location: `c:\Users\James\AppData\Roaming\Code\User\prompts\jarvis.hyper-alpha.instructions.md`

**Contents:**
- Comprehensive framework for high-velocity, high-beta asset trading
- Three core pillars: Asset Universe (crypto/leveraged ETFs), Kelly Criterion sizing, ATR trailing circuits
- Integration with tri-agent optimizer (new HyperAlpha variants)
- CRO validation criteria for aggressive strategies
- Code templates and file structure guidelines

**How It Works:**
- Instructions file will automatically apply to any prompt mentioning hyper-alpha strategies
- Guides strategy creation toward high-beta crypto pairs (BTC, ETH, SOL) and leveraged ETFs (TQQQ, SOXL)
- Enforces Kelly Criterion with 50% conservative fraction and instant regime drift closure
- Requires ATR-based trailing stops with automatic scaling at 4+ ATR profit levels

---

### 2. **Kelly Criterion Sizer Module**
📍 Location: `C:\Users\James\jarvis-quant-framework\utils\kelly_criterion.py`

**Key Features:**
- ✓ Dynamic position sizing based on rolling 100-trade win rate and edge ratios
- ✓ Regime drift detection (closes position if win rate drops below 40%)
- ✓ Conservative Kelly (50% of full Kelly) with 5x leverage cap
- ✓ Edge ratio validation (minimum 1.5x win/loss ratio required)
- ✓ JSON logging of regime switches for analysis

**Usage in Strategy:**
```python
from utils.kelly_criterion import KellyCriterionSizer, TradeRecord

sizer = KellyCriterionSizer(kelly_fraction=0.5)

# After each trade closes:
trade = TradeRecord(
    exit_date=datetime.now(),
    entry_price=100.0,
    exit_price=102.0,
    pnl=250.0,
    pnl_pct=0.02,
    is_win=True,
    hold_bars=5
)
sizer.add_trade(trade)

# Calculate position size for next trade:
result = sizer.calculate_position_size(account_equity=100000)
print(result['position_size_fraction'])  # e.g., 0.32x (32% of equity)
```

---

### 3. **ATR Circuit Module**
📍 Location: `C:\Users\James\jarvis-quant-framework\utils\atr_circuit.py`

**Key Features:**
- ✓ Non-linear trailing stop tightening based on profit progression
- ✓ Automatic scaling out (50% position) at 4+ ATR profit with RSI confirmation
- ✓ Consolidation detection (exit full position if reversal risk spike)
- ✓ ATR(14) calculation with numpy/pandas integration
- ✓ Spike detection (4ATR + RSI>75 = partial exit)

**Profit Escalation Levels:**
| Profit | Stop Placement | Action |
|--------|---|---|
| 0-1 ATR | Entry - 2×ATR | Protection |
| 1-2 ATR | Entry price | Breakeven |
| 2-3 ATR | Entry + 0.5×ATR | Mild tighten |
| 3-4 ATR | Entry + 1.5×ATR | Aggressive |
| 4+ ATR | Entry + 2×ATR | **SCALE 50%** |

**Usage in Strategy:**
```python
from utils.atr_circuit import ATRCircuit

circuit = ATRCircuit(atr_period=14, spike_threshold_atr=4.0)

# Calculate trailing stop
stop_result = circuit.calculate_trailing_stop(
    entry_price=100.0,
    current_price=104.0,
    atr_value=1.0
)
print(stop_result['stop_price'])      # e.g., 101.5
print(stop_result['exit_signal'])     # Hold, Scale 50%, Close

# Detect spike exits
spike_result = circuit.detect_spike_exit(
    current_price=104.0,
    entry_price=100.0,
    atr_value=1.0,
    rsi=78
)
if spike_result['exit_signal'] == ExitSignal.SCALE_OUT_50PCT:
    # Close 50% of position, keep 50% with tighter stop
    pass
```

---

## How to Activate These Instructions

### Option A: Explicit Hyper-Alpha Strategy Request
```
"Build a HyperAlpha strategy variant using Kelly Criterion and ATR circuits. 
Target SOL, ETH, TQQQ across 5 years. Apply to tri-agent optimizer."
```

**Result**: Agent will automatically:
1. Load `jarvis.hyper-alpha.instructions.md`
2. Create strategy class with Kelly sizing
3. Import and integrate `kelly_criterion.py` and `atr_circuit.py`
4. Test on high-beta assets
5. Apply stricter CRO validation (10% min return, 40% max DD)

---

### Option B: Mention Key Terms
Any prompt containing:
- "Kelly Criterion"
- "HyperAlpha"
- "ATR circuit"
- "High-beta" or "crypto trading"
- "Dynamic position sizing"

Will trigger automatic loading of the hyper-alpha instructions.

---

### Option C: Manual Integration
To manually integrate into existing strategies:

```python
# In your strategy file:
from utils.kelly_criterion import KellyCriterionSizer
from utils.atr_circuit import ATRCircuit, ExitSignal

class HyperAlphaStrategy(bt.Strategy):
    params = (
        ("fast", 5),
        ("slow", 20),
        ("rsi_period", 10),
    )
    
    def __init__(self):
        self.kelly_sizer = KellyCriterionSizer()
        self.atr_circuit = ATRCircuit()
        # ... indicators ...
    
    def next(self):
        # Entry logic with confirmed crossovers
        # ...
        
        # Exit with ATR circuit
        stop_result = self.atr_circuit.calculate_trailing_stop(
            self.entry_price, self.data.close[0], self.atr_value
        )
        
        if stop_result['exit_signal'] == ExitSignal.SCALE_OUT_50PCT:
            # Scale out 50%
            self.sell(size=self.position.size / 2)
```

---

## Next Actions & Recommendations

### Immediate: Create First HyperAlpha Strategy
```prompt
"Build a HyperAlpha-Kelly strategy with these parameters:
- EMA fast=5, slow=20
- RSI period=10 with overbought=75
- Kelly Criterion: 100-trade window, 50% fraction, 40% drift threshold
- ATR(14) circuits with 4x spike detection
- Test on BTC-USD, ETH-USD, SOL-USD over 3 years
- Add to tri-agent optimizer and report results"
```

**Expected Outcome:**
- 3 new strategy classes (HyperAlpha-Kelly, -Aggressive, -Conservative)
- Per-symbol Kelly sizing with regime logging
- ATR spike detection with partial exits
- Tri-agent results showing 15-25% annualized returns (if edge exists)

---

### Phase 2: Multi-Timeframe Confirmation
Enhance with higher-conviction entries:
```prompt
"Extend HyperAlpha with multi-timeframe confirmation:
- Daily timeframe: EMA crossover trigger
- 4H timeframe: ATR-based channel for confirmation
- Only enter if both align + RSI in 40-60 range
```

---

### Phase 3: Live Paper Trading
Execute real-time on Alpaca:
```prompt
"Deploy HyperAlpha-Kelly strategy to live paper trading:
- Real-time data from Alpaca API
- Dynamic Kelly sizing with live win-rate updates
- ATR circuits with market-execution slippage (5%)
- Log all trades and regime switches
- Email alerts on regime drift detection
```

---

### Phase 4: Portfolio-Level Kelly
Coordinate position sizing across multiple strategies:
```prompt
"Implement account-level Kelly Criterion:
- Combine win rates across all open HyperAlpha strategies
- Single Kelly calculation dictates total portfolio leverage
- Cascade 5x cap across positions proportionally
- Prevent over-leverage during peak-edge periods
```

---

## File Structure (Updated)

```
jarvis-quant-framework/
├── prompts/
│   └── jarvis.hyper-alpha.instructions.md      ← NEW
├── utils/
│   ├── kelly_criterion.py                      ← NEW
│   └── atr_circuit.py                          ← NEW
├── strategies/
│   ├── baseline_ema_rsi.py                     (existing)
│   ├── challenger_variants.py                  (existing)
│   ├── hyperalpha_kelly.py                     (to create)
│   ├── hyperalpha_aggressive.py                (to create)
│   └── hyperalpha_conservative.py              (to create)
└── logs/
    ├── kelly_regime_switches.json              (auto-generated)
    ├── partial_exits.json                      (auto-generated)
    └── tri_agent_results_hyperalpha.json       (auto-generated)
```

---

## Key Integration Points

### 1. **Backtest Harness** (Modify `backtest_harness.py`)
Add Kelly Criterion sizer option:
```python
class MultiAssetBacktest:
    def run(self, kelly_enabled=False, atr_circuit_enabled=False):
        if kelly_enabled:
            self.kelly_sizer = KellyCriterionSizer()
            # Use kelly_sizer.calculate_position_size() for sizing
```

### 2. **Tri-Agent Optimizer** (Modify `tri_agent_optimizer.py`)
Add HyperAlpha variants:
```python
def quant_generator(self):
    proposals = [
        # Existing
        {"name": "Baseline", ...},
        # NEW
        {"name": "HyperAlpha-Kelly", "kelly_enabled": True, ...},
        {"name": "HyperAlpha-Aggressive", "kelly_fraction": 0.75, ...},
    ]
```

### 3. **CRO Validation** (Modify `tri_agent_optimizer.py`)
Stricter criteria for HyperAlpha:
```python
if strategy_name.startswith("HyperAlpha"):
    # Higher return requirement (10% vs 5%)
    # Higher risk allowance (40% vs 30%)
    # Win rate minimum (45% vs none)
    is_robust = return > 0.10 and dd < 0.40 and win_rate > 0.45
```

---

## Validation Checklist

Before running first HyperAlpha strategy:

- [ ] `kelly_criterion.py` tested with mock trades
- [ ] `atr_circuit.py` tested with price progression
- [ ] Hyper-alpha instructions file loaded in VS Code
- [ ] First HyperAlpha strategy created and syntax-validated
- [ ] Backtest harness modified to support Kelly sizing
- [ ] Tri-agent optimizer includes HyperAlpha variants
- [ ] CRO validation rules updated for aggressive criteria
- [ ] Test on single asset (BTC-USD) first, then expand
- [ ] Verify regime switches logged correctly
- [ ] Confirm ATR scaling works as expected

---

## Support & Debugging

### If Kelly Sizing Isn't Triggering
- Check `kelly_regime_switches.json` to see regime state
- Ensure 50+ trades have completed
- Verify edge ratio (win/loss) > 1.5

### If ATR Circuits Aren't Exiting
- Confirm ATR(14) is calculating correctly
- Check RSI values (need >75 for spike exit)
- Verify profit is > 4 ATR for spike detection

### If Strategies Under-Perform
- Run diagnostic: Print Kelly stats at each calculation
- Compare actual vs expected stopping points
- Check slippage model (5% default) vs actual execution

---

**Created by**: Jarvis Agent  
**Framework**: Hyper-Alpha Quantitative Research  
**Status**: ✓ Ready for Implementation
