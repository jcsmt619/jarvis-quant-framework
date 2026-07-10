"""
strategies/hmm_adapter.py
=========================
Thin adapter that wraps the existing HMM regime-allocation strategy
(``core.hmm_engine.HMMRegimeEngine`` + ``core.regime_strategies.StrategyOrchestrator``)
behind the ``EdgeStrategy`` interface so the edge-hunting pipeline can run it.

**No strategy logic is modified.**  This file only translates between the
pipeline's ``fit`` / ``signal`` contract and the existing engine's API.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.base import EdgeStrategy, Signal
from core.hmm_engine import HMMRegimeEngine
from core.hmm_tuning import HMMTuningProfile
from core.regime_strategies import StrategyOrchestrator, LETF_STOP_MULTIPLIER
from data.feature_engineering import log_returns


class HMMAllocationAdapter(EdgeStrategy):
    """Wrap the existing HMM regime-allocation strategy for the pipeline."""

    def __init__(self) -> None:
        self._engine: HMMRegimeEngine | None = None
        self._orch: StrategyOrchestrator | None = None
        self._config: dict = {}
        self._letf_stop_multiplier: float = LETF_STOP_MULTIPLIER

    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "hmm_allocation"

    # ------------------------------------------------------------------
    def fit(
        self,
        train_features: pd.DataFrame,
        train_close: pd.Series,
        config: dict,
    ) -> None:
        """Train the HMM on the in-sample slice (BIC model selection)."""
        self._config = config
        wf = config.get("walk_forward", {})
        entry = config.get("entry_rules", {})
        exit_rules = config.get("exit_rules", {})

        n_candidates = wf.get("n_candidates", [3, 4, 5])
        n_init = wf.get("n_init", 4)
        random_state = wf.get("random_state", 42)
        profile_payload = config.get("hmm_tuning_profile")
        tuning_profile = HMMTuningProfile.from_dict(profile_payload) if profile_payload else None
        self._letf_stop_multiplier = exit_rules.get(
            "letf_stop_multiplier", LETF_STOP_MULTIPLIER,
        )

        ret_label = log_returns(train_close)

        self._engine = HMMRegimeEngine(
            n_candidates=n_candidates,
            n_init=n_init,
            min_train_bars=len(train_features),
            random_state=random_state,
            tuning_profile=tuning_profile,
        )
        self._engine.train(train_features, returns=ret_label)

        self._orch = StrategyOrchestrator(
            self._engine.regime_info,
            min_confidence=entry.get("min_confidence", 0.55),
            rebalance_threshold=entry.get("rebalance_threshold", 0.10),
            uncertainty_mult=entry.get("uncertainty_size_mult", 0.50),
            letf_stop_multiplier=self._letf_stop_multiplier,
        )

        # Seed the filtered state with the in-sample history.
        self._engine.reset_state()
        feat_matrix = train_features.to_numpy()
        for row in feat_matrix:
            self._engine.update(row)

    # ------------------------------------------------------------------
    def signal(
        self,
        bar_idx: int,
        features: pd.DataFrame,
        close: pd.Series,
    ) -> Signal:
        """Produce the target exposure for bar ``bar_idx`` (OOS walk)."""
        if self._engine is None or self._orch is None:
            return Signal(target_exposure=0.0)

        row = features.iloc[bar_idx].to_numpy()
        st = self._engine.update(row)

        price = float(close.iloc[bar_idx])
        # EMA50 fallback (same convention as the existing backtester).
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema = float(ema50.iloc[bar_idx]) if not np.isnan(ema50.iloc[bar_idx]) else price

        # ATR(14) for the stop price.  The existing backtester computes ATR
        # from OHLC; with only close available in the adapter we approximate
        # ATR as the EWM of |delta| (same alpha=1/14 convention).
        atr = close.diff().abs().ewm(alpha=1.0 / 14.0, adjust=False).mean()
        atr_val = float(atr.iloc[bar_idx]) if not np.isnan(atr.iloc[bar_idx]) else 0.0

        active = 0.0  # the pipeline tracks active allocation externally
        decision = self._orch.get_signal(
            st.state_id, price, ema, atr_val,
            st.probability, self._engine.is_flickering(),
            active_allocation=active,
        )
        tgt = decision.target_exposure

        # Mandatory stop: flatten when price closes below the stop.
        stopped = atr_val > 0 and price < decision.stop_price
        if stopped:
            tgt = 0.0

        return Signal(
            target_exposure=float(tgt),
            stop_price=float(decision.stop_price),
            meta={
                "regime_id": st.state_id,
                "label": st.label,
                "probability": float(st.probability),
                "confirmed": bool(st.is_confirmed),
                "strategy": decision.strategy,
                "stopped": bool(stopped),
            },
        )
