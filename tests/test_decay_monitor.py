"""
tests/test_decay_monitor.py
===========================
A monitor's contract is its DETECTION RATES, not one lucky draw: assertions
run across many seeded live tracks. KS must catch vol/shape drift, the edge
PSR must catch the silent mean decay KS cannot see, healthy tracks must
stay mostly green, and the dominated Sharpe-halving heuristic must be gone.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk.decay_monitor import DecayMonitor

N_SEEDS = 40
LIVE_N = 252                     # one year of live daily observations


@pytest.fixture(scope="module")
def mon() -> DecayMonitor:
    return DecayMonitor(min_live=50)


@pytest.fixture(scope="module")
def bt() -> pd.Series:
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(0.001, 0.01, 2000))   # healthy funded edge


def _rates(mon, bt, loc, scale, n=LIVE_N):
    """Verdict frequencies across N_SEEDS independent live tracks."""
    stat = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    ks_hits = psr_alarms = 0
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(1000 + seed)
        r = mon.diagnose(bt, pd.Series(rng.normal(loc, scale, n)))
        stat[r["status"]] += 1
        ks_hits += r["ks_p_value"] < mon.p_threshold
        psr_alarms += r["edge_psr"] < mon.psr_yellow
    return {k: v / N_SEEDS for k, v in stat.items()}, \
        ks_hits / N_SEEDS, psr_alarms / N_SEEDS


def test_waiting_gate(mon, bt):
    r = mon.diagnose(bt, pd.Series([0.001] * 10))
    assert r["status"] == "WAITING_FOR_DATA"
    assert np.isnan(r["ks_p_value"])


def test_healthy_track_mostly_green(mon, bt):
    """False-alarm rate on a healthy strategy stays near the designed
    ~psr_yellow + KS alpha, and healthy RED verdicts are rare."""
    rates, _, _ = _rates(mon, bt, loc=0.001, scale=0.01)
    assert rates["GREEN"] >= 0.65
    assert rates["RED"] <= 0.15


def test_silent_decay_caught_by_psr_not_ks(mon, bt):
    """The draft-killer: edge decays to zero at unchanged vol. KS stays
    blind; the PSR leg is the only detector with real power -- MEASURED at
    ~50% per independent year of live data (finite power is the honest
    finding; the draft's KS-only design has ~5%)."""
    rates, ks_rate, psr_rate = _rates(mon, bt, loc=0.0, scale=0.01)
    assert ks_rate <= 0.20                    # KS: near its false-alarm rate
    assert psr_rate >= 0.45                   # PSR: measured ~52% power
    assert psr_rate > ks_rate + 0.25          # and it dominates KS outright
    assert rates["GREEN"] <= 0.55             # "nominal" under half the time


def test_vol_regime_break_caught_by_ks(mon, bt):
    rates, ks_rate, _ = _rates(mon, bt, loc=-0.002, scale=0.025)
    assert ks_rate >= 0.95                    # unmissable distribution break
    assert rates["RED"] >= 0.95


def test_negative_backtest_no_nonsense(mon):
    """bt Sharpe < 0 with a matching live track: no halving-heuristic
    branch exists to demand live be MORE negative."""
    rng = np.random.default_rng(4)
    bt_bad = pd.Series(rng.normal(-0.0002, 0.01, 2000))
    greens = 0
    for seed in range(N_SEEDS):
        r = mon.diagnose(bt_bad, pd.Series(
            np.random.default_rng(2000 + seed).normal(-0.0002, 0.01, LIVE_N)))
        greens += r["status"] == "GREEN"
    assert greens / N_SEEDS >= 0.65           # matching track ~= healthy rates


def test_false_alarm_disclosure_present(mon, bt):
    rng = np.random.default_rng(5)
    r = mon.diagnose(bt, pd.Series(rng.normal(0.001, 0.01, 100)))
    assert "false RED per 20" in r["false_alarm_note"]


def test_vitals_math():
    r = pd.Series([0.01, -0.01, 0.01, 0.01])
    v = DecayMonitor.vitals(r)
    assert v["win_rate"] == pytest.approx(0.75)
    assert v["n"] == 4
    assert v["sharpe"] == pytest.approx(r.mean() / r.std() * np.sqrt(252))
