"""
edge_hunting/report_writer.py
================================
Writes sweep_results.csv, top_survivors.csv, funnel_report.md,
funnel_summary.json, and the cross-sectional momentum report files.
Pure I/O -- no strategy logic, no broker, no execution.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DEFAULT_OUT_DIR = Path("reports/edge_hunting")


def write_sweep_results(results_df: pd.DataFrame, out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "sweep_results.csv"
    results_df.to_csv(path, index=False)
    return path


def write_top_survivors(results_df: pd.DataFrame, out_dir: Path = DEFAULT_OUT_DIR,
                         top_n: int = 50) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    survivors = results_df[results_df["survived"] == True].copy()  # noqa: E712
    survivors = survivors.sort_values("oos_sharpe", ascending=False).head(top_n)
    path = out_dir / "top_survivors.csv"
    survivors.to_csv(path, index=False)
    return path


def _asset_concentration_warning(survivors: pd.DataFrame) -> str:
    if survivors.empty:
        return ""
    counts = survivors["asset"].value_counts(normalize=True)
    if not counts.empty and counts.iloc[0] > 0.5:
        return (f"⚠ WARNING: {counts.index[0]} accounts for "
                f"{counts.iloc[0]:.0%} of all survivors -- results may be "
                f"asset-specific rather than a genuine cross-market edge.")
    return ""


def write_funnel_report(
    results_df: pd.DataFrame,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(results_df)
    positive_oos = int((results_df["oos_sharpe"] > 0).sum())
    cleared_half = int((results_df["oos_sharpe"] > 0.5).sum())
    survivors = results_df[results_df["survived"] == True]  # noqa: E712
    n_survivors = len(survivors)

    survival_by_category = (
        results_df.groupby("category")["survived"].mean().sort_values(ascending=False)
        if "category" in results_df.columns else pd.Series(dtype=float)
    )
    survival_by_family = (
        results_df.groupby("family")["survived"].mean().sort_values(ascending=False)
        if "family" in results_df.columns else pd.Series(dtype=float)
    )
    mean_sharpe_by_category = (
        results_df.groupby("category")["oos_sharpe"].mean().sort_values(ascending=False)
        if "category" in results_df.columns else pd.Series(dtype=float)
    )

    failure_counts: dict[str, int] = {}
    if "failure_reason" in results_df.columns:
        failure_counts = results_df.loc[
            results_df["survived"] == False, "failure_reason"  # noqa: E712
        ].value_counts().to_dict()

    concentration_warning = _asset_concentration_warning(survivors)

    lines = [
        "# Funnel Report",
        "",
        f"- Total backtests run: {total}",
        f"- Positive OOS Sharpe: {positive_oos} ({positive_oos / total:.1%})" if total else "- Positive OOS Sharpe: 0",
        f"- Cleared 0.5 OOS Sharpe: {cleared_half} ({cleared_half / total:.1%})" if total else "- Cleared 0.5 OOS Sharpe: 0",
        f"- Survived all six filters: {n_survivors} ({n_survivors / total:.2%})" if total else "- Survived all six filters: 0",
        "",
    ]
    if concentration_warning:
        lines += [concentration_warning, ""]

    lines.append("## Survival Rate by Category")
    for cat, rate in survival_by_category.items():
        lines.append(f"- {cat}: {rate:.1%}")
    lines.append("")

    lines.append("## Survival Rate by Strategy Family")
    for fam, rate in survival_by_family.items():
        lines.append(f"- {fam}: {rate:.1%}")
    lines.append("")

    lines.append("## Mean OOS Sharpe by Category")
    for cat, s in mean_sharpe_by_category.items():
        lines.append(f"- {cat}: {s:.2f}")
    lines.append("")

    lines.append("## Failure Counts by Filter")
    for filt, n in sorted(failure_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {filt}: {n}")
    lines.append("")

    lines.append("## Top Survivors")
    if n_survivors:
        top = survivors.sort_values("oos_sharpe", ascending=False).head(20)
        cols = [c for c in ["asset", "strategy_name", "category", "oos_sharpe",
                             "oos_max_drawdown", "trade_count", "total_return"] if c in top.columns]
        lines.append(top[cols].to_string(index=False))
    else:
        lines.append("(no survivors)")

    md_path = out_dir / "funnel_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "total_backtests": total,
        "positive_oos_sharpe": positive_oos,
        "cleared_0.5_oos_sharpe": cleared_half,
        "survivors": n_survivors,
        "survival_rate": n_survivors / total if total else 0.0,
        "survival_by_category": survival_by_category.to_dict(),
        "survival_by_family": survival_by_family.to_dict(),
        "mean_oos_sharpe_by_category": mean_sharpe_by_category.to_dict(),
        "failure_counts_by_filter": failure_counts,
        "concentration_warning": concentration_warning,
    }
    json_path = out_dir / "funnel_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print("\n".join(lines))
    return md_path, json_path


def write_cross_sectional_report(
    cs_results: list[dict],
    single_asset_momentum_comparison: pd.DataFrame | None = None,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(cs_results)
    csv_path = out_dir / "cross_sectional_momentum.csv"
    df.to_csv(csv_path, index=False)

    lines = ["# Cross-Sectional Momentum Report", ""]
    lines.append(df.to_string(index=False))
    lines.append("")

    if single_asset_momentum_comparison is not None and not single_asset_momentum_comparison.empty:
        lines.append("## Comparison vs Single-Asset Momentum (from main sweep)")
        cs_mean_sharpe = df["oos_sharpe"].mean() if "oos_sharpe" in df.columns else float("nan")
        sa_mean_sharpe = single_asset_momentum_comparison["oos_sharpe"].mean()
        lines.append(f"- Cross-sectional mean OOS Sharpe: {cs_mean_sharpe:.2f}")
        lines.append(f"- Single-asset momentum mean OOS Sharpe: {sa_mean_sharpe:.2f}")
        verdict = "beats" if cs_mean_sharpe > sa_mean_sharpe else "does not beat"
        lines.append(f"- Cross-sectional ranking {verdict} single-asset momentum on mean OOS Sharpe "
                      f"(reported as-is, not tuned to look good).")
        lines.append("")
        lines.append("### Drawdowns (as-is)")
        lines.append(f"- Cross-sectional worst OOS max drawdown: {df['oos_max_drawdown'].min():.2%}"
                      if "oos_max_drawdown" in df.columns else "- n/a")
        lines.append(f"- Single-asset momentum worst OOS max drawdown: "
                      f"{single_asset_momentum_comparison['oos_max_drawdown'].min():.2%}")

    md_path = out_dir / "cross_sectional_momentum_report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    return csv_path, md_path
