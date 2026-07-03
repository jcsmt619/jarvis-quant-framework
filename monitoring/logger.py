"""
monitoring/logger.py
====================
Structured JSON logging (STEP 8). Every record is one JSON object per line
(JSONL) written to a size-rotating file (10 MB, keep 5 backups). Per the
01_CLAUDE.md convention, every state entry includes:
    timestamp, regime, probability, equity, positions, daily_pnl
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"

# Structured fields promoted to top level of each JSON record.
STATE_FIELDS = ("regime", "probability", "equity", "positions", "daily_pnl")

MAX_BYTES = 10 * 1024 * 1024  # 10 MB rotation
BACKUP_COUNT = 5


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in STATE_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def get_logger(
    name: str = "trading",
    log_file: str = "trading.jsonl",
    max_bytes: int = MAX_BYTES,
    backup_count: int = BACKUP_COUNT,
) -> logging.Logger:
    """Return a singleton JSON logger with a 10 MB rotating file handler."""
    logger = logging.getLogger(name)
    if getattr(logger, "_json_configured", False):
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger._json_configured = True  # type: ignore[attr-defined]
    return logger


def log_state(
    logger: logging.Logger,
    *,
    regime: str,
    probability: float,
    equity: float,
    positions: Any,
    daily_pnl: float,
    message: str = "state",
    level: int = logging.INFO,
    **extra: Any,
) -> None:
    """Emit one structured state record with the mandated fields."""
    logger.log(
        level,
        message,
        extra={
            "regime": regime,
            "probability": probability,
            "equity": equity,
            "positions": positions,
            "daily_pnl": daily_pnl,
            "extra_fields": extra,
        },
    )
