"""
edge_hunting/funnel.py
========================
Six-filter survival funnel applied to walk-forward out-of-sample results.
Thresholds are configurable (see configs/edge_hunting.yaml). A strategy
survives only if it passes ALL six filters.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FunnelThresholds:
    max_drawdown_floor: float = -0.35       # OOS max DD must be better than -35%
    min_oos_sharpe: float = 0.5             # OOS Sharpe must exceed 0.5
    max_oos_sharpe: float = 2.5             # OOS Sharpe must be below 2.5
    max_oos_over_is_ratio: float = 1.30     # OOS Sharpe <= 1.3x in-sample Sharpe
    min_trade_count: int = 30               # at least 30 trades
    require_positive_in_sample: bool = True  # in-sample Sharpe must be > 0


FILTER_NAMES = [
    "max_drawdown",
    "min_oos_sharpe",
    "max_oos_sharpe",
    "oos_over_is_ratio",
    "min_trade_count",
    "positive_in_sample",
]


@dataclass
class FunnelVerdict:
    passed: dict[str, bool] = field(default_factory=dict)
    survived: bool = False
    failure_reason: str = ""

    def first_failure(self) -> str:
        for name in FILTER_NAMES:
            if not self.passed.get(name, False):
                return name
        return ""


def evaluate_funnel(
    in_sample_sharpe: float,
    oos_sharpe: float,
    oos_max_drawdown: float,
    trade_count: int,
    thresholds: FunnelThresholds | None = None,
) -> FunnelVerdict:
    t = thresholds or FunnelThresholds()
    passed: dict[str, bool] = {}

    passed["max_drawdown"] = oos_max_drawdown > t.max_drawdown_floor
    passed["min_oos_sharpe"] = oos_sharpe > t.min_oos_sharpe
    passed["max_oos_sharpe"] = oos_sharpe < t.max_oos_sharpe

    if in_sample_sharpe > 0:
        ratio_ok = oos_sharpe <= t.max_oos_over_is_ratio * in_sample_sharpe
    else:
        # If in-sample Sharpe isn't positive, the ratio check is moot --
        # filter 6 (require_positive_in_sample) will already reject this
        # candidate, so don't double-penalize; mark ratio filter as pass
        # to keep failure attribution clean and pointed at filter 6.
        ratio_ok = True
    passed["oos_over_is_ratio"] = ratio_ok

    passed["min_trade_count"] = trade_count >= t.min_trade_count
    passed["positive_in_sample"] = (in_sample_sharpe > 0) if t.require_positive_in_sample else True

    survived = all(passed.values())
    verdict = FunnelVerdict(passed=passed, survived=survived)
    if not survived:
        verdict.failure_reason = verdict.first_failure()
    return verdict


def failure_detail(
    name: str,
    in_sample_sharpe: float,
    oos_sharpe: float,
    oos_max_drawdown: float,
    trade_count: int,
    thresholds: FunnelThresholds | None = None,
) -> str:
    t = thresholds or FunnelThresholds()
    if name == "max_drawdown":
        return f"OOS max drawdown {oos_max_drawdown:.2%} <= floor {t.max_drawdown_floor:.2%}"
    if name == "min_oos_sharpe":
        return f"OOS Sharpe {oos_sharpe:.2f} <= minimum {t.min_oos_sharpe:.2f}"
    if name == "max_oos_sharpe":
        return f"OOS Sharpe {oos_sharpe:.2f} >= maximum {t.max_oos_sharpe:.2f} (suspiciously high)"
    if name == "oos_over_is_ratio":
        return (f"OOS Sharpe {oos_sharpe:.2f} exceeds {t.max_oos_over_is_ratio:.0%} of "
                f"in-sample Sharpe {in_sample_sharpe:.2f} (overfit signature)")
    if name == "min_trade_count":
        return f"Trade count {trade_count} < minimum {t.min_trade_count}"
    if name == "positive_in_sample":
        return f"In-sample Sharpe {in_sample_sharpe:.2f} is not positive"
    return "unknown filter"
