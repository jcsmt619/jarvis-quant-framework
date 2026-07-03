"""
monitoring/dashboard.py
=======================
Terminal dashboard (STEP 8) rendered with `rich`, tuned for the Hyper-Alpha
architecture. It reflects the AGGRESSIVE live parameters (4.0x max leverage,
6% daily / 25% peak circuit breakers) pulled straight from config/settings.yaml
via the RiskManager limits, not the conservative course defaults.

Panels:
  * REGIME (HMM Brain)      — regime label, RISK-ON/OFF, stability, vol level
  * PERFORMANCE             — equity, daily P&L, gross allocation, leverage x/4.0x
  * POSITIONS (Hyper-Vel.)  — per-position side / price / P&L / stop
  * RISK STATUS (Breakers)  — daily & peak drawdown vs their hard limits
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.risk_manager import RiskLimits


@dataclass
class Position:
    symbol: str
    side: str          # "LONG" / "SHORT"
    price: float
    pnl_pct: float
    stop: float


@dataclass
class StrategyAllocation:
    name: str
    weight_pct: float          # 0-100
    sharpe: float
    status: str                # "Healthy" | "Watch" | "Disabled"


@dataclass
class DashboardState:
    # Regime
    regime_label: str = "NEUTRAL"
    risk_on: bool = False
    stability_bars: int = 0
    vol_level: str = "Mid"
    # Performance
    equity: float = 100000.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    allocation_pct: float = 0.0     # gross exposure % of equity (can exceed 100)
    leverage: float = 0.0
    # Positions
    positions: list[Position] = field(default_factory=list)
    # Risk (drawdowns as positive fractions, e.g. 0.012 == 1.2%)
    daily_dd: float = 0.0
    peak_dd: float = 0.0
    # Multi-strategy allocations (empty in single-strategy mode)
    strategy_rows: list[StrategyAllocation] = field(default_factory=list)
    cash_reserve_pct: float = 0.0


def _limits() -> RiskLimits:
    return RiskLimits.from_settings()


def _bar(value: float, limit: float, width: int = 22) -> str:
    frac = 0.0 if limit <= 0 else min(max(value / limit, 0.0), 1.0)
    filled = int(round(frac * width))
    return "[" + "=" * filled + " " * (width - filled) + "]"


def _dd_color(value: float, limit: float) -> str:
    if limit <= 0:
        return "green"
    frac = value / limit
    return "green" if frac < 0.5 else ("yellow" if frac < 0.85 else "red")


def _lev_color(leverage: float, max_lev: float) -> str:
    if leverage >= max_lev * 0.95:
        return "red"
    if leverage >= max_lev * 0.75:
        return "yellow"
    return "green"


def _regime_panel(state: DashboardState) -> Panel:
    tag = "RISK ON (Hyper)" if state.risk_on else "RISK OFF (Cash)"
    color = "bold green" if state.risk_on else "bold red"
    body = Text.assemble(
        (f"{state.regime_label}  ", "bold cyan"),
        (f"[{tag}]", color),
        (f"   Stability: {state.stability_bars} bars", "white"),
        (f"   Vol: {state.vol_level}", "white"),
    )
    return Panel(body, title="REGIME (HMM Brain)", border_style="cyan")


def _performance_panel(state: DashboardState) -> Panel:
    lim = _limits()
    max_lev = lim.max_leverage
    pnl_color = "green" if state.daily_pnl >= 0 else "red"
    sign = "+" if state.daily_pnl >= 0 else "-"
    lev_col = _lev_color(state.leverage, max_lev)
    body = Text.assemble(
        ("Equity: ", "white"), (f"${state.equity:,.0f}", "bold white"),
        ("    Daily: ", "white"),
        (f"{sign}${abs(state.daily_pnl):,.0f} ({state.daily_pnl_pct:+.1f}%)", pnl_color),
        ("\nAlloc:  ", "white"), (f"{state.allocation_pct:.0f}%", "bold white"),
        ("      Leverage: ", "white"),
        (f"{state.leverage:.1f}x / {max_lev:.1f}x", f"bold {lev_col}"),
    )
    return Panel(body, title="PERFORMANCE (Hyper-Alpha)", border_style="magenta")


def _positions_panel(state: DashboardState) -> Panel:
    table = Table(expand=True, show_edge=False, header_style="bold")
    table.add_column("Symbol")
    table.add_column("Side")
    table.add_column("Price", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("Stop", justify="right")
    if not state.positions:
        table.add_row("—", "FLAT", "—", "—", "—")
    for p in state.positions:
        side_col = "green" if p.side.upper() == "LONG" else "red"
        pnl_col = "green" if p.pnl_pct >= 0 else "red"
        table.add_row(
            p.symbol, Text(p.side.upper(), style=side_col), f"${p.price:,.2f}",
            Text(f"{p.pnl_pct:+.1f}%", style=pnl_col), f"${p.stop:,.2f}",
        )
    high_beta = any(p.symbol.upper() in {"SOXL", "TQQQ"} for p in state.positions)
    if high_beta:
        table.caption = "(Stop widened for 3x Volatility Tolerance)"
        table.caption_style = "italic dim"
    return Panel(table, title="POSITIONS (Hyper-Velocity)", border_style="yellow")


def _risk_panel(state: DashboardState) -> Panel:
    lim = _limits()
    daily_limit = lim.daily_dd_halt      # 6%
    peak_limit = lim.peak_dd_lock        # 25%
    d_col = _dd_color(state.daily_dd, daily_limit)
    p_col = _dd_color(state.peak_dd, peak_limit)
    body = Text.assemble(
        ("Daily DD: ", "white"),
        (f"{state.daily_dd * 100:4.1f}% / {daily_limit * 100:.1f}%  ", d_col),
        (f"{_bar(state.daily_dd, daily_limit)}", d_col),
        ("\nPeak  DD: ", "white"),
        (f"{state.peak_dd * 100:4.1f}% / {peak_limit * 100:.0f}%   ", p_col),
        (f"{_bar(state.peak_dd, peak_limit)}", p_col),
    )
    return Panel(body, title="RISK STATUS (Circuit Breakers)", border_style="red")


def _status_style(status: str) -> tuple[str, str]:
    """(display_label, rich_style) for a strategy health status."""
    s = status.lower()
    if s.startswith("health"):
        return "Healthy \u2705", "green"
    if s.startswith("disab"):
        return "Disabled \u26d4", "red"
    return "Watch \u26a0\ufe0f", "yellow"


def _multistrat_panel(state: DashboardState) -> Panel:
    table = Table(expand=True, show_edge=False, header_style="bold")
    table.add_column("Strategy")
    table.add_column("Weight", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Health", justify="right")
    for row in state.strategy_rows:
        label, style = _status_style(row.status)
        sharpe_col = "green" if row.sharpe >= 0 else "red"
        table.add_row(
            row.name,
            f"{row.weight_pct:.0f}%",
            Text(f"{row.sharpe:+.1f}", style=sharpe_col),
            Text(label, style=style),
        )
    table.add_row(
        Text("Cash Reserve", style="dim"),
        Text(f"{state.cash_reserve_pct:.0f}%", style="dim"),
        "", "",
    )
    return Panel(table, title="MULTI-STRAT ALLOCATIONS", border_style="blue")


def render_dashboard(state: DashboardState) -> Group:
    """Build the full dashboard as a rich renderable."""
    panels = [
        _regime_panel(state),
        _performance_panel(state),
        _positions_panel(state),
        _risk_panel(state),
    ]
    if state.strategy_rows:
        panels.append(_multistrat_panel(state))
    return Group(*panels)
