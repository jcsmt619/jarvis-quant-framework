"""BR-13 Brendan full system integration audit contracts.

This module is a static, deterministic audit of research-only interfaces. It
does not run broker sync, load credentials, construct broker clients, route
orders, submit orders, or enable live trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from broker import account_sync_design
from broker import human_approved_execution_safety_design
from engines.moonshot.deterministic import br10c_config_driven_screener_pipeline
from engines.moonshot.deterministic import candidate_universe_builder
from engines.moonshot.deterministic import daily_position_monitor_alert_engine
from engines.moonshot.deterministic import llm_analyst_thesis_generator
from engines.moonshot.deterministic import local_operator_dashboard
from engines.moonshot.deterministic import options_chain_quality_scanner
from engines.moonshot.deterministic import options_contract_scorer
from engines.moonshot.deterministic import paper_autopilot_loop
from engines.moonshot.deterministic import paper_options_portfolio_manager
from engines.moonshot.deterministic import trade_score_risk_gate
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-13"
MODULE_NAME = "Brendan Full System Integration Audit"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
REQUIRED_DISABLED_FLAGS = (
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "live_trading_enabled",
)


@dataclass(frozen=True)
class IntegrationComponent:
    phase: str
    module: str
    pathway: str
    interface_kind: str
    manifest: dict[str, Any]

    def validate(self) -> None:
        _require_text("phase", self.phase)
        _require_text("module", self.module)
        if self.pathway not in {"deterministic", "non_deterministic_analyst", "safety_design"}:
            raise ValueError("BR-13 component pathway is not recognized")
        _require_text("interface_kind", self.interface_kind)
        _validate_manifest_safety(self.manifest, f"{self.phase} {self.module}")


@dataclass(frozen=True)
class IntegrationHandoff:
    name: str
    source_phase: str
    target_phase: str
    deterministic_interface: str
    expected_label: str
    human_review_required: bool
    broker_boundary: str

    def validate(self, component_phases: tuple[str, ...]) -> None:
        _require_text("handoff name", self.name)
        if self.source_phase not in component_phases:
            raise ValueError("BR-13 handoff source phase is not registered")
        if self.target_phase not in component_phases:
            raise ValueError("BR-13 handoff target phase is not registered")
        _require_text("deterministic_interface", self.deterministic_interface)
        _require_safe_label(self.expected_label)
        if not self.human_review_required:
            raise ValueError("BR-13 trade-relevant handoffs must require human review")
        if self.broker_boundary not in {
            "none",
            "read_only_design_only",
            "human_approved_design_only",
        }:
            raise ValueError("BR-13 handoff broker boundary is not recognized")


@dataclass(frozen=True)
class IntegrationAuditReport:
    phase: str
    module: str
    labels: tuple[str, ...]
    components: tuple[IntegrationComponent, ...]
    handoffs: tuple[IntegrationHandoff, ...]
    safety: dict[str, Any]
    decision: str = "INTEGRATION_AUDIT_COMPLETE_RESEARCH_ONLY"
    live_trading_status: str = "LIVE TRADING: DISABLED"

    def validate(self) -> None:
        if self.phase != PHASE_ID:
            raise ValueError("BR-13 audit report has wrong phase")
        if self.labels != REQUIRED_LABELS:
            raise ValueError("BR-13 audit report must preserve required labels")
        if not self.components:
            raise ValueError("BR-13 audit report requires components")
        if not self.handoffs:
            raise ValueError("BR-13 audit report requires handoffs")
        phases = tuple(component.phase for component in self.components)
        if len(phases) != len(set(phases)):
            raise ValueError("BR-13 component phases must be unique")
        for component in self.components:
            component.validate()
        for handoff in self.handoffs:
            handoff.validate(phases)
        _validate_manifest_safety(self.safety, "BR-13 audit")
        if self.live_trading_status != "LIVE TRADING: DISABLED":
            raise ValueError("BR-13 must keep live trading disabled")


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "blocked_by_safety_gate": True,
        "integration_audit_only": True,
        "conceptual_connectivity_verified": True,
        "deterministic_interfaces_verified": True,
        "read_only_broker_sync_design_only": True,
        "human_approved_safety_design_only": True,
        "credential_loading_required": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "account_state_imported": False,
        "manual_confirmations_recorded": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def default_components() -> tuple[IntegrationComponent, ...]:
    entries: tuple[tuple[str, str, str, Callable[[], dict[str, Any]]], ...] = (
        ("BR-10C", "deterministic", "track_b_screener_report", br10c_config_driven_screener_pipeline.safety_manifest),
        ("BR-02", "deterministic", "candidate_universe_report", candidate_universe_builder.safety_manifest),
        ("BR-03", "deterministic", "options_chain_quality_report", options_chain_quality_scanner.safety_manifest),
        ("BR-04", "deterministic", "contract_scoring_report", options_contract_scorer.safety_manifest),
        ("BR-05", "non_deterministic_analyst", "prompt_package_and_thesis_report", llm_analyst_thesis_generator.safety_manifest),
        ("BR-06", "deterministic", "trade_score_risk_gate_report", trade_score_risk_gate.safety_manifest),
        ("BR-07", "deterministic", "paper_options_portfolio_report", paper_options_portfolio_manager.safety_manifest),
        ("BR-08", "deterministic", "daily_position_monitor_report", daily_position_monitor_alert_engine.safety_manifest),
        ("BR-09", "deterministic", "local_operator_dashboard_report", local_operator_dashboard.safety_manifest),
        ("BR-10", "deterministic", "paper_autopilot_loop_report", paper_autopilot_loop.safety_manifest),
        ("BR-11", "safety_design", "read_only_broker_account_sync_design", account_sync_design.safety_manifest),
        (
            "BR-12",
            "safety_design",
            "human_approved_execution_safety_design",
            human_approved_execution_safety_design.safety_manifest,
        ),
    )
    return tuple(
        IntegrationComponent(
            phase=phase,
            module=str(manifest_fn()["module"]),
            pathway=pathway,
            interface_kind=interface_kind,
            manifest=manifest_fn(),
        )
        for phase, pathway, interface_kind, manifest_fn in entries
    )


def default_handoffs() -> tuple[IntegrationHandoff, ...]:
    return (
        IntegrationHandoff(
            name="track_b_screener_to_candidate_universe",
            source_phase="BR-10C",
            target_phase="BR-02",
            deterministic_interface="research_queue_symbols_to_candidate_inputs",
            expected_label=HUMAN_REVIEW_REQUIRED,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="candidate_universe_to_chain_quality",
            source_phase="BR-02",
            target_phase="BR-03",
            deterministic_interface="included_candidate_symbols_to_local_option_chain_inputs",
            expected_label=MONITOR_ONLY,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="chain_quality_to_contract_scoring",
            source_phase="BR-03",
            target_phase="BR-04",
            deterministic_interface="quality_checked_option_chains_to_contract_score_decisions",
            expected_label=MONITOR_ONLY,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="contract_scoring_to_llm_thesis",
            source_phase="BR-04",
            target_phase="BR-05",
            deterministic_interface="suitable_contracts_to_source_grounded_prompt_packages",
            expected_label=HUMAN_REVIEW_REQUIRED,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="llm_thesis_to_risk_gate",
            source_phase="BR-05",
            target_phase="BR-06",
            deterministic_interface="parsed_thesis_records_to_trade_score_risk_gate_context",
            expected_label=HUMAN_REVIEW_REQUIRED,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="risk_gate_to_paper_portfolio",
            source_phase="BR-06",
            target_phase="BR-07",
            deterministic_interface="paper_only_gate_decisions_to_simulated_fills_and_local_marks",
            expected_label=PAPER_ONLY,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="paper_portfolio_to_monitor",
            source_phase="BR-07",
            target_phase="BR-08",
            deterministic_interface="paper_positions_to_daily_monitor_snapshots_and_alerts",
            expected_label=MONITOR_ONLY,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="monitor_to_dashboard",
            source_phase="BR-08",
            target_phase="BR-09",
            deterministic_interface="alerts_positions_thesis_and_scores_to_static_dashboard_rows",
            expected_label=HUMAN_REVIEW_REQUIRED,
            human_review_required=True,
            broker_boundary="none",
        ),
        IntegrationHandoff(
            name="dashboard_to_read_only_broker_sync_design",
            source_phase="BR-09",
            target_phase="BR-11",
            deterministic_interface="dashboard_reconciliation_needs_to_read_only_snapshot_schema",
            expected_label=MONITOR_ONLY,
            human_review_required=True,
            broker_boundary="read_only_design_only",
        ),
        IntegrationHandoff(
            name="risk_gate_and_dashboard_to_human_approved_safety_design",
            source_phase="BR-09",
            target_phase="BR-12",
            deterministic_interface="trade_relevant_dashboard_context_to_approval_gate_design",
            expected_label=HUMAN_REVIEW_REQUIRED,
            human_review_required=True,
            broker_boundary="human_approved_design_only",
        ),
        IntegrationHandoff(
            name="paper_autopilot_loop_to_full_audit",
            source_phase="BR-10",
            target_phase="BR-13",
            deterministic_interface="local_paper_workflow_manifest_to_integration_audit",
            expected_label=PAPER_ONLY,
            human_review_required=True,
            broker_boundary="none",
        ),
    )


def build_integration_audit_report() -> IntegrationAuditReport:
    report = IntegrationAuditReport(
        phase=PHASE_ID,
        module=MODULE_NAME,
        labels=REQUIRED_LABELS,
        components=default_components() + (
            IntegrationComponent(
                phase=PHASE_ID,
                module=MODULE_NAME,
                pathway="deterministic",
                interface_kind="integration_audit_report",
                manifest=safety_manifest(),
            ),
        ),
        handoffs=default_handoffs(),
        safety=safety_manifest(),
    )
    report.validate()
    return report


def integration_audit_payload(report: IntegrationAuditReport) -> dict[str, Any]:
    report.validate()
    return {
        "phase": report.phase,
        "module": report.module,
        "labels": report.labels,
        "decision": report.decision,
        "live_trading_status": report.live_trading_status,
        "metrics": {
            "component_count": len(report.components),
            "handoff_count": len(report.handoffs),
            "human_review_required_handoff_count": len(
                tuple(handoff for handoff in report.handoffs if handoff.human_review_required)
            ),
            "disabled_component_count": len(tuple(component for component in report.components if _manifest_disabled(component.manifest))),
        },
        "components": [
            {
                "phase": component.phase,
                "module": component.module,
                "pathway": component.pathway,
                "interface_kind": component.interface_kind,
                "live_trading_enabled": component.manifest.get("live_trading_enabled"),
                "broker_order_call_performed": component.manifest.get("broker_order_call_performed"),
                "live_trading_status": "LIVE TRADING: " + str(component.manifest.get("LIVE TRADING")),
            }
            for component in report.components
        ],
        "handoffs": [
            {
                "name": handoff.name,
                "source_phase": handoff.source_phase,
                "target_phase": handoff.target_phase,
                "deterministic_interface": handoff.deterministic_interface,
                "expected_label": handoff.expected_label,
                "human_review_required": handoff.human_review_required,
                "broker_boundary": handoff.broker_boundary,
            }
            for handoff in report.handoffs
        ],
        "safety": report.safety,
    }


def runtime_notes(report: IntegrationAuditReport) -> tuple[str, ...]:
    report.validate()
    return (
        f"br13_component_count={len(report.components)}",
        f"br13_handoff_count={len(report.handoffs)}",
        "conceptual_connectivity_verified=true",
        "deterministic_interfaces_verified=true",
        "credential_loading_required=false",
        "broker_connection_attempted=false",
        "broker_read_call_performed=false",
        "broker_order_call_performed=false",
        "broker_order_submitted=false",
        "broker_order_routing_enabled=false",
        "live_trading_enabled=false",
        report.live_trading_status,
        f"br13_decision={report.decision}",
    )


def _validate_manifest_safety(manifest: dict[str, Any], owner: str) -> None:
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError(f"{owner} must keep LIVE TRADING disabled")
    if manifest.get("live_trading_enabled") is not False:
        raise ValueError(f"{owner} cannot enable live trading")
    if manifest.get("broker_order_call_performed") is not False:
        raise ValueError(f"{owner} cannot perform broker order calls")
    for field_name in REQUIRED_DISABLED_FLAGS:
        if field_name in manifest and manifest[field_name] is not False:
            raise ValueError(f"{owner} cannot set {field_name}")
    labels = tuple(manifest.get("labels", ()))
    if not labels:
        raise ValueError(f"{owner} must expose safety labels")
    for label in labels:
        _require_safe_label(label)


def _manifest_disabled(manifest: dict[str, Any]) -> bool:
    return (
        manifest.get("LIVE TRADING") == "DISABLED"
        and manifest.get("live_trading_enabled") is False
        and manifest.get("broker_order_call_performed") is False
    )


def _require_text(field_name: str, value: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe BR-13 research, monitor, paper, review, or blocked label")
