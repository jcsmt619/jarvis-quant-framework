"""
edge_hunting/reporter.py
Write the experiment output artefacts to reports/experiments/{name}/.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from edge_hunting.gate import GateVerdict


def write_reports(
    out_dir: Path,
    config: dict,
    metrics: dict,
    trades: list,
    equity: np.ndarray,
    index: pd.DatetimeIndex,
    target: np.ndarray,
    close: np.ndarray,
    benchmarks: dict,
    robustness: dict,
    gate_verdict: GateVerdict,
    look_ahead_passed: bool,
) -> None:
    """Write all experiment artefacts to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # metrics.json
    metrics_payload = {
        "strategy_name": config["strategy_name"],
        "metrics": _json_safe(metrics),
        "benchmarks": _json_safe(benchmarks),
        "robustness": _json_safe(robustness),
        "look_ahead_passed": look_ahead_passed,
        "gate_verdict": gate_verdict.verdict,
        "hard_failures": gate_verdict.hard_failures,
        "soft_warnings": gate_verdict.soft_warnings,
    }
    with open(out_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, default=str)

    # trades.csv
    trade_rows = [{k: v for k, v in t.items() if k != "meta"} for t in trades]
    pd.DataFrame(trade_rows).to_csv(out_dir / "trades.csv", index=False)

    # equity_curve.csv
    pd.DataFrame({
        "date": index,
        "equity": equity,
        "target": target,
        "close": close,
    }).to_csv(out_dir / "equity_curve.csv", index=False)

    # drawdown.csv
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    underwater = np.zeros(len(equity), dtype=int)
    cur = 0
    for i, flag in enumerate(equity < peak):
        cur = cur + 1 if flag else 0
        underwater[i] = cur
    pd.DataFrame({
        "date": index,
        "drawdown_pct": dd,
        "underwater_bars": underwater,
    }).to_csv(out_dir / "drawdown.csv", index=False)

    # cpcv_sharpe_distribution.csv
    cpcv_sharpes = robustness.get("cpcv_sharpes", [])
    if cpcv_sharpes:
        pd.DataFrame({
            "path": range(len(cpcv_sharpes)),
            "sharpe": cpcv_sharpes,
        }).to_csv(out_dir / "cpcv_sharpe_distribution.csv", index=False)

    # stress_test_summary.json
    stress = {
        k: _json_safe(v) for k, v in robustness.items()
        if k.startswith("stress_")
    }
    with open(out_dir / "stress_test_summary.json", "w", encoding="utf-8") as f:
        json.dump(stress, f, indent=2, default=str)

    # config_snapshot.yaml
    with open(out_dir / "config_snapshot.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    # assumptions.md
    _write_assumptions(out_dir / "assumptions.md", config)

    # failure_reasons.md
    _write_failure_reasons(out_dir / "failure_reasons.md", config, gate_verdict)


def _write_assumptions(path: Path, config: dict) -> None:
    fees = config.get("fees", {})
    tts = config.get("train_test_split", {})
    ps = config.get("position_sizing", {})
    rob = config.get("robustness", {})
    lines = [
        f"# Assumptions - {config['strategy_name']}",
        "",
        "## Data",
        "- Source: yfinance (daily OHLCV)",
        f"- Symbols: {', '.join(config.get('symbols', []))}",
        f"- Period: {config.get('start_date')} to {config.get('end_date')}",
        "",
        "## Costs",
        f"- Commission: ${fees.get('commission_per_trade', 0):.2f} per trade",
        f"- Slippage: {fees.get('slippage_bps', 0):.1f} bps per fill",
        "",
        "## Backtest",
        f"- Walk-forward: {tts.get('train_window', 252)} train / "
        f"{tts.get('test_window', 126)} test / {tts.get('step_size', 126)} step",
        f"- Fill delay: {tts.get('fill_delay', 1)} bar(s)",
        f"- Initial capital: ${ps.get('initial_capital', 100000):,.0f}",
        "",
        "## Robustness",
        f"- CPCV: {rob.get('cpcv', {}).get('n_groups', 6)} groups, "
        f"{rob.get('cpcv', {}).get('n_test_groups', 2)} test",
        f"- Deflated Sharpe trials: {rob.get('deflated_sharpe', {}).get('n_trials', 1)}",
        "",
        "## Limitations",
        "- No intraday data (daily bars only)",
        "- No market impact modeling",
        "- Past performance does not guarantee future results",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_failure_reasons(path: Path, config: dict, verdict: GateVerdict) -> None:
    lines = [f"# Failure Reasons - {config['strategy_name']}", ""]
    lines.append(f"## Verdict: {verdict.verdict}")
    lines.append("")
    if verdict.hard_failures:
        lines.append("## Hard Gate Failures")
        lines.append("")
        for fail in verdict.hard_failures:
            lines.append(f"- **{fail}**")
        lines.append("")
    if verdict.soft_warnings:
        lines.append("## Soft Warnings")
        lines.append("")
        for warn in verdict.soft_warnings:
            lines.append(f"- {warn}")
        lines.append("")
    if verdict.passed:
        lines.append("## Note")
        lines.append("")
        lines.append("Passing the validation gate means the strategy is NOT OBVIOUSLY BROKEN.")
        lines.append("Paper trading is the next step, not deployment.")
    else:
        lines.append("## Recommendation")
        lines.append("")
        lines.append(
            f"Do not paper trade. The strategy fails {len(verdict.hard_failures)} "
            f"hard gate(s). Review the signal logic and feature set."
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _json_safe(obj):
    """Convert numpy types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj
