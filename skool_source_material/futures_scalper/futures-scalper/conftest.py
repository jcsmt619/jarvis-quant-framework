"""Shared pytest fixtures.

Everything runs offline on synthetic regime-switching bars so the suite needs
no broker and no network.
"""

import pytest

from data.loaders import generate_synthetic_bars
from core.features import FeatureEngineer
from core.hmm_engine import HMMEngine


@pytest.fixture(scope="session")
def bars():
    return generate_synthetic_bars(n=2500, base_price=18000, seed=3, n_regimes=3)


@pytest.fixture(scope="session")
def feature_engineer():
    return FeatureEngineer({"zscore_window": 252})


@pytest.fixture(scope="session")
def hmm_features(bars, feature_engineer):
    return feature_engineer.compute_hmm_features(bars)


@pytest.fixture(scope="session")
def fitted_engine(hmm_features):
    eng = HMMEngine({"n_candidates": [3], "n_init": 4, "min_train_bars": 400,
                     "stability_bars": 2})
    eng.fit(hmm_features)
    return eng


@pytest.fixture
def hmm_config():
    return {"n_candidates": [3], "n_init": 4, "min_train_bars": 400, "stability_bars": 2,
            "zscore_window": 252}
