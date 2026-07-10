from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-15"
MODULE_NAME = "Session Evidence Review Gate"
SOURCE_PHASE_ID = "BR-14"
SOURCE_MODULE_NAME = "Local Paper Research Session Runner"
DEFAULT_EVIDENCE_DIR = Path("reports/br14_local_paper_research_session_runner/manual_20260709T194500")
DEFAULT_REPORT_DIR = Path("reports/br15_session_evidence_review_gate")
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
EXPECTED_SESSION_FLOW = (
    "BR-10C",
    "BR-02",
    "BR-03",
    "BR-04",
    "BR-05",
    "BR-06",
    "BR-07",
    "BR-08",
    "BR-09",
)
REQUIRED_DISABLED_FLAGS = (
    "credential_loading_attempted",
    "broker_connection_attempted",
    "broker_read_call_performed",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "live_trading_enabled",
)
EXPECTED_ARTIFACTS = {
    "session": ("local_paper_research_session.json", "local_paper_research_session.md"),
    "screener": ("br10c_screener/config_driven_screener_pipeline.json", "br10c_screener/config_driven_screener_pipeline.md"),
    "candidate_universe": ("br02_candidate_universe/candidate_universe.json", "br02_candidate_universe/candidate_universe.md"),
    "chain_quality": ("br03_options_chain_quality/options_chain_quality.json", "br03_options_chain_quality/options_chain_quality.md"),
    "contract_scoring": ("br04_contract_scoring/options_contract_scoring.json", "br04_contract_scoring/options_contract_scoring.md"),
    "analyst_thesis": ("br05_analyst_thesis/llm_analyst_thesis_generator.json", "br05_analyst_thesis/llm_analyst_thesis_generator.md"),
    "risk_gate": ("br06_risk_gate/trade_score_risk_gate.json", "br06_risk_gate/trade_score_risk_gate.md"),
    "paper_portfolio": ("br07_paper_portfolio/paper_options_portfolio.json", "br07_paper_portfolio/paper_options_portfolio.md"),
    "position_monitor": ("br08_position_monitor/daily_position_monitor_alerts.json", "br08_position_monitor/daily_position_monitor_alerts.md"),
    "operator_dashboard": ("br09_operator_dashboard/local_operator_dashboard.json", "br09_operator_dashboard/local_operator_dashboard.md"),
}


@dataclass(frozen=True)
class EvidenceArtifactReview:
    name: str
    json_path: str
    markdown_path: str
    json_present: bool
    markdown_present: bool
    json_valid: bool
    json_error: str | None = None

    def validate(self) -> None:
        if not self.name:
            raise ValueError("artifact review requires a name")
        if self.json_present and not self.json_valid:
            raise ValueError(f"{self.name} JSON is present but invalid")


@dataclass(frozen=True)
class SessionEvidenceReviewReport:
    as_of: datetime
    evidence_dir: str
    artifact_reviews: tuple[EvidenceArtifactReview, ...]
    source_payload: dict[str, Any]
    safety: dict[str, Any]
    acceptance_criteria: dict[str, bool]
    unresolved_review_items: tuple[str, ...]
    required_human_review_actions: tuple[str, ...]
    readiness_state: str
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("session evidence review gate must require human review")
        _validate_disabled_safety(self.safety)
        for artifact_review in self.artifact_reviews:
            artifact_review.validate()
        if self.readiness_state != "BLOCKED_BY_SAFETY_GATE_HUMAN_REVIEW_REQUIRED":
            raise ValueError("session evidence review gate must remain blocked by safety gate")
        if not self.required_human_review_actions:
            raise ValueError("session evidence review gate must include required human review actions")


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "source_phase": SOURCE_PHASE_ID,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "evidence_review_only": True,
        "read_only_evidence_access": True,
        "session_rerun_attempted": False,
        "evidence_mutation_attempted": False,
        "artifact_deletion_attempted": False,
        "credential_loading_attempted": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_session_evidence_review_report(
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    as_of: datetime | None = None,
) -> SessionEvidenceReviewReport:
    evidence_dir = Path(evidence_dir)
    artifact_reviews = tuple(_review_artifact(evidence_dir, name, paths) for name, paths in EXPECTED_ARTIFACTS.items())
    source_payload = _load_json_if_valid(evidence_dir / EXPECTED_ARTIFACTS["session"][0])
    safety = safety_manifest()
    criteria = _acceptance_criteria(evidence_dir, artifact_reviews, source_payload)
    unresolved_items = _unresolved_review_items(source_payload, criteria)
    required_actions = (
        "Human reviewer must compare BR-15 report against committed BR-14 evidence before any next phase.",
        "Human reviewer must confirm all BR-14 safety flags remain disabled.",
        "Human reviewer must keep any trade-relevant interpretation labeled HUMAN_REVIEW_REQUIRED.",
        "Human reviewer must leave live trading disabled and broker order paths inactive.",
    )
    report = SessionEvidenceReviewReport(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        evidence_dir=str(evidence_dir),
        artifact_reviews=artifact_reviews,
        source_payload=source_payload,
        safety=safety,
        acceptance_criteria=criteria,
        unresolved_review_items=unresolved_items,
        required_human_review_actions=required_actions,
        readiness_state="BLOCKED_BY_SAFETY_GATE_HUMAN_REVIEW_REQUIRED",
    )
    report.validate()
    return report


