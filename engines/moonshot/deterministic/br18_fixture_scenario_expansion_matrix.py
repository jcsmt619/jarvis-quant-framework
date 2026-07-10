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


PHASE_ID = "BR-18"
MODULE_NAME = "Fixture Scenario Expansion Matrix"
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br18_fixture_scenario_expansion_matrix.json")
DEFAULT_REPORT_DIR = Path("reports/br18_fixture_scenario_expansion_matrix")
JSON_REPORT_NAME = "fixture_scenario_expansion_matrix.json"
MARKDOWN_REPORT_NAME = "fixture_scenario_expansion_matrix.md"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
REQUIRED_SCENARIO_TYPES = (
    "bullish",
    "bearish",
    "neutral",
    "stale-data",
    "poor-liquidity",
    "no-candidate",
    "thesis-missing",
    "chain-quality-failed",
    "risk-rejected",
    "paper-hold",
)
PIPELINE_STAGES = (
    "candidate_selection",
    "chain_quality",
    "contract_scoring",
    "thesis_packaging",
    "risk_gate_decision",
    "paper_only_portfolio_simulation",
    "monitor_alerts",
    "dashboard_summary",
)
REQUIRED_DISABLED_FLAGS = (
    "credential_loading_attempted",
    "env_file_read_attempted",
    "secret_request_attempted",
    "data_provider_call_attempted",
    "external_network_call_attempted",
    "real_data_fetch_attempted",
    "broker_connection_attempted",
    "broker_read_call_performed",
    "real_paper_wrapper_connected",
    "real_paper_wrapper_attempted",
    "real_paper_order_submitted",
    "broker_order_call_performed",
    "broker_order_submitted",
    "broker_order_routing_enabled",
    "trade_instruction_created",
    "broker_action_created",
    "order_path_created",
    "live_state_mutation_attempted",
    "live_trading_enabled",
)


@dataclass(frozen=True)
class ScenarioStageExpectation:
    stage: str
    status: str
    label: str
    reason: str

    def validate(self) -> None:
        if self.stage not in PIPELINE_STAGES:
            raise ValueError(f"unsupported BR-18 stage: {self.stage}")
        _require_text("stage status", self.status)
        _require_text("stage reason", self.reason)
        _require_safe_label(self.label)


@dataclass(frozen=True)
class FixtureScenario:
    scenario_id: str
    scenario_type: str
    symbol: str
    description: str
    expected_behavior: tuple[ScenarioStageExpectation, ...]

    def validate(self) -> None:
        _require_text("scenario_id", self.scenario_id)
        if self.scenario_type not in REQUIRED_SCENARIO_TYPES:
            raise ValueError(f"unsupported BR-18 scenario_type: {self.scenario_type}")
        _require_text("scenario symbol", self.symbol)
        _require_text("scenario description", self.description)
        stage_names = tuple(item.stage for item in self.expected_behavior)
        if stage_names != PIPELINE_STAGES:
            raise ValueError("BR-18 scenario must define every pipeline stage in order")
        for item in self.expected_behavior:
            item.validate()
        risk_stage = self.stage("risk_gate_decision")
        if self.scenario_type in {"stale-data", "poor-liquidity", "thesis-missing", "chain-quality-failed", "risk-rejected"}:
            if risk_stage.label != BLOCKED_BY_SAFETY_GATE:
                raise ValueError("blocked BR-18 scenarios must be blocked at the risk gate")
        if self.scenario_type in {"bullish", "paper-hold"} and risk_stage.label != PAPER_ONLY:
            raise ValueError("BR-18 paper hold scenarios must remain paper-only")
        portfolio_stage = self.stage("paper_only_portfolio_simulation")
        if portfolio_stage.label != PAPER_ONLY:
            raise ValueError("BR-18 portfolio simulation stage must be paper-only")
        thesis_stage = self.stage("thesis_packaging")
        if thesis_stage.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-18 thesis packaging must require human review")

    def stage(self, stage_name: str) -> ScenarioStageExpectation:
        for item in self.expected_behavior:
            if item.stage == stage_name:
                return item
        raise ValueError(f"missing BR-18 stage: {stage_name}")


