"""
tests/test_hmm_regime.py
========================
The macro regime gate must be (a) a clean 0/1 series aligned to the input index
and (b) strictly causal: the gate at bar t must not change when future bars are
appended (no look-ahead leaking through the regime sensor into the risk layer).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from utils.hmm_regime import HMMRegimeSensor, MacroRegime

ROOT = Path(__file__).resolve().parent.parent
SPY_CSV = ROOT / "data" / "raw" / "spy.csv"


@pytest.fixture(scope="module")
def spy():
    if not SPY_CSV.exists():
        pytest.skip("SPY data not available")
    df = pd.read_csv(SPY_CSV, parse_dates=["date"]).set_index("date")
    df.columns = [c.lower() for c in df.columns]
    return df


def _fast_sensor():
    # Small windows keep the test quick while exercising retraining.
    return HMMRegimeSensor(n_candidates=[3], n_init=1, min_train=150, retrain_every=100, max_train=200)


def test_gate_is_binary_and_aligned(spy):
    df = spy.iloc[:450]
    gate = _fast_sensor().compute_gate_series(df)
    assert list(gate.index) == list(df.index)
    assert set(np.unique(gate.to_numpy())).issubset({0.0, 1.0})
    # Warm-up region (before any model exists) must be cash.
    assert gate.iloc[:150].sum() == 0.0


def test_gate_has_no_look_ahead(spy):
    sensor = _fast_sensor()
    short = sensor.compute_gate_series(spy.iloc[:380])
    long = sensor.compute_gate_series(spy.iloc[:450])
    common = short.index.intersection(long.index)
    assert len(common) > 100
    np.testing.assert_array_equal(short.loc[common].to_numpy(), long.loc[common].to_numpy())


def test_gate_only_reduces_exposure(spy):
    """The gate can only be 0 or 1 -> it can never amplify leverage, only cut it."""
    gate = _fast_sensor().compute_gate_series(spy.iloc[:450])
    assert gate.max() <= 1.0
    assert gate.min() >= 0.0
