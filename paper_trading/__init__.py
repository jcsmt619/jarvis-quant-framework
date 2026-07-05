"""
paper_trading package
======================
Phase 2 (dry-run signal logger) of the Alpaca Paper-Trading Gate.
See docs/ALPACA_PAPER_TRADING_GATE_SPEC.md.

This package contains NO broker connection code. It never submits an
order, paper or live. It only evaluates the approved EEM rsi_revert
(14,30/70) signal against provided price data and logs what Jarvis
WOULD do.
"""
