"""
tests/test_look_ahead.py
========================
THE critical test. The HMM must report a regime at time T using only data up to
T. If appending future bars changes an earlier filtered state, the forward
algorithm is peeking at the future (look-ahead bias) and every backtest built on
it is a lie.

Note on the lesson's snippet: it compares predict_regime_filtered(data[0:400])[-1]
with predict_regime_filtered(data[0:500])[400], which is an off-by-one (index 399
vs 400). We assert the methodologically correct thing: the ENTIRE overlapping
region of filtered states must be identical.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.hmm_engine import HMMRegimeEngine
from data.feature_engineering import build_standardized_features

ROOT = Path(__file__).resolve().parent.parent
SPY_CSV = ROOT / "data" / "raw" / "spy.csv"


@pytest.fixture(scope="module")
def trained_engine_and_features():
    if not SPY_CSV.exists():
        pytest.skip("SPY data not available")
    df = pd.read_csv(SPY_CSV, parse_dates=["date"]).set_index("date")
    df.columns = [c.lower() for c in df.columns]
    feats = build_standardized_features(df)
    returns = np.log(df["close"] / df["close"].shift(1)).reindex(feats.index)

    engine = HMMRegimeEngine(n_candidates=[3], n_init=2, min_train_bars=300)
    engine.train(feats, returns=returns)
    return engine, feats


def test_no_look_ahead_bias(trained_engine_and_features):
    engine, feats = trained_engine_and_features
    X = feats.to_numpy()
    assert len(X) >= 600, "need enough bars for the test"

    regime_short = engine.predict_regime_filtered(X[:400])
    regime_long = engine.predict_regime_filtered(X[:500])

    # Every filtered state in the overlap must match exactly.
    assert np.array_equal(regime_short, regime_long[:400]), "LOOK-AHEAD BIAS DETECTED"

    # Lesson-style single-point check, correctly aligned (index 399).
    assert regime_short[-1] == regime_long[399], "LOOK-AHEAD BIAS DETECTED"


def test_incremental_update_matches_batch(trained_engine_and_features):
    """Cached live update() must reproduce the batch forward pass exactly."""
    engine, feats = trained_engine_and_features
    X = feats.to_numpy()[:300]

    batch_states = engine.predict_regime_filtered(X)

    engine.reset_state()
    live_states = []
    for row in X:
        # Compare RAW argmax (pre stability filter) against the batch forward pass.
        engine.update(row)
        live_states.append(engine._raw_history[-1])

    assert np.array_equal(batch_states, np.array(live_states)), "live forward pass diverged from batch"
