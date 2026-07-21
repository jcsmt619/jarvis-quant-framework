from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ui_service.constants import LIVE_TRADING_STATUS, READ_ENDPOINTS, SAFETY_STATE

ROOT = Path(__file__).resolve().parents[1]
UI00_FIXTURE = ROOT / "ui_contracts" / "fixtures" / "ui00_application_architecture_contract.fixture.json"
BR14_REPORT = ROOT / "reports" / "br14_local_paper_research_session_runner" / "manual_20260709T194500" / "local_paper_research_session.json"
BR26_REPORT = ROOT / "reports" / "br26_read_only_data_snapshot_import_contract" / "read_only_data_snapshot_import_contract.json"
BR29_REPORT = ROOT / "reports" / "br29_offline_snapshot_research_replay_evidence_pack" / "offline_snapshot_research_replay_evidence_pack.json"
BR30_REPORT = ROOT / "reports" / "br30_read_only_live_market_data_adapter" / "read_only_live_market_data_adapter.json"
UI03_FIXTURE = ROOT / "ui_contracts" / "fixtures" / "ui03_research_workbench.fixture.json"
UI03_MODELS = {"research", "screener", "opportunities", "analyst_theses", "market_regime", "lifecycle"}


class ReadModelSource:
    def __init__(self, source_mode: str = "fixture") -> None:
        self.source_mode = source_mode
        self._ui00 = _load_json(UI00_FIXTURE)
        self._ui03 = _load_json(UI03_FIXTURE)

    def read(self, model_name: str) -> tuple[dict[str, Any], list[str]]:
        if self.source_mode == "live_provider":
            return _unavailable(model_name, "live_provider_mode_unavailable_pending_br30_dxlink_validation"), [
                "live_provider_mode_unavailable_pending_br30_dxlink_validation"
            ]
        if model_name == "safety":
            return {"status": "disabled", **SAFETY_STATE}, []
        if model_name == "system_health":
            return self._health(), []
        if model_name == "data_status":
            return self._data_status(), []
        if model_name in READ_ENDPOINTS.values():
            return self._module(model_name), []
        return _unavailable(model_name, "read_model_unknown"), ["read_model_unknown"]

    def _health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "heartbeat_age_seconds": 0,
            "audit_ledger_status": "memory_only",
            "safety_status": LIVE_TRADING_STATUS,
            "ui_required_for_engine_operation": False,
            "is_live": False,
            "provider_validation_status": "pending",
        }

    def _data_status(self) -> dict[str, Any]:
        report = _load_json(BR30_REPORT if self.source_mode == "recorded_response" else BR26_REPORT)
        if not report:
            return _unavailable("data_status", "source_artifact_missing")
        return {
            "freshness": _pick(report, "as_of", default="unavailable"),
            "gaps": report.get("rejection_reasons", []),
            "stale_flags": ["provider_validation_pending"],
            "provenance": _safe_provenance(report),
            "source_artifacts": _source_paths(report),
            "is_live": False,
            "provider_validation_status": "pending",
            "live_trading_status": LIVE_TRADING_STATUS,
        }

    def _module(self, model_name: str) -> dict[str, Any]:
        report = _report_for_model(model_name, self.source_mode)
        contract_model = _contract_read_model(self._ui00, model_name)
        if not report and model_name not in {"portfolio", "alerts", "models", "market_regime"}:
            return _unavailable(model_name, "source_artifact_missing")
        data = {
            "read_model": model_name,
            "required_fields": contract_model.get("required_fields", []),
            "status": "available" if report or model_name in {"portfolio", "alerts", "models", "market_regime"} else "unavailable",
            "classification": "read_only",
            "summary": _summary_for(model_name, report),
            "source_artifacts": _source_paths(report),
            "is_live": False,
            "provider_validation_status": "pending",
            "live_trading_status": LIVE_TRADING_STATUS,
        }
        if model_name in UI03_MODELS:
            data["ui03"] = _ui03_for_model(self._ui03, model_name, self.source_mode)
            data["status"] = data["ui03"].get("status", data["status"])
        return data


def _contract_read_model(contract: dict[str, Any], name: str) -> dict[str, Any]:
    for item in contract.get("read_models", []):
        if item.get("name") == name:
            return item
    return {}


def _report_for_model(model_name: str, source_mode: str) -> dict[str, Any]:
    if source_mode == "recorded_response" and model_name in {"data_status", "options"}:
        return _load_json(BR30_REPORT)
    if model_name in {"research", "opportunities", "performance_analytics", "backtests"}:
        return _load_json(BR29_REPORT)
    if model_name in {"screener", "risk_gate", "portfolio", "alerts", "paper_activity", "options", "moonshot_research", "analyst_theses", "lifecycle"}:
        return _load_json(BR14_REPORT)
    return {}


