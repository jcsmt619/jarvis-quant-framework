"""
tests/test_meridian_lite.py
===========================
Meridian-Lite engine: factor causality (no look-ahead), beta-neutral
construction, and sector-cap enforcement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.meridian_lite import (
    MeridianConfig,
    _pick_with_sector_cap,
    factor_scores,
    rolling_beta,
)


def _synthetic(n_days=800, n_stocks=30, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=n_days)
    rets = rng.normal(0.0004, 0.015, (n_days, n_stocks))
    prices = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)),
                          index=dates, columns=[f"S{i:02d}" for i in range(n_stocks)])
    sectors = {f"S{i:02d}": f"sec{i % 5}" for i in range(n_stocks)}
    return prices, sectors


# --- 1. causality: scores at t identical with/without future data -----------
def test_factor_scores_no_lookahead():
    prices, sectors = _synthetic()
    cfg = MeridianConfig()
    loc = 500
    full = factor_scores(prices, sectors, loc, cfg)
    prefix = factor_scores(prices.iloc[: loc + 1], sectors, loc, cfg)
    pd.testing.assert_series_equal(full["composite"], prefix["composite"])


def test_beta_no_lookahead():
    prices, sectors = _synthetic()
    spy = prices.mean(axis=1)
    loc = 500
    full = rolling_beta(prices, spy, loc, 60)
    prefix = rolling_beta(prices.iloc[: loc + 1], spy.iloc[: loc + 1], loc, 60)
    pd.testing.assert_series_equal(full, prefix)


# --- 2. beta-neutral construction --------------------------------------------
def test_short_book_scaling_neutralizes_beta():
    cfg = MeridianConfig()
    beta_l, beta_s = 1.30, 0.90            # longs high-beta, shorts low-beta
    short_gross = np.clip(cfg.long_gross * beta_l / beta_s, *cfg.short_scale_bounds)
    net_beta = cfg.long_gross * beta_l - short_gross * beta_s
    assert abs(net_beta) < 0.05            # ~0 within clamp bounds

    # Clamp binds on extreme ratios but bounds residual beta.
    beta_l2, beta_s2 = 2.0, 0.5
    sg2 = np.clip(cfg.long_gross * beta_l2 / beta_s2, *cfg.short_scale_bounds)
    assert sg2 == cfg.short_scale_bounds[1]        # clamped at 1.10


# --- 3. sector cap ------------------------------------------------------------
def test_sector_cap_enforced():
    ranked = pd.DataFrame({
        "sector": ["tech"] * 8 + ["fin"] * 8,
        "composite": np.linspace(2.0, 0.1, 16),
    }, index=[f"T{i}" for i in range(16)])
    picked = _pick_with_sector_cap(ranked, n=10, cap=5)
    counts = ranked.loc[picked, "sector"].value_counts()
    assert counts.max() <= 5 and len(picked) == 10