def session_evidence_review_payload(report: SessionEvidenceReviewReport) -> dict[str, Any]:
    report.validate()
    source_metrics = dict(report.source_payload.get("metrics", {}))
    source_safety = dict(report.source_payload.get("safety", {}))
    artifact_presence = {
        review.name: {
            "json_path": review.json_path,
            "markdown_path": review.markdown_path,
            "json_present": review.json_present,
            "markdown_present": review.markdown_present,
            "json_valid": review.json_valid,
            "json_error": review.json_error,
        }
        for review in report.artifact_reviews
    }
    flow = tuple(report.source_payload.get("session_flow", ()))
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "source_phase": SOURCE_PHASE_ID,
        "source_module": SOURCE_MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "evidence_dir": report.evidence_dir,
        "evidence_integrity": {
            "evidence_dir_present": Path(report.evidence_dir).exists(),
            "expected_artifact_count": len(EXPECTED_ARTIFACTS),
            "json_artifacts_present": sum(1 for review in report.artifact_reviews if review.json_present),
            "markdown_artifacts_present": sum(1 for review in report.artifact_reviews if review.markdown_present),
            "json_artifacts_valid": sum(1 for review in report.artifact_reviews if review.json_valid),
            "missing_artifacts": tuple(
                review.name
                for review in report.artifact_reviews
                if not review.json_present or not review.markdown_present
            ),
            "invalid_json_artifacts": tuple(
                review.name for review in report.artifact_reviews if review.json_present and not review.json_valid
            ),
            "session_written_artifacts_empty": report.source_payload.get("written_artifacts") == {},
            "evidence_review_only": True,
        },
        "safety_manifest_review": {
            "source_safety": source_safety,
            "review_safety": report.safety,
            "required_labels_present": tuple(source_safety.get("labels", ())) == REQUIRED_LABELS,
            "disabled_flags_verified": all(source_safety.get(field_name) is False for field_name in REQUIRED_DISABLED_FLAGS),
            "live_trading_status": source_safety.get("LIVE TRADING"),
        },
        "session_metrics": source_metrics,
        "session_flow_completeness": {
            "expected_flow": EXPECTED_SESSION_FLOW,
            "observed_flow": flow,
            "complete": flow == EXPECTED_SESSION_FLOW,
        },
        "generated_artifact_presence": artifact_presence,
        "simulated_paper_contracts": tuple(report.source_payload.get("paper_contract_ids", ())),
        "monitor_alerts": tuple(report.source_payload.get("monitor_alert_ids", ())),
        "readiness_state": {
            "state": report.readiness_state,
            "ready_for_live_trading": False,
            "broker_actions_allowed": False,
            "human_review_required": True,
            "blocked_by_safety_gate": True,
        },
        "unresolved_review_items": report.unresolved_review_items,
        "acceptance_criteria": report.acceptance_criteria,
        "required_human_review_actions": report.required_human_review_actions,
        "safety": report.safety,
    }


def render_markdown_session_evidence_review(report: SessionEvidenceReviewReport) -> str:
    payload = session_evidence_review_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Evidence Integrity",
    ]
    integrity = payload["evidence_integrity"]
    lines.extend(
        [
            f"- evidence_dir_present: {integrity['evidence_dir_present']}",
            f"- expected_artifact_count: {integrity['expected_artifact_count']}",
            f"- json_artifacts_present: {integrity['json_artifacts_present']}",
            f"- markdown_artifacts_present: {integrity['markdown_artifacts_present']}",
            f"- json_artifacts_valid: {integrity['json_artifacts_valid']}",
            f"- session_written_artifacts_empty: {integrity['session_written_artifacts_empty']}",
        ]
    )

    lines.extend(["", "## Safety Manifest"])
    safety_review = payload["safety_manifest_review"]
    lines.append(f"- required_labels_present: {safety_review['required_labels_present']}")
    lines.append(f"- disabled_flags_verified: {safety_review['disabled_flags_verified']}")
    lines.append(f"- live_trading_status: {safety_review['live_trading_status']}")

    lines.extend(["", "## Session Metrics"])
    for name, value in payload["session_metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Session Flow Completeness"])
    lines.append(f"- complete: {payload['session_flow_completeness']['complete']}")
    for phase in payload["session_flow_completeness"]["observed_flow"]:
        lines.append(f"- {phase}")

    lines.extend(["", "## Generated Artifact Presence"])
    for name, artifact in payload["generated_artifact_presence"].items():
        lines.append(
            f"- {name}: json_present={artifact['json_present']}, "
            f"markdown_present={artifact['markdown_present']}, json_valid={artifact['json_valid']}"
        )

    lines.extend(["", "## Simulated Paper Contracts"])
    for contract_id in payload["simulated_paper_contracts"] or ("no_simulated_paper_contracts",):
        lines.append(f"- {contract_id}")

    lines.extend(["", "## Monitor Alerts"])
    for alert_id in payload["monitor_alerts"] or ("no_monitor_alerts",):
        lines.append(f"- {alert_id}")

    lines.extend(["", "## Readiness State"])
    readiness = payload["readiness_state"]
    lines.append(f"- state: {readiness['state']}")
    lines.append(f"- ready_for_live_trading: {readiness['ready_for_live_trading']}")
    lines.append(f"- broker_actions_allowed: {readiness['broker_actions_allowed']}")
    lines.append(f"- human_review_required: {readiness['human_review_required']}")

    lines.extend(["", "## Unresolved Review Items"])
    for item in payload["unresolved_review_items"] or ("none",):
        lines.append(f"- {item}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(["", "## Required Human Review Actions"])
    for action in payload["required_human_review_actions"]:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Evidence review only; the BR-14 session is not rerun.",
            "- No evidence mutation, artifact deletion, credential loading, broker connection, broker endpoint call, broker action, order path, or live trading enablement.",
        ]
    )
    return "\n".join(lines)


