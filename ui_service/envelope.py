from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from ui_service.constants import (
    LIVE_TRADING_STATUS,
    MAX_CORRELATION_ID_BYTES,
    MAX_JSON_BYTES,
    PROVIDER_VALIDATION_PENDING,
    SAFETY_STATE,
    SCHEMA_VERSION,
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def normalize_correlation_id(value: str | None) -> tuple[str | None, str | None]:
    if value is None or value == "":
        return f"corr-{uuid.uuid4().hex}", None
    if len(value.encode("utf-8")) > MAX_CORRELATION_ID_BYTES or not _SAFE_ID.match(value):
        return None, "malformed_or_oversized_correlation_id"
    return value, None


def response_envelope(
    *,
    request_id: str,
    correlation_id: str,
    source_mode: str,
    data: Any,
    warnings: list[str] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "correlation_id": correlation_id,
        "generated_at": utc_now(),
        "source_mode": source_mode,
        "provider_validation_status": PROVIDER_VALIDATION_PENDING,
        "safety_state": dict(SAFETY_STATE),
        "data": data,
        "warnings": warnings or [],
        "errors": errors or [],
    }
    if _json_size(envelope) <= MAX_JSON_BYTES:
        return envelope
    envelope["data"] = {
        "status": "unavailable",
        "reason": "bounded_output_limit_exceeded",
        "is_live": False,
        "live_trading_status": LIVE_TRADING_STATUS,
    }
    envelope["warnings"] = [*envelope["warnings"], "bounded_output_limit_exceeded"]
    return envelope


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_size(payload: dict[str, Any]) -> int:
    return len(json_bytes(payload))
