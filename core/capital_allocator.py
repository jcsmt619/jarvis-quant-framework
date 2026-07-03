"""
core/capital_allocator.py
=========================
Decides what FRACTION of trading capital each enabled strategy receives. It runs
on a schedule (default weekly) and only sets capital limits -- it never overrides
a strategy's own trade decisions. Strategies converge to their new budget via
their normal rebalance logic.

Approaches (config-selectable, default inverse_vol):
  * equal_weight          - 1/N
  * inverse_vol           - naive risk parity: w_i = (1/vol_i)/sum(1/vol_j)
  * risk_parity           - equalize marginal contribution to variance (scipy)
  * performance_weighted  - w_i = max(sharpe_i,0)/sum(...); equal-weight fallback

Layered on top of every approach:
  * Correlation merge   - pairs with 60d corr > 0.8 are treated as ONE strategy
                          for weighting (they aren't actually diversified).
  * Constraints         - per-strategy weight_min/weight_max, weights sum to 1.
  * Reserve             - a cash reserve (default 10%) is always held back.
  * Kill switch         - portfolio daily DD >2% halves all; >3% zeros all.
                          Fires on TOTAL portfolio P&L (defense in depth).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "config" / "settings.yaml"


@dataclass
class AllocatorConfig:
    approach: str = "inverse_vol"       # equal_weight|inverse_vol|risk_parity|performance_weighted
    reserve: float = 0.10               # cash always held back
    vol_window: int = 60
    corr_window: int = 60
    corr_merge_threshold: float = 0.80
    rebalance_threshold: float = 0.05   # min abs weight change to act
    daily_dd_halve: float = 0.02        # kill switch: halve all
    daily_dd_zero: float = 0.03         # kill switch: zero all
    rebalance_weekday: int = 6          # Sunday (Mon=0 .. Sun=6)

    @classmethod
    def from_settings(cls, path: Path | str | None = None) -> "AllocatorConfig":
        path = Path(path) if path else SETTINGS
        try:
            import yaml
            data = (yaml.safe_load(path.read_text()) or {}).get("allocator", {})
        except Exception:
            return cls()
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class AllocationChange:
    strategy_name: str
    old_weight: float
    new_weight: float
    old_capital: float
    new_capital: float
    reason: str


@dataclass
class PortfolioSnapshot:
    total_capital: float = 100000.0
    daily_drawdown: float = 0.0         # positive fraction, e.g. 0.025 == 2.5%
    daily_pnl: float = 0.0


class CapitalAllocator:
    def __init__(self, registry, config: AllocatorConfig | None = None, total_capital: float = 100000.0):
        self.registry = registry
        self.config = config or AllocatorConfig()
        self.total_capital = total_capital
        try:
            from monitoring.logger import get_logger
            self._log = get_logger("allocator", log_file="allocator.jsonl")
        except Exception:  # pragma: no cover
            self._log = logging.getLogger("allocator")
        self._last_merges: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Return data
    # ------------------------------------------------------------------
    def _active_names(self) -> list[str]:
        return list(self.registry.active().keys())

    def _returns_frame(self, names: list[str]) -> pd.DataFrame | None:
        series = {}
        for n in names:
            hist = list(self.registry.get(n).performance_history)[-self.config.corr_window:]
            series[n] = hist
        min_len = min((len(v) for v in series.values()), default=0)
        if min_len < 2:
            return None
        aligned = {n: v[-min_len:] for n, v in series.items()}
        return pd.DataFrame(aligned)

    # ------------------------------------------------------------------
    # Correlation
    # ------------------------------------------------------------------
    def compute_correlation_matrix(self) -> pd.DataFrame:
        names = self._active_names()
        frame = self._returns_frame(names)
        if frame is None or frame.shape[1] < 2:
            return pd.DataFrame(index=names, columns=names, dtype=float)
        return frame.corr()

    def should_merge_correlated_strategies(self) -> list[tuple[str, str]]:
        names = self._active_names()
        corr = self.compute_correlation_matrix()
        merges: list[tuple[str, str]] = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                if a in corr.index and b in corr.columns:
                    c = corr.loc[a, b]
                    if pd.notna(c) and c > self.config.corr_merge_threshold:
                        merges.append((a, b))
                        self._log.warning(
                            "correlation merge",
                            extra={"extra_fields": {"pair": [a, b], "corr": round(float(c), 4)}},
                        )
        self._last_merges = merges
        return merges

    @staticmethod
    def _connected_groups(names: list[str], pairs: list[tuple[str, str]]) -> list[list[str]]:
        parent = {n: n for n in names}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b in pairs:
            if a in parent and b in parent:
                parent[find(a)] = find(b)
        groups: dict[str, list[str]] = {}
        for n in names:
            groups.setdefault(find(n), []).append(n)
        return list(groups.values())

    # ------------------------------------------------------------------
    # Weighting
    # ------------------------------------------------------------------
    def _group_weights(self, groups: list[list[str]], frame: pd.DataFrame | None) -> np.ndarray:
        g = len(groups)
        approach = self.config.approach

        if approach == "equal_weight" or frame is None:
            return np.ones(g) / g

        # Representative return series per group (mean of members).
        reps = pd.DataFrame({idx: frame[grp].mean(axis=1) for idx, grp in enumerate(groups)})

        if approach == "inverse_vol":
            vols = reps.std().to_numpy()
            inv = np.where(vols > 1e-12, 1.0 / vols, 0.0)
            return inv / inv.sum() if inv.sum() > 0 else np.ones(g) / g

        if approach == "performance_weighted":
            sharpes = []
            for grp in groups:
                s = np.mean([self.registry.get(n).get_recent_sharpe(self.config.vol_window) for n in grp])
                sharpes.append(max(s, 0.0))
            arr = np.array(sharpes)
            return arr / arr.sum() if arr.sum() > 0 else np.ones(g) / g  # fallback: equal

        if approach == "risk_parity":
            return self._risk_parity_weights(reps.cov().to_numpy())

        return np.ones(g) / g

    @staticmethod
    def _risk_parity_weights(cov: np.ndarray) -> np.ndarray:
        n = cov.shape[0]
        if n == 1:
            return np.ones(1)
        vols = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
        w0 = (1.0 / vols)
        w0 = w0 / w0.sum()          # inverse-vol start (already near risk parity)
        try:
            from scipy.optimize import minimize

            def objective(w: np.ndarray) -> float:
                port_var = float(w @ cov @ w)
                if port_var <= 1e-18:
                    return 0.0
                rc = w * (cov @ w) / port_var          # fractional risk contributions (sum=1)
                return float(np.sum((rc - 1.0 / n) ** 2))

            res = minimize(
                objective, w0, method="SLSQP",
                bounds=[(1e-6, 1.0)] * n,
                constraints={"type": "eq", "fun": lambda w: w.sum() - 1.0},
                options={"maxiter": 500, "ftol": 1e-12},
            )
            w = res.x if res.success else w0
        except Exception:  # scipy missing / solver failure -> inverse vol
            w = w0
        w = np.clip(w, 0.0, None)
        return w / w.sum() if w.sum() > 0 else np.ones(n) / n

    def _apply_constraints(self, weights: dict[str, float]) -> tuple[dict[str, float], list[str]]:
        mins = {n: self.registry.get(n).weight_min for n in weights}
        maxs = {n: self.registry.get(n).weight_max for n in weights}
        w = dict(weights)
        clipped: set[str] = set()
        for _ in range(100):
            for n in w:
                lo, hi = mins[n], maxs[n]
                cv = min(max(w[n], lo), hi)
                if cv != w[n]:
                    clipped.add(n)
                w[n] = cv
            total = sum(w.values())
            if abs(total - 1.0) < 1e-9:
                break
            free = [n for n in w if mins[n] < w[n] < maxs[n]]
            if not free:
                break
            deficit = 1.0 - total
            free_total = sum(w[n] for n in free) or float(len(free))
            for n in free:
                share = (w[n] / free_total) if free_total else (1.0 / len(free))
                w[n] += deficit * share
        total = sum(w.values())
        if total > 0:
            w = {n: v / total for n, v in w.items()}
        return w, sorted(clipped)

    def allocate(self) -> dict[str, float]:
        """Target weights (summing to 1) over enabled strategies."""
        names = self._active_names()
        if not names:
            return {}
        frame = self._returns_frame(names)
        pairs = self.should_merge_correlated_strategies()
        groups = self._connected_groups(names, pairs)
        gw = self._group_weights(groups, frame)

        weights: dict[str, float] = {}
        for grp, w in zip(groups, gw):
            per = float(w) / len(grp)          # split a merged group's weight evenly
            for n in grp:
                weights[n] = per

        constrained, clipped = self._apply_constraints(weights)
        self._log.info(
            "allocate",
            extra={"extra_fields": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "approach": self.config.approach,
                "computed_weights": {k: round(v, 4) for k, v in weights.items()},
                "correlation_adjustments": [list(p) for p in pairs],
                "constraints_applied": clipped,
                "final_weights": {k: round(v, 4) for k, v in constrained.items()},
            }},
        )
        return constrained

    # ------------------------------------------------------------------
    # Rebalance
    # ------------------------------------------------------------------
    def is_rebalance_day(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now.weekday() == self.config.rebalance_weekday

    def rebalance(self, registry, portfolio_state: PortfolioSnapshot) -> list[AllocationChange]:
        self.registry = registry
        total = getattr(portfolio_state, "total_capital", self.total_capital)
        daily_dd = getattr(portfolio_state, "daily_drawdown", 0.0)

        target = self.allocate()
        trading_fraction = 1.0 - self.config.reserve

        kill_mult, kill_reason = 1.0, ""
        if daily_dd > self.config.daily_dd_zero:
            kill_mult, kill_reason = 0.0, f"KILL SWITCH: daily DD {daily_dd:.2%} > {self.config.daily_dd_zero:.0%} -> 0%"
        elif daily_dd > self.config.daily_dd_halve:
            kill_mult, kill_reason = 0.5, f"KILL SWITCH: daily DD {daily_dd:.2%} > {self.config.daily_dd_halve:.0%} -> 50%"

        changes: list[AllocationChange] = []
        for name, strat in self.registry.all().items():
            old_cap = strat.allocated_capital
            old_w = (old_cap / total) if total else 0.0
            new_w = target.get(name, 0.0) * trading_fraction * kill_mult
            new_cap = new_w * total
            if abs(new_w - old_w) > self.config.rebalance_threshold or (kill_mult < 1.0 and old_w > 0):
                strat.allocated_capital = new_cap
                changes.append(AllocationChange(
                    strategy_name=name, old_weight=old_w, new_weight=new_w,
                    old_capital=old_cap, new_capital=new_cap,
                    reason=kill_reason or f"{self.config.approach} rebalance",
                ))

        self._log.info(
            "rebalance",
            extra={"extra_fields": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kill_switch": kill_reason or None,
                "reserve": self.config.reserve,
                "changes": [c.__dict__ for c in changes],
            }},
        )
        return changes
