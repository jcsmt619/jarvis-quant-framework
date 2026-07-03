"""
Kelly Criterion Dynamic Position Sizing Module
================================================
Calculates optimal position size based on historical win rates and edge ratios.
Implements regime drift detection with instant position closure on edge collapse.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class TradeRecord:
    """Single closed trade record for Kelly calculation."""
    exit_date: datetime
    entry_price: float
    exit_price: float
    pnl: float  # Profit/Loss in currency
    pnl_pct: float  # P&L as percentage
    is_win: bool
    hold_bars: int


class KellyCriterionSizer:
    """
    Dynamic position sizing using Kelly Criterion formula:
    
    f* = (p*b - q) / b
    
    where:
        p = win rate
        q = loss rate (1 - p)
        b = ratio of average win to average loss
        
    Position Size = f* * kelly_fraction * account_equity
    """
    
    def __init__(
        self,
        lookback_window: int = 100,
        kelly_fraction: float = 0.5,
        min_sample_trades: int = 50,
        regime_drift_threshold: float = 0.40,
        regime_recovery_threshold: float = 0.50,
        min_edge_ratio: float = 1.5,
        logs_dir: Optional[Path] = None,
    ):
        """
        Parameters:
        -----------
        lookback_window : int
            Number of recent trades to consider for Kelly calculation
        kelly_fraction : float
            Conservative fraction of Kelly (e.g., 0.5 = half Kelly)
        min_sample_trades : int
            Minimum historical trades before Kelly sizing kicks in
        regime_drift_threshold : float
            Win rate below this triggers regime drift (close position)
        regime_recovery_threshold : float
            Win rate above this resumes trading after drift
        min_edge_ratio : float
            Minimum win/loss ratio required for Kelly scaling
        logs_dir : Path
            Directory for regime switch logging
        """
        self.lookback_window = lookback_window
        self.kelly_fraction = kelly_fraction
        self.min_sample_trades = min_sample_trades
        self.regime_drift_threshold = regime_drift_threshold
        self.regime_recovery_threshold = regime_recovery_threshold
        self.min_edge_ratio = min_edge_ratio
        self.logs_dir = logs_dir or Path.cwd() / "logs"
        
        self.closed_trades: list[TradeRecord] = []
        self.regime_state = "normal"  # "normal" or "drifted"
        self.regime_switches: list[dict] = []
    
    def add_trade(self, trade: TradeRecord) -> None:
        """Record a closed trade."""
        self.closed_trades.append(trade)
    
    def _calculate_statistics(self, trades: list[TradeRecord]) -> dict:
        """Calculate win rate, edge ratio, and validity."""
        if not trades:
            return {"valid": False, "reason": "No trades"}
        
        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]
        
        if not wins or not losses:
            return {
                "valid": False,
                "reason": "Insufficient win/loss mix",
                "win_count": len(wins),
                "loss_count": len(losses),
            }
        
        p = len(wins) / len(trades)
        q = 1 - p
        
        avg_win = sum(t.pnl for t in wins) / len(wins)
        avg_loss = abs(sum(t.pnl for t in losses) / len(losses))
        
        if avg_loss == 0:
            return {"valid": False, "reason": "Zero avg loss"}
        
        b = avg_win / avg_loss
        
        return {
            "valid": True,
            "win_rate": p,
            "loss_rate": q,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "edge_ratio": b,
            "num_trades": len(trades),
            "num_wins": len(wins),
            "num_losses": len(losses),
        }
    
    def _detect_regime_drift(self, recent_trades: list[TradeRecord], current_win_rate: float) -> tuple[str, Optional[str]]:
        """
        Detect regime drift by checking recent win rate against thresholds.
        
        Returns: (new_regime_state, regime_switch_reason)
        """
        recent_10 = recent_trades[-10:] if len(recent_trades) >= 10 else recent_trades
        if len(recent_10) < 5:
            return self.regime_state, None
        
        recent_win_rate = sum(1 for t in recent_10 if t.is_win) / len(recent_10)
        
        new_state = self.regime_state
        reason = None
        
        if self.regime_state == "normal" and recent_win_rate < self.regime_drift_threshold:
            new_state = "drifted"
            reason = f"Win rate collapsed to {recent_win_rate:.1%} (threshold: {self.regime_drift_threshold:.1%})"
        
        elif self.regime_state == "drifted" and recent_win_rate > self.regime_recovery_threshold:
            new_state = "normal"
            reason = f"Win rate recovered to {recent_win_rate:.1%} (threshold: {self.regime_recovery_threshold:.1%})"
        
        if new_state != self.regime_state:
            self.regime_switches.append({
                "timestamp": datetime.now().isoformat(),
                "from_state": self.regime_state,
                "to_state": new_state,
                "reason": reason,
                "recent_win_rate": recent_win_rate,
                "current_win_rate": current_win_rate,
            })
        
        return new_state, reason
    
    def calculate_position_size(self, account_equity: float) -> dict:
        """
        Calculate optimal position size based on Kelly Criterion.
        
        Returns: {
            'position_size_fraction': float,  # 0.0 to 5.0
            'kelly_full': float,
            'kelly_conservative': float,
            'regime_state': str,
            'stats': dict,
            'reason': str,
        }
        """
        # Insufficient trade history
        if len(self.closed_trades) < self.min_sample_trades:
            return {
                "position_size_fraction": 0.20,
                "regime_state": "initialization",
                "reason": f"Building trade history: {len(self.closed_trades)}/{self.min_sample_trades}",
                "stats": {"num_trades": len(self.closed_trades)},
            }
        
        # Get recent trades for calculation
        recent_trades = self.closed_trades[-self.lookback_window :]
        stats = self._calculate_statistics(recent_trades)
        
        if not stats["valid"]:
            return {
                "position_size_fraction": 0.20,
                "regime_state": "initialization",
                "reason": stats.get("reason", "Invalid trade statistics"),
                "stats": stats,
            }
        
        # Regime drift detection
        self.regime_state, drift_reason = self._detect_regime_drift(
            recent_trades, stats["win_rate"]
        )
        
        if self.regime_state == "drifted":
            return {
                "position_size_fraction": 0.0,
                "regime_state": "drifted",
                "reason": drift_reason or "Regime drift detected",
                "stats": stats,
            }
        
        # Kelly formula: f* = (p*b - q) / b
        p = stats["win_rate"]
        b = stats["edge_ratio"]
        q = stats["loss_rate"]
        
        if b < self.min_edge_ratio:
            # Edge too weak for Kelly
            return {
                "position_size_fraction": 0.20,
                "regime_state": "low_edge",
                "reason": f"Edge ratio {b:.2f}x below minimum {self.min_edge_ratio:.2f}x",
                "stats": stats,
            }
        
        kelly_full = (p * b - q) / b if b > 0 else 0.0
        kelly_conservative = kelly_full * self.kelly_fraction
        
        # Clamp to [0, 5x] leverage
        optimal_size = max(0.0, min(kelly_conservative, 5.0))
        
        return {
            "position_size_fraction": optimal_size,
            "position_size_currency": optimal_size * account_equity,
            "kelly_full": kelly_full,
            "kelly_conservative": kelly_conservative,
            "kelly_fraction_used": self.kelly_fraction,
            "regime_state": self.regime_state,
            "stats": stats,
            "reason": f"Kelly sizing: f*={kelly_full:.3f}, 50% Kelly={kelly_conservative:.3f}, clamped to {optimal_size:.3f}x",
        }
    
    def export_regime_log(self, output_path: Optional[Path] = None) -> Path:
        """Save regime switches to JSON log."""
        output_path = output_path or (self.logs_dir / "kelly_regime_switches.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        log_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_trades_recorded": len(self.closed_trades),
            "regime_switches": self.regime_switches,
            "current_regime": self.regime_state,
        }
        
        output_path.write_text(json.dumps(log_data, indent=2))
        return output_path
    
    def __repr__(self) -> str:
        return (
            f"KellyCriterionSizer("
            f"trades={len(self.closed_trades)}, "
            f"regime={self.regime_state}, "
            f"switches={len(self.regime_switches)})"
        )


if __name__ == "__main__":
    # Example usage
    from datetime import datetime, timedelta
    
    sizer = KellyCriterionSizer()
    
    # Simulate 100 trades
    for i in range(100):
        is_win = (i % 7) < 5  # 71% win rate
        pnl = 250 if is_win else -100
        pnl_pct = 0.02 if is_win else -0.01
        
        trade = TradeRecord(
            exit_date=datetime.now() - timedelta(days=100 - i),
            entry_price=100.0,
            exit_price=102.0 if is_win else 99.0,
            pnl=pnl,
            pnl_pct=pnl_pct,
            is_win=is_win,
            hold_bars=5 + i % 10,
        )
        sizer.add_trade(trade)
    
    # Calculate position size
    result = sizer.calculate_position_size(account_equity=100000)
    print(f"Position size: {result['position_size_fraction']:.3f}x")
    print(f"Regime: {result['regime_state']}")
    print(f"Reason: {result['reason']}")
    print(f"Stats: {result['stats']}")
    
    # Export log
    log_path = sizer.export_regime_log()
    print(f"\nRegime log saved to: {log_path}")
