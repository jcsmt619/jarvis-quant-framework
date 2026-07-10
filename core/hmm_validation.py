from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.experiment_registry import append_experiment_record, build_experiment_record
from core.hmm_tuning import HMMTuningProfile, LIVE_TRADING_DISABLED
from risk.policies import HUMAN_REVIEW_REQUIRED, MONITOR_ONLY, PAPER_ONLY, RESEARCH_ONLY


@dataclass(frozen=True)
class HMMValidationConfig:
    experiment_id: str
    strategy_id: str
    asset: str
    dataset_id: str
    timeframe: str
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    fill_delay_bars: int = 1
    drift_z_threshold: float = 2.0
    min_baseline_excess_sharpe: float = 0.0
    labels: tuple[str, ...] = (RESEARCH_ONLY, PAPER_ONLY, MONITOR_ONLY, HUMAN_REVIEW_REQUIRED)
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False

    def validate(self) -> "HMMValidationConfig":
        required = {
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "asset": self.asset,
            "dataset_id": self.dataset_id,
            "timeframe": self.timeframe,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "validation_start": self.validation_start,
            "validation_end": self.validation_end,
        }
        for field_name, value in required.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"HMM validation config is missing {field_name}")
        if self.fill_delay_bars < 0:
            raise ValueError("fill_delay_bars must be >= 0")
        if self.drift_z_threshold <= 0:
            raise ValueError("drift_z_threshold must be positive")
        if RESEARCH_ONLY not in self.labels or PAPER_ONLY not in self.labels:
            raise ValueError("HMM validation must include RESEARCH_ONLY and PAPER_ONLY labels")
        if HUMAN_REVIEW_REQUIRED not in self.labels:
            raise ValueError("HMM validation must require human review")
        if self.live_trading_enabled or self.broker_order_routing_enabled:
            raise ValueError("HMM validation cannot enable live trading or broker routing")
        return self

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["labels"] = list(self.labels)
        payload["live_trading_status"] = LIVE_TRADING_DISABLED
        return payload


@dataclass(frozen=True)
class HMMValidationResult:
    config: HMMValidationConfig
    profile: dict[str, Any]
    tuned_metrics: dict[str, float | int]
    baseline_metrics: dict[str, dict[str, float | int]]
    baseline_comparison: dict[str, float | bool | str]
    drift_checks: dict[str, Any]
    review_report: dict[str, Any]
    labels: tuple[str, ...] = (RESEARCH_ONLY, PAPER_ONLY, MONITOR_ONLY, HUMAN_REVIEW_REQUIRED)
    live_trading_enabled: bool = False
    broker_order_routing_enabled: bool = False
    broker_order_call_performed: bool = False
    real_paper_order_submitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["config"] = self.config.to_dict()
        payload["labels"] = list(self.labels)
        payload["live_trading_status"] = LIVE_TRADING_DISABLED
        return payload


def validate_hmm_regime_experiment(
    *,
    config: HMMValidationConfig,
    profile: HMMTuningProfile,
    train_features: pd.DataFrame,
    validation_returns: pd.Series,
    tuned_allocations: pd.Series,
    baseline_allocations: dict[str, pd.Series] | None = None,
    validation_features: pd.DataFrame | None = None,
) -> HMMValidationResult:
    """Evaluate one tuned HMM allocation stream against naive OOS baselines."""
    config.validate()
    profile.validate()
    returns = _clean_series("validation_returns", validation_returns)
    tuned = _align_allocation("tuned_hmm", tuned_allocations, returns.index)
    baselines = baseline_allocations or build_naive_baseline_allocations(returns)
    if not baselines:
        raise ValueError("at least one naive baseline is required")

    tuned_metrics = _performance_metrics(_delayed_strategy_returns(returns, tuned, config.fill_delay_bars))
    baseline_metrics = {
        name: _performance_metrics(
            _delayed_strategy_returns(returns, _align_allocation(name, allocation, returns.index), config.fill_delay_bars)
        )
        for name, allocation in sorted(baselines.items())
    }
    comparison = _compare_to_baselines(
        tuned_metrics,
        baseline_metrics,
        min_excess_sharpe=config.min_baseline_excess_sharpe,
    )
    drift_checks = compute_feature_drift_checks(
        train_features=train_features,
        validation_features=validation_features,
        drift_z_threshold=config.drift_z_threshold,
    )
    report = _review_report(config, tuned_metrics, baseline_metrics, comparison, drift_checks)

    return HMMValidationResult(
        config=config,
        profile=profile.to_dict(),
        tuned_metrics=tuned_metrics,
        baseline_metrics=baseline_metrics,
        baseline_comparison=comparison,
        drift_checks=drift_checks,
        review_report=report,
    )