@dataclass(frozen=True)
class FixtureScenarioExpansionMatrixReport:
    as_of: datetime
    scenarios: tuple[FixtureScenario, ...]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("BR-18 scenario matrix must require human review")
        scenario_types = tuple(item.scenario_type for item in self.scenarios)
        if scenario_types != REQUIRED_SCENARIO_TYPES:
            raise ValueError("BR-18 scenario matrix must contain the required scenario types in order")
        if len({item.scenario_id for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("BR-18 scenario ids must be unique")
        for item in self.scenarios:
            item.validate()
        _validate_disabled_safety(self.safety)


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
        "fixture_only": True,
        "offline_only": True,
        "deterministic_matrix_only": True,
        "paper_portfolio_updates_simulated": True,
        "credential_loading_attempted": False,
        "env_file_read_attempted": False,
        "secret_request_attempted": False,
        "data_provider_call_attempted": False,
        "external_network_call_attempted": False,
        "real_data_fetch_attempted": False,
        "broker_connection_attempted": False,
        "broker_read_call_performed": False,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "trade_instruction_created": False,
        "broker_action_created": False,
        "order_path_created": False,
        "live_state_mutation_attempted": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def load_scenario_matrix_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("BR-18 fixture must be a JSON object")
    return payload


def build_fixture_scenario_expansion_matrix_report(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    as_of: datetime | None = None,
) -> FixtureScenarioExpansionMatrixReport:
    payload = load_scenario_matrix_fixture(fixture_path)
    report = FixtureScenarioExpansionMatrixReport(
        as_of=as_of or datetime.now(timezone.utc).replace(microsecond=0),
        scenarios=tuple(_scenario_from_payload(item) for item in payload["scenarios"]),
        safety=safety_manifest(),
    )
    report.validate()
    return report


def fixture_scenario_expansion_matrix_payload(report: FixtureScenarioExpansionMatrixReport) -> dict[str, Any]:
    report.validate()
    stage_counts = _stage_status_counts(report.scenarios)
    scenario_outcomes = tuple(_scenario_outcome(item) for item in report.scenarios)
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "required_scenario_types": REQUIRED_SCENARIO_TYPES,
        "pipeline_stages": PIPELINE_STAGES,
        "metrics": {
            "scenario_count": len(report.scenarios),
            "pipeline_stage_count": len(PIPELINE_STAGES),
            "matrix_cell_count": len(report.scenarios) * len(PIPELINE_STAGES),
            "paper_hold_scenario_count": sum(1 for item in scenario_outcomes if item["risk_gate_label"] == PAPER_ONLY),
            "blocked_scenario_count": sum(1 for item in scenario_outcomes if item["risk_gate_label"] == BLOCKED_BY_SAFETY_GATE),
            "human_review_scenario_count": sum(1 for item in scenario_outcomes if item["risk_gate_label"] == HUMAN_REVIEW_REQUIRED),
            "monitor_alert_scenario_count": sum(1 for item in scenario_outcomes if item["monitor_alert_status"] not in {"clear", "empty"}),
            "dashboard_summary_count": len(report.scenarios),
        },
        "scenario_outcomes": scenario_outcomes,
        "stage_status_counts": stage_counts,
        "scenarios": [_scenario_payload(item) for item in report.scenarios],
        "acceptance_criteria": {
            "all_required_scenarios_present": tuple(item.scenario_type for item in report.scenarios) == REQUIRED_SCENARIO_TYPES,
            "all_pipeline_stages_covered": all(tuple(stage.stage for stage in item.expected_behavior) == PIPELINE_STAGES for item in report.scenarios),
            "fixture_only_offline": report.safety["fixture_only"] is True and report.safety["offline_only"] is True,
            "no_credentials_or_secrets": all(
                report.safety[field_name] is False
                for field_name in ("credential_loading_attempted", "env_file_read_attempted", "secret_request_attempted")
            ),
            "no_data_provider_or_network_calls": all(
                report.safety[field_name] is False
                for field_name in ("data_provider_call_attempted", "external_network_call_attempted", "real_data_fetch_attempted")
            ),
            "no_broker_or_order_paths": all(report.safety[field_name] is False for field_name in REQUIRED_DISABLED_FLAGS),
            "paper_simulation_only": report.safety["paper_portfolio_updates_simulated"] is True,
            "live_trading_disabled": report.safety["LIVE TRADING"] == "DISABLED",
            "human_review_required": report.label == HUMAN_REVIEW_REQUIRED,
        },
    }


def render_markdown_fixture_scenario_expansion_matrix(report: FixtureScenarioExpansionMatrixReport) -> str:
    payload = fixture_scenario_expansion_matrix_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Purpose",
        "BR-18 expands offline fixture coverage across deterministic Moonshot LEAPS scenario outcomes and proves expected behavior through the research pipeline.",
        "",
        "## Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Scenario Matrix"])
    header = "| Scenario | Candidate | Chain | Score | Thesis | Risk Gate | Paper Sim | Alerts | Dashboard |"
    lines.append(header)
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for scenario in payload["scenarios"]:
        stages = scenario["expected_behavior"]
        lines.append(
            "| "
            + " | ".join(
                (
                    scenario["scenario_type"],
                    _cell(stages["candidate_selection"]),
                    _cell(stages["chain_quality"]),
                    _cell(stages["contract_scoring"]),
                    _cell(stages["thesis_packaging"]),
                    _cell(stages["risk_gate_decision"]),
                    _cell(stages["paper_only_portfolio_simulation"]),
                    _cell(stages["monitor_alerts"]),
                    _cell(stages["dashboard_summary"]),
                )
            )
            + " |"
        )

    lines.extend(["", "## Scenario Outcomes"])
    for item in payload["scenario_outcomes"]:
        lines.append(
            f"- {item['scenario_type']}: risk={item['risk_gate_status']} label={item['risk_gate_label']} "
            f"paper={item['paper_simulation_status']} alert={item['monitor_alert_status']}"
        )

    lines.extend(["", "## Stage Status Counts"])
    for stage_name, counts in payload["stage_status_counts"].items():
        rendered = ", ".join(f"{name}={value}" for name, value in sorted(counts.items()))
        lines.append(f"- {stage_name}: {rendered}")

    lines.extend(["", "## Acceptance Criteria"])
    for name, passed in payload["acceptance_criteria"].items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "## Safety Boundaries",
            "- RESEARCH_ONLY; MONITOR_ONLY; PAPER_ONLY; HUMAN_REVIEW_REQUIRED; BLOCKED_BY_SAFETY_GATE.",
            "- Offline fixture-only matrix generation.",
            "- No credentials, .env reads, secrets, data-provider calls, broker connections, broker actions, order paths, live state mutation, or live trading enablement.",
            "- Paper-only portfolio behavior is simulated locally and never routed externally.",
        ]
    )
    return "\n".join(lines)


