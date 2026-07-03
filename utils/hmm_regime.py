"""
utils/hmm_regime.py
===================
Macro REGIME SENSOR built natively on the STEP 2 HMM engine
(core/hmm_engine.py). It collapses the engine's volatility-ranked regimes into a
single binary risk gate that the leverage layer must consult BEFORE sizing:

    RISK_ON  = Calm / Trending-Bull   -> gate = 1.0  (allow Kelly scaling)
    RISK_OFF = High-Vol Chop / Bear   -> gate = 0.0  (force cash)
    NEUTRAL  = anything ambiguous      -> gate = 0.0  (conservative: cash)

Design guarantees:
  * DE-RISKING ONLY. The gate multiplies target exposure by {0, 1}; it can never
    increase leverage beyond the RiskManager caps. Its only power is to force
    cash. It cannot cause a circuit-breaker trip; it exists to prevent one.
  * NO LOOK-AHEAD. Regimes are produced by the engine's forward-filtered
    inference, and the model at bar t is trained only on data < t (expanding
    walk-forward retrain). Appending future bars cannot change past gates.

RISK_ON is deliberately strict: calm (lowest volatility tercile) AND price above
the 200-period trend AND a confirmed, non-flickering, high-confidence regime.
Everything else sits in cash. This is the "brain that avoids the breakers".
"""

from __future__ import annotations

import logging
import sys
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.hmm_engine import HMMRegimeEngine
from data.feature_engineering import build_standardized_features, log_returns

logger = logging.getLogger("hmm_regime")


class MacroRegime(Enum):
    RISK_ON = "risk_on"       # calm / trending-bull
    RISK_OFF = "risk_off"     # high-vol chop / bear
    NEUTRAL = "neutral"       # ambiguous


class HMMRegimeSensor:
    def __init__(
        self,
        n_candidates: list[int] | None = None,
        n_init: int = 2,
        min_train: int = 504,
        retrain_every: int = 252,
        max_train: int = 756,
        trend_period: int = 200,
        min_confidence: float = 0.55,
    ):
        self.n_candidates = n_candidates or [3, 4]
        self.n_init = n_init
        self.min_train = min_train
        self.retrain_every = retrain_every
        self.max_train = max_train
        self.trend_period = trend_period
        self.min_confidence = min_confidence

    # ------------------------------------------------------------------
    def _macro_label(self, engine: HMMRegimeEngine, state, trend_up: bool) -> MacroRegime:
        k = engine.n_regimes or 1
        sid = state.state_id
        try:
            vol_rank = engine.vol_sorted_ids.index(sid) / (k - 1) if k > 1 else 0.0
        except ValueError:
            vol_rank = 0.5
        info = engine.regime_info.get(sid)
        expected_return = info.expected_return if info else 0.0
        confident = (
            state.probability >= self.min_confidence
            and state.is_confirmed
            and not engine.is_flickering()
        )

        # High volatility OR negative expected drift -> get out.
        if vol_rank >= 2.0 / 3.0 or expected_return < 0.0:
            return MacroRegime.RISK_OFF
        # Calm + uptrend + confident -> unlock.
        if vol_rank <= 1.0 / 3.0 and trend_up and confident:
            return MacroRegime.RISK_ON
        return MacroRegime.NEUTRAL

    # ------------------------------------------------------------------
    def compute_gate_series(self, df: pd.DataFrame) -> pd.Series:
        """
        Return a causal gate Series (0.0 / 1.0) aligned to df.index. 1.0 means
        RISK_ON (allow scaling); 0.0 means cash. Warm-up bars are 0.0.
        """
        data = df.copy()
        data.columns = [c.lower() for c in data.columns]
        feats = build_standardized_features(data)
        full = pd.Series(0.0, index=df.index)
        if len(feats) < self.min_train + 5:
            return full

        X = feats.to_numpy()
        close = data["close"].reindex(feats.index).to_numpy()
        sma = data["close"].rolling(self.trend_period).mean().reindex(feats.index).to_numpy()
        rets = log_returns(data["close"], 1).reindex(feats.index)
        n = len(feats)
        gate = np.zeros(n)

        engine: HMMRegimeEngine | None = None
        trained_at = -10 ** 9
        i = self.min_train
        while i < n:
            if engine is None or (i - trained_at) >= self.retrain_every:
                start = max(0, i - self.max_train)
                try:
                    engine = HMMRegimeEngine(
                        n_candidates=self.n_candidates, n_init=self.n_init,
                        min_train_bars=self.min_train,
                    )
                    engine.train(feats.iloc[start:i], returns=rets.iloc[start:i])
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("regime train failed @%d: %s", i, exc)
                    engine = None
                    i += 1
                    continue
                trained_at = i
                engine.reset_state()
                for row in X[start:i]:      # warm the forward filter on past only
                    engine.update(row)

            state = engine.update(X[i])
            trend_up = bool(not np.isnan(sma[i]) and close[i] > sma[i])
            gate[i] = 1.0 if self._macro_label(engine, state, trend_up) == MacroRegime.RISK_ON else 0.0
            i += 1

        full.loc[feats.index] = gate
        return full
