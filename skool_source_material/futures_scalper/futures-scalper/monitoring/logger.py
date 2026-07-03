"""Structured logging. Human-readable on the console, JSON in the log files.

Four rotating files keep the noise separated: main, trades, alerts, and regime
changes. The trade and alert logs are the audit trail you review after a
session.
"""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            payload.update(record.extra_data)  # type: ignore[attr-defined]
        return json.dumps(payload, default=str)


def setup_logger(name: str = "futures_scalper", level: str = "INFO",
                 log_dir: str = "logs", json_files: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                                           datefmt="%H:%M:%S"))
    logger.addHandler(console)

    d = Path(log_dir)
    d.mkdir(parents=True, exist_ok=True)
    fmt = _JsonFormatter() if json_files else logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for fname in ("main", "trades", "alerts", "regime"):
        h = RotatingFileHandler(d / f"{fname}.log", maxBytes=10 * 1024 * 1024, backupCount=5)
        h.setFormatter(fmt)
        if fname != "main":
            h.addFilter(_NameFilter(fname))
        logger.addHandler(h)
    return logger


class _NameFilter(logging.Filter):
    def __init__(self, tag: str) -> None:
        super().__init__()
        self.tag = tag

    def filter(self, record: logging.LogRecord) -> bool:
        return getattr(record, "channel", "main") == self.tag


def log_channel(logger: logging.Logger, channel: str, msg: str, **data) -> None:
    extra = {"channel": channel}
    if data:
        extra["extra_data"] = data
    logger.info(msg, extra=extra)
