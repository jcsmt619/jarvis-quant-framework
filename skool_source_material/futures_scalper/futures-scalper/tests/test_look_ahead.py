"""The critical test. If filtered inference is honest, the regime printed at a
given bar must be identical whether or not future bars exist. A failure here
means the forward pass is peeking ahead and every backtest number is inflated.
"""

import numpy as np


def test_filtered_posterior_is_stable_to_future_data(fitted_engine, hmm_features):
    eng = fitted_engine
    full = eng.filtered_posteriors(hmm_features)
    for cut in (500, 800, 1100):
        partial = eng.filtered_posteriors(hmm_features.iloc[:cut])
        diff = np.abs(full[cut - 1] - partial[cut - 1]).max()
        assert diff < 1e-9, f"look-ahead at bar {cut}: max diff {diff}"


def test_regime_argmax_matches_across_lengths(fitted_engine, hmm_features):
    eng = fitted_engine
    full = eng.filtered_posteriors(hmm_features)
    cut = 900
    partial = eng.filtered_posteriors(hmm_features.iloc[:cut])
    assert int(np.argmax(full[cut - 1])) == int(np.argmax(partial[cut - 1]))


def test_posteriors_are_valid_distributions(fitted_engine, hmm_features):
    post = fitted_engine.filtered_posteriors(hmm_features)
    row_sums = post.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-6)
    assert (post >= -1e-9).all()
