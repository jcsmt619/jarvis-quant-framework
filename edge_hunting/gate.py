"""
edge_hunting/gate.py
====================
Validation gate evaluator.  Checks a strategy's metrics + robustness results
against the hard/soft gate criteria defined in docs/STRATEGY_VALIDATION_GATE.md.

A strategy that fails ANY hard gate is REJECTED.  Soft gates are reported as
warnings but do not block.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GateVerdict:
    """Result of the validation gate evaluation."""

    verdict: str  # "PASS" | "FAIL"
    hard_failures: list[str] = field(default_factory=list)
    soft_warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"


def evaluate(
    metrics: dict,
    robustness: dict,
    look_ahead_passed: bool,
    beats_random: bool,
    beats_buy_hold: bool,
    config: dict,
) -> GateVerdict:
    """Evaluate the validation gate.

    Parameters
    ----------
    metrics : dict
        Output of ``backtest.performance.compute_metrics``.
    robustness : dict
        Contains ``dsr``, ``cpcv_pct_positive``, ``crash_worst_dd``,
        ``param_sensitivity_stable``.
    look_ahead_passed : bool
        Whether the look-ahead test gate passed.
    beats_random : bool
        Whether the strategy beats the random allocation mean return.
    beats_buy_hold : bool
        Whether the strategy beats buy & hold.
    config : dict
        The ``validation_gate`` section from the experiment config.
    """
    hard: list[str] = []
    soft: list[str] = []

    # --- Hard gates ---
    min_sharpe = config.get("min_oos_sharpe", 0.5)
    if metrics.get("sharpe", 0) < min_sharpe:
        hard.append(
            f"H1: OOS Sharpe {metrics.get('sharpe', 0):.2f} < {min_sharpe}"
        )

    max_dd = config.get("max_max_drawdown", 0.25)
    if metrics.get("max_drawdown", 0) > max_dd:
        hard.append(
            f"H2: Max DD {metrics.get('max_drawdown', 0):.2%} > {max_dd:.2%}"
        )

    min_dsr = config.get("min_dsr", 0.80)
    dsr = robustness.get("dsr", 0.0)
    if dsr < min_dsr:
        hard.append(f"H3: DSR {dsr:.2f} < {min_dsr}")

    min_cpcv = config.get("min_cpcv_pct_positive", 0.60)
    cpcv_pct = robustness.get("cpcv_pct_positive", 0.0)
    if cpcv_pct < min_cpcv:
        hard.append(f"H4: CPCV {cpcv_pct:.0%} positive < {min_cpcv:.0%}")

    if config.get("must_beat_random", True) and not beats_random:
        hard.append("H5: does not beat random allocation")

    if not look_ahead_passed:
        hard.append("H6: look-ahead test FAILED")

    crash_dd = robustness.get("crash_worst_dd", 0.0)
    if crash_dd < -0.35:
        hard.append(f"H7: crash stress worst DD {crash_dd:.2%} < -35%")

    if not robustness.get("param_sensitivity_stable", True):
        hard.append("H8: parameter sensitivity unstable")

    # --- Soft gates ---
    if not beats_buy_hold:
        soft.append("S1: does not beat buy & hold (informational)")

    cpcv_std = robustness.get("cpcv_sharpe_std", 0.0)
    if cpcv_std > 1.5:
        soft.append(f"S2: CPCV Sharpe std {cpcv_std:.2f} > 1.50")

    pf = metrics.get("profit_factor", 0)
    if pf < 1.2:
        soft.append(f"S3: profit factor {pf:.2f} < 1.20")

    wr = metrics.get("win_rate", 0)
    if wr < 0.35:
        soft.append(f"S4: win rate {wr:.0%} < 35%")

    avg_hold = metrics.get("avg_holding_bars", 0)
    if avg_hold < 2:
        soft.append(f"S5: avg holding {avg_hold:.1f} bars < 2 (overtrading?)")

    contained = robustness.get("regime_misclass_contained", True)
    if not contained:
        soft.append("S6: regime misclassification NOT contained")

    return GateVerdict(
        verdict="PASS" if not hard else "FAIL",
        hard_failures=hard,
        soft_warnings=soft,
    )