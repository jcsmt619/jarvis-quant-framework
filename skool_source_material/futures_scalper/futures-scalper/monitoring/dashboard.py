"""Live terminal dashboard built on rich.

Shows the things you actually watch on a futures session: where the session
clock is, the current regime and how stable it is, open contracts and their
P&L, and the two prop-firm meters that decide whether you keep the account. If
rich is unavailable it degrades to a plain text snapshot.
"""

from __future__ import annotations

from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    _RICH = True
except Exception:  # pragma: no cover
    _RICH = False


class Dashboard:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and _RICH
        self._console = Console() if _RICH else None
        self._live: Optional["Live"] = None

    def start(self) -> None:
        if self.enabled:
            self._live = Live(console=self._console, refresh_per_second=2, screen=False)
            self._live.start()

    def stop(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def render(self, state: dict) -> None:
        if not self.enabled:
            self._plain(state)
            return
        self._live.update(self._build(state))

    # -- rendering ---------------------------------------------------------
    def _build(self, s: dict):
        from rich.table import Table
        from rich.panel import Panel
        from rich.console import Group

        header = Table.grid(expand=True)
        header.add_column(justify="left")
        header.add_column(justify="right")
        session = s.get("session", "?")
        clock = s.get("clock", "")
        header.add_row(f"[bold]FUTURES SCALPER[/bold]  {s.get('symbol','')}",
                       f"session: [cyan]{session}[/cyan]  {clock}")

        regime = Table.grid(expand=True)
        regime.add_column()
        prob = s.get("regime_prob", 0.0)
        regime.add_row(
            f"regime: [bold]{s.get('regime','?')}[/bold] ({prob*100:.0f}%)   "
            f"stability: {s.get('stability',0)} bars   "
            f"flicker: {s.get('flicker',0)}")

        pos_table = Table(expand=True, show_edge=False)
        for col in ("symbol", "side", "qty", "avg", "uP&L"):
            pos_table.add_column(col)
        for p in s.get("positions", []):
            pnl = p.get("upnl", 0.0)
            color = "green" if pnl >= 0 else "red"
            pos_table.add_row(p["symbol"], p["side"], str(p["qty"]),
                              f"{p['avg']:.2f}", f"[{color}]{pnl:,.0f}[/{color}]")

        risk = Table.grid(expand=True)
        risk.add_column()
        risk.add_row(self._meter("daily loss", s.get("daily_loss", 0), s.get("daily_limit", 1)))
        risk.add_row(self._meter("trailing DD", s.get("trailing_used", 0), s.get("trailing_limit", 1)))
        equity = s.get("equity", 0.0)
        risk.add_row(f"equity: [bold]${equity:,.0f}[/bold]   "
                     f"realized today: ${s.get('realized_today',0):,.0f}   "
                     f"broker: {s.get('broker','sim')}")

        return Group(
            Panel(header, border_style="blue"),
            Panel(regime, title="regime", border_style="magenta"),
            Panel(pos_table, title="positions", border_style="white"),
            Panel(risk, title="risk / prop-firm", border_style="yellow"),
        )

    def _meter(self, label: str, used: float, limit: float) -> str:
        limit = max(limit, 1e-9)
        frac = min(1.0, abs(used) / limit)
        filled = int(frac * 20)
        color = "green" if frac < 0.5 else ("yellow" if frac < 0.8 else "red")
        bar = f"[{color}]{'#' * filled}{'.' * (20 - filled)}[/{color}]"
        return f"{label:12s} {bar} ${abs(used):,.0f}/${limit:,.0f}"

    def _plain(self, s: dict) -> None:
        print(f"[{s.get('clock','')}] {s.get('symbol','')} | {s.get('session','?')} | "
              f"regime {s.get('regime','?')} ({s.get('regime_prob',0)*100:.0f}%) | "
              f"equity ${s.get('equity',0):,.0f} | "
              f"day -${abs(s.get('daily_loss',0)):,.0f}/${s.get('daily_limit',0):,.0f}")