def write_session_evidence_review_report(
    report: SessionEvidenceReviewReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    report.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "session_evidence_review_gate.json"
    markdown_path = out_dir / "session_evidence_review_gate.md"
    json_path.write_text(json.dumps(session_evidence_review_payload(report), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_session_evidence_review(report), encoding="utf-8")
    return json_path, markdown_path


def run_session_evidence_review_gate(
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> SessionEvidenceReviewReport:
    report = build_session_evidence_review_report(evidence_dir=evidence_dir, as_of=as_of)
    write_session_evidence_review_report(report, out_dir=out_dir)
    return report


def _review_artifact(
    evidence_dir: Path,
    name: str,
    paths: tuple[str, str],
) -> EvidenceArtifactReview:
    json_path = evidence_dir / paths[0]
    markdown_path = evidence_dir / paths[1]
    json_valid = False
    json_error = None
    if json_path.exists():
        try:
            json.loads(json_path.read_text(encoding="utf-8"))
            json_valid = True
        except json.JSONDecodeError as exc:
            json_error = str(exc)
    return EvidenceArtifactReview(
        name=name,
        json_path=str(json_path),
        markdown_path=str(markdown_path),
        json_present=json_path.exists(),
        markdown_present=markdown_path.exists(),
        json_valid=json_valid,
        json_error=json_error,
    )


def _load_json_if_valid(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _acceptance_criteria(
    evidence_dir: Path,
    artifact_reviews: tuple[EvidenceArtifactReview, ...],
    source_payload: dict[str, Any],
) -> dict[str, bool]:
    source_safety = dict(source_payload.get("safety", {}))
    return {
        "br14_evidence_directory_present": evidence_dir.exists(),
        "expected_json_and_markdown_artifacts_present": all(
            review.json_present and review.markdown_present for review in artifact_reviews
        ),
        "expected_json_artifacts_parse": all(review.json_valid for review in artifact_reviews),
        "source_phase_is_br14": source_payload.get("phase") == SOURCE_PHASE_ID,
        "source_label_requires_human_review": source_payload.get("label") == HUMAN_REVIEW_REQUIRED,
        "source_session_flow_complete": tuple(source_payload.get("session_flow", ())) == EXPECTED_SESSION_FLOW,
        "source_metrics_present": bool(source_payload.get("metrics")),
        "source_simulated_paper_contracts_recorded": bool(source_payload.get("paper_contract_ids")),
        "source_monitor_alerts_recorded": "monitor_alert_ids" in source_payload,
        "source_required_labels_present": tuple(source_safety.get("labels", ())) == REQUIRED_LABELS,
        "source_disabled_runtime_flags_verified": all(
            source_safety.get(field_name) is False for field_name in REQUIRED_DISABLED_FLAGS
        ),
        "source_live_trading_disabled": source_safety.get("LIVE TRADING") == "DISABLED",
        "review_gate_is_evidence_review_only": True,
        "review_gate_blocks_live_trading": True,
    }


def _unresolved_review_items(
    source_payload: dict[str, Any],
    criteria: dict[str, bool],
) -> tuple[str, ...]:
    items = [f"acceptance_criterion_failed:{name}" for name, passed in criteria.items() if not passed]
    if source_payload.get("written_artifacts") == {}:
        items.append("source_written_artifacts_field_empty_review_file_presence_instead")
    items.append("human_review_required_before_next_phase")
    items.append("live_trading_remains_disabled")
    return tuple(items)


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in (
        "session_rerun_attempted",
        "evidence_mutation_attempted",
        "artifact_deletion_attempted",
        *REQUIRED_DISABLED_FLAGS,
    ):
        if manifest.get(field_name) is not False:
            raise ValueError(f"session evidence review gate cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("session evidence review gate must keep LIVE TRADING disabled")