def _summary_for(model_name: str, report: dict[str, Any]) -> dict[str, Any]:
    metrics = report.get("metrics", {}) if isinstance(report, dict) else {}
    readiness = report.get("readiness_state", {}) if isinstance(report, dict) else {}
    if model_name == "portfolio":
        return {"snapshot_id": "fixture-paper-read-only", "mode": "PAPER_ONLY", "positions": "redacted_count_only", "position_count": metrics.get("paper_position_count", 0)}
    if model_name == "alerts":
        return {"alert_count": metrics.get("monitor_alert_count", 0), "ack_state": "read_only_unavailable"}
    if model_name == "analyst_theses":
        return {"human_review_required": True, "thesis_count": metrics.get("analyst_prompt_package_count", 0)}
    if model_name == "risk_gate":
        return {"decision": "BLOCKED_BY_SAFETY_GATE", "blocked_reasons": report.get("block_reasons", []), "required_labels": SAFETY_STATE["labels"], "live_trading_status": LIVE_TRADING_STATUS}
    if model_name == "options":
        return {"chain_quality": "pending", "greeks": "unavailable_in_ui01_summary", "dte": "unavailable_in_ui01_summary", "iv": "unavailable_in_ui01_summary", "theta": "unavailable_in_ui01_summary"}
    if model_name == "market_regime":
        return {"regime": "unavailable", "confidence": None, "model_version": "ui01-fixture", "as_of": "unavailable"}
    return {
        "phase": report.get("phase"),
        "module": report.get("module"),
        "label": report.get("label", "HUMAN_REVIEW_REQUIRED"),
        "metrics": _safe_metrics(metrics),
        "readiness_state": readiness.get("state", "READ_ONLY_UNAVAILABLE"),
    }


def _safe_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    allowed = {}
    for key, value in metrics.items():
        if any(marker in key.lower() for marker in ("price", "return", "account")):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            allowed[key] = value
    return allowed


def _safe_provenance(report: dict[str, Any]) -> dict[str, Any]:
    evidence = report.get("evidence", {})
    return {
        "source_mode": report.get("request_mode", "fixture"),
        "schema": report.get("target_snapshot_schema_name") or report.get("schema", {}).get("snapshot_version"),
        "provider_name": evidence.get("provider_name", "pending"),
        "quality_state": "pending",
    }


def _source_paths(report: dict[str, Any]) -> list[str]:
    if not report:
        return []
    paths = report.get("source_paths")
    if isinstance(paths, dict):
        return list(paths.values())
    path = report.get("evidence", {}).get("raw_path")
    return [path] if path else []


def _unavailable(model_name: str, reason: str) -> dict[str, Any]:
    return {
        "read_model": model_name,
        "status": "unavailable",
        "reason": reason,
        "is_live": False,
        "provider_validation_status": "pending",
        "live_trading_status": LIVE_TRADING_STATUS,
    }


def _ui03_for_model(payload: dict[str, Any], model_name: str, source_mode: str) -> dict[str, Any]:
    if not payload:
        return {"status": "unavailable", "reason": "ui03_fixture_missing", "is_live": False, "live_trading_status": LIVE_TRADING_STATUS}
    common = {
        "schema_version": payload.get("schema_version", "ui03.research_workbench.view_model.v1"),
        "source_mode": source_mode,
        "provider_validation_status": "pending",
        "is_live": False,
        "live_trading_status": LIVE_TRADING_STATUS,
        "generated_at": payload.get("generated_at", "unavailable"),
        "observation_time": payload.get("observation_time", "unavailable"),
        "freshness": payload.get("freshness", {"state": "unavailable"}),
        "provenance": payload.get("provenance", {}),
        "safety_labels": SAFETY_STATE["labels"],
        "status": "available",
    }
    if model_name == "research":
        return {**common, "research": payload.get("research", {}), "candidates": payload.get("candidates", [])[:3]}
    if model_name == "screener":
        return {**common, "candidates": payload.get("candidates", [])[:25]}
    if model_name == "opportunities":
        return {**common, "opportunities": payload.get("candidates", [])[:25]}
    if model_name == "analyst_theses":
        return {**common, "theses": payload.get("theses", [])[:25], "candidates": payload.get("candidates", [])[:25]}
    if model_name == "market_regime":
        regime = payload.get("market_regime", {})
        return {**common, "status": regime.get("status", "unavailable"), "market_regime": regime}
    if model_name == "lifecycle":
        return {**common, "lifecycle": payload.get("lifecycle", {}), "candidates": payload.get("candidates", [])[:25]}
    return {**common, "status": "unavailable", "reason": "ui03_model_unknown"}


def _pick(payload: dict[str, Any], key: str, *, default: Any = None) -> Any:
    return payload.get(key, default)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
