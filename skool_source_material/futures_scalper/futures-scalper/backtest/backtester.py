"""Walk-forward backtester for intraday futures.

The shape is the same as the stock template: roll an in-sample window forward,
fit the HMM on it, then trade the out-of-sample window bar by bar with the
filtered regime so there is no look-ahead. The differences are futures-specific.
P&L runs through the simulation broker so a backtest dollar equals a live-sim
dollar, sizing is in contracts, fills cost a tick of slippage, and the prop-firm
rules (daily loss limit, trailing drawdown) are enforced during the walk so the
equity curve reflects what a funded account would actually have allowed.

Signal-on-close, fill-on-close-plus-slippage is the execution model. Bracket
exits are checked from the next bar using its high and low.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from brokers.base import OrderRequest, OrderSide, OrderType
from brokers.sim_broker import SimBroker
from core.features import FeatureEngineer
from core.hmm_engine import HMMEngine
from core.instruments import InstrumentSpec, get_instrument
from core.risk_manager import AccountState, HaltLevel, RiskManager
from core.scalp_strategies import Direction, ScalpOrchestrator


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    regime_history: pd.DataFrame
    blown: bool = False
    blown_reason: str = ""
    windows: int = 0
    meta: dict = field(default_factory=dict)


class WalkForwardBacktester:
    def __init__(self, config: dict, instrument: Optional[InstrumentSpec] = None) -> None:
        self.config = config
        self.bt = config.get("backtest", {})
        wf = self.bt.get("walk_forward", {})
        self.train_window = int(wf.get("train_window", 1500))
        self.test_window = int(wf.get("test_window", 500))
        self.step_size = int(wf.get("step_size", 500))
        self.instrument = instrument

        self.fe = FeatureEngineer(config.get("hmm", {}))
        self.hmm_cfg = config.get("hmm", {})
        self.strat_cfg = config.get("strategy", {})
        self.risk_cfg = config.get("risk", {})
        self.min_confidence = float(self.strat_cfg.get("min_confidence", 0.50))

    def run(self, bars: pd.DataFrame, symbol: str) -> BacktestResult:
        instrument = self.instrument or get_instrument(symbol)
        feats_full = self.fe.compute_hmm_features(bars)         # backward-looking, no look-ahead
        strat_full = self.fe.compute_strategy_features(bars)
        bars = bars.loc[feats_full.index.min():]                # align to feature warmup

        sim = SimBroker({
            "initial_equity": float(self.bt.get("initial_equity", 50000.0)),
            "slippage_ticks": float(self.bt.get("slippage_ticks", 1.0)),
            "commission_per_contract": float(self.bt.get("commission_per_contract", 2.50)),
        }, instruments={symbol: instrument})
        sim.connect()

        risk = RiskManager(self.risk_cfg)
        acct = AccountState(equity=sim.initial_equity, starting_equity=sim.initial_equity,
                            session_start_equity=sim.initial_equity,
                            high_water_mark=sim.initial_equity)

        equity_points: list[tuple[pd.Timestamp, float]] = []
        regime_rows: list[dict] = []
        blown, blown_reason = False, ""
        windows = 0
        cur_day = None

        feat_index = feats_full.index
        n = len(feat_index)
        is_start = 0
        while is_start + self.train_window + 1 < n and not blown:
            is_end = is_start + self.train_window
            oos_end = min(is_end + self.test_window, n)
            is_feats = feats_full.iloc[is_start:is_end]
            if len(is_feats) < self.hmm_cfg.get("min_train_bars", 300):
                break

            eng = HMMEngine(self.hmm_cfg)
            try:
                eng.fit(is_feats)
            except Exception:
                is_start += self.step_size
                continue
            orch = ScalpOrchestrator(self.strat_cfg, eng.regime_infos)
            windows += 1

            oos_feats = feats_full.iloc[is_end:oos_end]
            posteriors = eng.filtered_posteriors(oos_feats)
            eng.reset_tracking()

            for i, ts in enumerate(oos_feats.index):
                bar = bars.loc[ts]
                # 1. Advance bracket checks on this bar (exits from prior entries).
                trade = sim.on_bar(symbol, bar)

                # 2. Mark account, run breakers.
                acct.equity = sim.get_account().equity
                if cur_day is None:
                    cur_day = ts.normalize()
                elif ts.normalize() != cur_day:
                    cur_day = ts.normalize()
                    risk.start_session(acct)
                risk.update_after_fill_or_mark(acct)
                equity_points.append((ts, acct.equity))

                if risk.breaker.level is HaltLevel.HALTED_LOCKED:
                    sim.close_all()
                    blown, blown_reason = True, risk.breaker.reason
                    acct.equity = sim.get_account().equity
                    equity_points[-1] = (ts, acct.equity)
                    break

                # 3. Regime (with stability) at this bar.
                raw_id = int(np.argmax(posteriors[i]))
                conf_id, is_conf, consec = eng._update_stability(raw_id)
                prob = float(posteriors[i][conf_id])
                label = eng.get_regime_info(conf_id).regime_name
                regime_rows.append({"timestamp": ts, "regime_id": conf_id,
                                    "regime": label, "probability": prob,
                                    "confirmed": is_conf})

                if risk.is_halted() or not is_conf or prob < self.min_confidence:
                    continue
                if eng.is_flickering():
                    continue

                # 4. Signal from strategy features up to this bar.
                sfeats = strat_full.loc[:ts]
                from core.hmm_engine import RegimeState
                rstate = RegimeState(label=label, state_id=conf_id, probability=prob,
                                     state_probabilities=posteriors[i], timestamp=ts,
                                     is_confirmed=is_conf, consecutive_bars=consec)
                sig = orch.generate_signal(symbol, sfeats, rstate, instrument)
                if sig is None or sig.direction is Direction.FLAT:
                    continue

                # 5. Only one position per symbol at a time in this engine.
                if any(p.symbol == symbol and p.quantity != 0 for p in sim.get_positions()):
                    continue

                decision = risk.validate_signal(acct, sig, instrument)
                if not decision.approved or decision.contracts < 1:
                    continue
                side = OrderSide.BUY if sig.direction is Direction.LONG else OrderSide.SELL
                sim.set_price(symbol, sig.entry_price)
                sim.place_order(OrderRequest(
                    symbol=symbol, side=side, quantity=decision.contracts,
                    order_type=OrderType.MARKET,
                    stop_loss=sig.stop_price, take_profit=sig.target_price))
                acct.trades_today += 1

            is_start += self.step_size

        sim.close_all()
        equity = pd.Series(dict(equity_points)).sort_index() if equity_points else pd.Series(dtype=float)
        trades = pd.DataFrame(sim.closed_trades)
        regimes = pd.DataFrame(regime_rows).set_index("timestamp") if regime_rows else pd.DataFrame()

        return BacktestResult(
            equity_curve=equity, trades=trades, regime_history=regimes,
            blown=blown, blown_reason=blown_reason, windows=windows,
            meta={"symbol": symbol, "initial_equity": sim.initial_equity,
                  "final_equity": float(equity.iloc[-1]) if len(equity) else sim.initial_equity},
        )