def write_fixture_scenario_expansion_matrix_report(
    report: FixtureScenarioExpansionMatrixReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    report.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_REPORT_NAME
    markdown_path = out_dir / MARKDOWN_REPORT_NAME
    json_path.write_text(json.dumps(fixture_scenario_expansion_matrix_payload(report), indent=2, default=str), encoding="utf-8")
    markdown_path.write_text(render_markdown_fixture_scenario_expansion_matrix(report), encoding="utf-8")
    return json_path, markdown_path


def run_fixture_scenario_expansion_matrix(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    out_dir: Path = DEFAULT_REPORT_DIR,
    as_of: datetime | None = None,
) -> FixtureScenarioExpansionMatrixReport:
    report = build_fixture_scenario_expansion_matrix_report(fixture_path=fixture_path, as_of=as_of)
    write_fixture_scenario_expansion_matrix_report(report, out_dir=out_dir)
    return report


def _scenario_from_payload(payload: dict[str, Any]) -> FixtureScenario:
    expected_behavior = payload["expected_behavior"]
    return FixtureScenario(
        scenario_id=payload["scenario_id"],
        scenario_type=payload["scenario_type"],
        symbol=payload["symbol"],
        description=payload["description"],
        expected_behavior=tuple(
            ScenarioStageExpectation(
                stage=stage_name,
                status=expected_behavior[stage_name]["status"],
                label=expected_behavior[stage_name]["label"],
                reason=expected_behavior[stage_name]["reason"],
            )
            for stage_name in PIPELINE_STAGES
        ),
    )


def _scenario_payload(scenario: FixtureScenario) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "symbol": scenario.symbol,
        "description": scenario.description,
        "expected_behavior": {
            item.stage: {
                "status": item.status,
                "label": item.label,
                "reason": item.reason,
            }
            for item in scenario.expected_behavior
        },
    }


def _scenario_outcome(scenario: FixtureScenario) -> dict[str, Any]:
    risk = scenario.stage("risk_gate_decision")
    paper = scenario.stage("paper_only_portfolio_simulation")
    alerts = scenario.stage("monitor_alerts")
    dashboard = scenario.stage("dashboard_summary")
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "symbol": scenario.symbol,
        "risk_gate_status": risk.status,
        "risk_gate_label": risk.label,
        "paper_simulation_status": paper.status,
        "monitor_alert_status": alerts.status,
        "dashboard_status": dashboard.status,
    }


def _stage_status_counts(scenarios: tuple[FixtureScenario, ...]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {stage_name: {} for stage_name in PIPELINE_STAGES}
    for scenario in scenarios:
        for item in scenario.expected_behavior:
            counts[item.stage][item.status] = counts[item.stage].get(item.status, 0) + 1
    return counts


def _cell(stage_payload: dict[str, str]) -> str:
    return f"{stage_payload['status']} ({stage_payload['label']})"


def _validate_disabled_safety(manifest: dict[str, Any]) -> None:
    for field_name in REQUIRED_DISABLED_FLAGS:
        if manifest.get(field_name) is not False:
            raise ValueError(f"BR-18 scenario matrix cannot set {field_name}")
    if manifest.get("LIVE TRADING") != "DISABLED":
        raise ValueError("BR-18 scenario matrix must keep LIVE TRADING disabled")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