def build_naive_baseline_allocations(validation_returns: pd.Series, *, vol_window: int = 20) -> dict[str, pd.Series]:
    returns = _clean_series("validation_returns", validation_returns)
    buy_hold = pd.Series(1.0, index=returns.index, name="buy_hold")
    rolling_vol = returns.rolling(vol_window, min_periods=max(2, vol_window // 2)).std()
    vol_cutoff = rolling_vol.expanding(min_periods=1).median()
    naive_vol_filter = (rolling_vol <= vol_cutoff).astype(float).fillna(1.0)
    naive_vol_filter.name = "naive_vol_filter"
    return {
        "buy_hold": buy_hold,
        "naive_vol_filter": naive_vol_filter,
    }


def compute_feature_drift_checks(
    *,
    train_features: pd.DataFrame,
    validation_features: pd.DataFrame | None,
    drift_z_threshold: float,
) -> dict[str, Any]:
    if drift_z_threshold <= 0:
        raise ValueError("drift_z_threshold must be positive")
    if validation_features is None:
        return {
            "checked": False,
            "status": "not_available",
            "drift_z_threshold": float(drift_z_threshold),
            "flagged_features": [],
            "feature_count": 0,
        }
    if train_features.empty or validation_features.empty:
        raise ValueError("train_features and validation_features must be non-empty when drift is checked")

    common = [column for column in train_features.columns if column in validation_features.columns]
    if not common:
        raise ValueError("no common features available for drift checks")

    feature_checks: dict[str, dict[str, float | bool]] = {}
    flagged: list[str] = []
    for column in common:
        train = pd.to_numeric(train_features[column], errors="coerce").dropna()
        valid = pd.to_numeric(validation_features[column], errors="coerce").dropna()
        if train.empty or valid.empty:
            continue
        train_std = float(train.std(ddof=0))
        denom = train_std if train_std > 1e-12 else 1.0
        z_score = float(abs(float(valid.mean()) - float(train.mean())) / denom)
        flagged_feature = z_score > drift_z_threshold
        if flagged_feature:
            flagged.append(str(column))
        feature_checks[str(column)] = {
            "train_mean": float(train.mean()),
            "validation_mean": float(valid.mean()),
            "train_std": train_std,
            "mean_shift_z": z_score,
            "flagged": flagged_feature,
        }

    return {
        "checked": True,
        "status": "drift_flagged" if flagged else "passed",
        "drift_z_threshold": float(drift_z_threshold),
        "flagged_features": flagged,
        "feature_count": len(feature_checks),
        "features": feature_checks,
    }


def write_hmm_validation_artifacts(
    result: HMMValidationResult,
    *,
    report_dir: Path = Path("reports/hmm_validation"),
) -> tuple[Path, Path]:
    result.config.validate()
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(result.config.experiment_id)
    json_path = report_dir / f"{stem}.json"
    md_path = report_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown_report(result), encoding="utf-8")
    return json_path, md_path


def append_hmm_validation_to_registry(
    result: HMMValidationResult,
    *,
    registry_dir: Path = Path("reports/experiment_registry"),
    artifacts: tuple[str, ...] = (),
    now: datetime | None = None,
) -> Path:
    result.config.validate()
    record = build_experiment_record(
        experiment_id=result.config.experiment_id,
        experiment_type="hmm_regime_validation",
        strategy_id=result.config.strategy_id,
        engine="hmm_regime_validation",
        label=HUMAN_REVIEW_REQUIRED,
        summary="BR-10E HMM regime validation is research-only, paper-only, and requires human review.",
        dataset_id=result.config.dataset_id,
        timeframe=result.config.timeframe,
        parameters={
            "config": result.config.to_dict(),
            "profile": result.profile,
        },
        metrics={
            "tuned_metrics": result.tuned_metrics,
            "baseline_metrics": result.baseline_metrics,
            "baseline_comparison": result.baseline_comparison,
            "drift_checks": result.drift_checks,
        },
        artifacts=artifacts,
        notes=(RESEARCH_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED, LIVE_TRADING_DISABLED),
        tags=("BR-10E", "hmm", "regime_validation"),
        now=now,
    )
    return append_experiment_record(record, registry_dir=registry_dir)


def _clean_series(field_name: str, series: pd.Series) -> pd.Series:
    if not isinstance(series, pd.Series):
        raise ValueError(f"{field_name} must be a pandas Series")
    cleaned = pd.to_numeric(series, errors="coerce").dropna()
    if cleaned.empty:
        raise ValueError(f"{field_name} must contain numeric values")
    return cleaned.astype(float)


def _align_allocation(name: str, allocation: pd.Series, index: pd.Index) -> pd.Series:
    aligned = _clean_series(name, allocation).reindex(index).ffill().fillna(0.0)
    if ((aligned < 0.0) | (aligned > 1.0)).any():
        raise ValueError(f"{name} allocation must stay between 0 and 1")
    return aligned.astype(float)


def _delayed_strategy_returns(returns: pd.Series, allocation: pd.Series, fill_delay_bars: int) -> pd.Series:
    effective_allocation = allocation.shift(fill_delay_bars).fillna(0.0)
    return (returns * effective_allocation).astype(float)


def _performance_metrics(strategy_returns: pd.Series) -> dict[str, float | int]:
    returns = _clean_series("strategy_returns", strategy_returns)
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    volatility = float(returns.std(ddof=0) * np.sqrt(252.0))
    sharpe = 0.0 if volatility <= 1e-12 else float(returns.mean() * 252.0 / volatility)
    total_return = float(equity.iloc[-1] - 1.0)
    return {
        "bars": int(len(returns)),
        "total_return": total_return,
        "annualized_return": float(returns.mean() * 252.0),
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "positive_bars": int((returns > 0.0).sum()),
    }


def _compare_to_baselines(
    tuned_metrics: dict[str, float | int],
    baseline_metrics: dict[str, dict[str, float | int]],
    *,
    min_excess_sharpe: float,
) -> dict[str, float | bool | str]:
    best_name, best_metrics = max(
        baseline_metrics.items(),
        key=lambda item: float(item[1]["sharpe"]),
    )
    excess_sharpe = float(tuned_metrics["sharpe"]) - float(best_metrics["sharpe"])
    beat_best = excess_sharpe >= min_excess_sharpe
    return {
        "best_baseline": best_name,
        "best_baseline_sharpe": float(best_metrics["sharpe"]),
        "tuned_sharpe": float(tuned_metrics["sharpe"]),
        "excess_sharpe_vs_best_baseline": excess_sharpe,
        "beat_best_baseline": beat_best,
        "min_excess_sharpe_required": float(min_excess_sharpe),
    }


def _review_report(
    config: HMMValidationConfig,
    tuned_metrics: dict[str, float | int],
    baseline_metrics: dict[str, dict[str, float | int]],
    comparison: dict[str, float | bool | str],
    drift_checks: dict[str, Any],
) -> dict[str, Any]:
    status = HUMAN_REVIEW_REQUIRED
    if drift_checks.get("status") == "drift_flagged" or not comparison["beat_best_baseline"]:
        status = HUMAN_REVIEW_REQUIRED
    return {
        "phase": "BR-10E",
        "asset": config.asset,
        "status": status,
        "labels": [RESEARCH_ONLY, PAPER_ONLY, MONITOR_ONLY, HUMAN_REVIEW_REQUIRED],
        "live_trading_status": LIVE_TRADING_DISABLED,
        "decision": "paper_only_review_required",
        "tuned_sharpe": tuned_metrics["sharpe"],
        "baseline_count": len(baseline_metrics),
        "best_baseline": comparison["best_baseline"],
        "drift_status": drift_checks["status"],
    }


def _markdown_report(result: HMMValidationResult) -> str:
    lines = [
        f"# BR-10E HMM Regime Validation - {result.config.experiment_id}",
        "",
        f"- Asset: {result.config.asset}",
        f"- Dataset: {result.config.dataset_id}",
        f"- Timeframe: {result.config.timeframe}",
        f"- Labels: {', '.join(result.labels)}",
        f"- Live trading: {LIVE_TRADING_DISABLED}",
        f"- Review: {HUMAN_REVIEW_REQUIRED}",
        "",
        "## Tuned HMM",
        f"- Sharpe: {result.tuned_metrics['sharpe']:.6f}",
        f"- Total return: {result.tuned_metrics['total_return']:.6f}",
        f"- Max drawdown: {result.tuned_metrics['max_drawdown']:.6f}",
        "",
        "## Baseline Comparison",
        f"- Best baseline: {result.baseline_comparison['best_baseline']}",
        f"- Excess Sharpe: {result.baseline_comparison['excess_sharpe_vs_best_baseline']:.6f}",
        f"- Beat best baseline: {result.baseline_comparison['beat_best_baseline']}",
        "",
        "## Drift Checks",
        f"- Status: {result.drift_checks['status']}",
        f"- Flagged features: {', '.join(result.drift_checks.get('flagged_features', [])) or 'none'}",
        "",
        "This artifact is research-only and paper-only. Human review is required before any operational use.",
        "",
    ]
    return "\n".join(lines)


def _safe_stem(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)
