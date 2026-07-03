"""Mobile alerts over Telegram.

This is the piece members asked for: a ping on the phone when something happens
rather than having to watch a terminal. It uses the standard library to call the
Telegram bot API, so there is no extra dependency. If no token is configured it
quietly does nothing except log, which keeps testing and the default sim path
clean.

Setup is two steps: message @BotFather to create a bot and get a token, then put
the token and your chat id in .env as TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Optional


class TelegramNotifier:
    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        self.token = cfg.get("token") or os.getenv("TELEGRAM_TOKEN", "")
        self.chat_id = cfg.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        self.timeout = float(cfg.get("timeout", 8.0))

    def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
        }).encode()
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
                return bool(body.get("ok"))
        except Exception:
            return False

    # Convenience wrappers with consistent formatting.
    def signal(self, symbol: str, direction: str, contracts: int, entry: float,
               stop: float, target: Optional[float], regime: str) -> bool:
        tgt = f"{target:.2f}" if target else "trail"
        return self.send(
            f"\U0001F4C8 <b>{direction.upper()} {contracts} {symbol}</b>\n"
            f"entry {entry:.2f} | stop {stop:.2f} | target {tgt}\nregime: {regime}")

    def fill(self, symbol: str, direction: str, contracts: int, price: float) -> bool:
        return self.send(f"\u2705 filled {direction} {contracts} {symbol} @ {price:.2f}")

    def breaker(self, level: str, reason: str) -> bool:
        return self.send(f"\U0001F6D1 <b>{level}</b>\n{reason}")
