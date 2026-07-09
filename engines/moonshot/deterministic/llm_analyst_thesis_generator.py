from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from engines.moonshot.deterministic.options_contract_scorer import (
    ContractScoringReport,
    contract_scoring_payload,
    load_contract_scoring_report,
)
from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
)


PHASE_ID = "BR-05"
MODULE_NAME = "LLM Analyst Thesis Generator"
REQUIRED_LABELS = (
    RESEARCH_ONLY,
    MONITOR_ONLY,
    PAPER_ONLY,
    HUMAN_REVIEW_REQUIRED,
    BLOCKED_BY_SAFETY_GATE,
)
SAFE_ACTION_LABELS = REQUIRED_LABELS
DEFAULT_FIXTURE_PATH = Path("engines/moonshot/deterministic/fixtures/br05_llm_analyst_thesis_generator.json")
DEFAULT_REPORT_DIR = Path("reports/br05_llm_analyst_thesis_generator")


@dataclass(frozen=True)
class AnalystPromptPackage:
    prompt_id: str
    symbol: str
    contract_ids: tuple[str, ...]
    created_at: datetime
    system_prompt: str
    user_prompt: str
    source_context: dict[str, Any]
    safety: dict[str, Any]
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        _require_text("prompt_id", self.prompt_id)
        _require_symbol(self.symbol)
        if not self.contract_ids:
            raise ValueError("analyst prompt package requires at least one contract id")
        for contract_id in self.contract_ids:
            _require_text("contract_id", contract_id)
        _require_text("system_prompt", self.system_prompt)
        _require_text("user_prompt", self.user_prompt)
        if not self.source_context:
            raise ValueError("source_context is required")
        _require_safe_label(self.label)
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("analyst prompt packages must require human review")
        if self.safety.get("live_trading_enabled") is not False:
            raise ValueError("analyst prompt package cannot enable live trading")
        if self.safety.get("broker_order_call_performed") is not False:
            raise ValueError("analyst prompt package cannot perform broker calls")


@dataclass(frozen=True)
class AnalystThesisRecord:
    thesis_id: str
    prompt_id: str
    symbol: str
    generated_at: datetime
    thesis_summary: str
    bull_case: tuple[str, ...]
    bear_case: tuple[str, ...]
    catalysts: tuple[str, ...]
    invalidation_triggers: tuple[str, ...]
    risk_notes: tuple[str, ...]
    source_citations: tuple[str, ...]
    confidence: str
    label: str = HUMAN_REVIEW_REQUIRED
    research_only: bool = True
    human_review_required: bool = True
    live_trading_enabled: bool = False
    broker_order_call_performed: bool = False

    def validate(self) -> None:
        _require_text("thesis_id", self.thesis_id)
        _require_text("prompt_id", self.prompt_id)
        _require_symbol(self.symbol)
        for field_name, value in (
            ("thesis_summary", self.thesis_summary),
            ("confidence", self.confidence),
        ):
            _require_text(field_name, value)
        for field_name, values in (
            ("bull_case", self.bull_case),
            ("bear_case", self.bear_case),
            ("catalysts", self.catalysts),
            ("invalidation_triggers", self.invalidation_triggers),
            ("risk_notes", self.risk_notes),
            ("source_citations", self.source_citations),
        ):
            _require_non_empty_text_tuple(field_name, values)
        _require_safe_label(self.label)
        if self.label != HUMAN_REVIEW_REQUIRED:
            raise ValueError("analyst thesis records must require human review")
        if not self.research_only or not self.human_review_required:
            raise ValueError("analyst thesis records must remain research-only and human-review-required")
        if self.live_trading_enabled or self.broker_order_call_performed:
            raise ValueError("analyst thesis records cannot enable trading or broker calls")


@dataclass(frozen=True)
class AnalystThesisReport:
    as_of: datetime
    prompt_packages: tuple[AnalystPromptPackage, ...]
    thesis_records: tuple[AnalystThesisRecord, ...]
    safety: dict[str, Any]
    label: str = BLOCKED_BY_SAFETY_GATE

    def validate(self) -> None:
        if not self.prompt_packages:
            raise ValueError("analyst thesis report requires at least one prompt package")
        for package in self.prompt_packages:
            package.validate()
        for record in self.thesis_records:
            record.validate()
            if record.prompt_id not in {package.prompt_id for package in self.prompt_packages}:
                raise ValueError("analyst thesis record prompt_id must match a prompt package")
        _require_safe_label(self.label)
        if self.label != BLOCKED_BY_SAFETY_GATE:
            raise ValueError("analyst thesis report must remain blocked by safety gate")


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
        "live_api_calls_required": False,
        "local_prompt_packaging_only": True,
        "source_grounded_context_required": True,
        "real_paper_wrapper_connected": False,
        "real_paper_wrapper_attempted": False,
        "real_paper_order_submitted": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "broker_order_routing_enabled": False,
        "live_trading_enabled": False,
        "LIVE TRADING": "DISABLED",
    }


def build_analyst_prompt_packages(
    scoring_report: ContractScoringReport | None = None,
    created_at: datetime | None = None,
) -> tuple[AnalystPromptPackage, ...]:
    report = scoring_report or load_contract_scoring_report()
    report.validate()
    payload = contract_scoring_payload(report)
    report_as_of = created_at or report.as_of
    contracts_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for contract in payload["suitable_contracts"]:
        contracts_by_symbol.setdefault(contract["underlying_symbol"], []).append(contract)
    if not contracts_by_symbol:
        raise ValueError("analyst prompt packaging requires at least one suitable contract")

    packages = tuple(
        _prompt_package_for_symbol(symbol, contracts, payload, report_as_of)
        for symbol, contracts in sorted(contracts_by_symbol.items())
    )
    for package in packages:
        package.validate()
    return packages


def parse_analyst_response(response_text: str, package: AnalystPromptPackage) -> AnalystThesisRecord:
    package.validate()
    _require_text("response_text", response_text)
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("analyst response must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("analyst response must be a JSON object")
    if payload.get("prompt_id") != package.prompt_id:
        raise ValueError("analyst response prompt_id must match prompt package")
    if payload.get("symbol") != package.symbol:
        raise ValueError("analyst response symbol must match prompt package")

    record = AnalystThesisRecord(
        thesis_id=payload["thesis_id"],
        prompt_id=payload["prompt_id"],
        symbol=payload["symbol"],
        generated_at=_parse_datetime(payload["generated_at"]),
        thesis_summary=payload["thesis_summary"],
        bull_case=_text_tuple(payload["bull_case"]),
        bear_case=_text_tuple(payload["bear_case"]),
        catalysts=_text_tuple(payload["catalysts"]),
        invalidation_triggers=_text_tuple(payload["invalidation_triggers"]),
        risk_notes=_text_tuple(payload["risk_notes"]),
        source_citations=_text_tuple(payload["source_citations"]),
        confidence=payload["confidence"],
        label=payload.get("label", HUMAN_REVIEW_REQUIRED),
        research_only=bool(payload.get("research_only", True)),
        human_review_required=bool(payload.get("human_review_required", True)),
        live_trading_enabled=bool(payload.get("live_trading_enabled", False)),
        broker_order_call_performed=bool(payload.get("broker_order_call_performed", False)),
    )
    record.validate()
    _require_citations_in_context(record.source_citations, package.source_context)
    return record


def load_fixture_analyst_responses(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    responses = payload.get("analyst_responses", {})
    if not isinstance(responses, dict) or not responses:
        raise ValueError("BR-05 fixture requires analyst_responses")
    return {str(prompt_id): json.dumps(response) for prompt_id, response in responses.items()}


def build_analyst_thesis_report(
    prompt_packages: tuple[AnalystPromptPackage, ...] | list[AnalystPromptPackage] | None = None,
    response_text_by_prompt_id: dict[str, str] | None = None,
    as_of: datetime | None = None,
) -> AnalystThesisReport:
    packages = tuple(build_analyst_prompt_packages() if prompt_packages is None else prompt_packages)
    if not packages:
        raise ValueError("analyst thesis report requires at least one prompt package")
    for package in packages:
        package.validate()
    responses = response_text_by_prompt_id or {}
    records = tuple(
        parse_analyst_response(responses[package.prompt_id], package)
        for package in packages
        if package.prompt_id in responses
    )
    report = AnalystThesisReport(
        as_of=as_of or max(package.created_at for package in packages),
        prompt_packages=packages,
        thesis_records=records,
        safety=safety_manifest(),
    )
    report.validate()
    return report


def analyst_thesis_payload(report: AnalystThesisReport) -> dict[str, Any]:
    report.validate()
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "as_of": report.as_of.isoformat(),
        "label": report.label,
        "safety": report.safety,
        "metrics": {
            "prompt_package_count": len(report.prompt_packages),
            "parsed_thesis_record_count": len(report.thesis_records),
            "human_review_required_count": len(report.prompt_packages) + len(report.thesis_records),
        },
        "prompt_packages": [_prompt_payload(package) for package in report.prompt_packages],
        "thesis_records": [_record_payload(record) for record in report.thesis_records],
    }


def render_markdown_analyst_thesis(report: AnalystThesisReport) -> str:
    payload = analyst_thesis_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Metrics",
    ]
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {value}")

    lines.extend(["", "## Prompt Packages"])
    for package in payload["prompt_packages"]:
        lines.append(
            "- "
            + package["prompt_id"]
            + f": symbol={package['symbol']}, contracts="
            + ", ".join(package["contract_ids"])
            + f", label={package['label']}"
        )

    lines.extend(["", "## Parsed Thesis Records"])
    if payload["thesis_records"]:
        for record in payload["thesis_records"]:
            lines.append(
                "- "
                + record["thesis_id"]
                + f": symbol={record['symbol']}, confidence={record['confidence']}, "
                + f"label={record['label']}"
            )
            lines.append("  summary: " + record["thesis_summary"])
    else:
        lines.append("- no_analyst_responses_parsed")

    lines.extend(
        [
            "",
            "## Safety",
            "- Local prompt packaging and response parsing only; no live API calls are required.",
            "- Analyst thesis records are research-only and human-review-required.",
            "- Report-level state remains blocked by safety gate.",
        ]
    )
    return "\n".join(lines)


def write_analyst_thesis_report(
    report: AnalystThesisReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "llm_analyst_thesis_generator.json"
    md_path = out_dir / "llm_analyst_thesis_generator.md"
    json_path.write_text(json.dumps(analyst_thesis_payload(report), indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_analyst_thesis(report), encoding="utf-8")
    return json_path, md_path


def _prompt_package_for_symbol(
    symbol: str,
    contracts: list[dict[str, Any]],
    source_payload: dict[str, Any],
    created_at: datetime,
) -> AnalystPromptPackage:
    selected_contracts = sorted(contracts, key=lambda item: (-item["total_score"], item["contract_id"]))[:3]
    source_context = {
        "phase": source_payload["phase"],
        "source_module": source_payload["module"],
        "source_as_of": source_payload["as_of"],
        "symbol": symbol,
        "contracts": [
            {
                "contract_id": contract["contract_id"],
                "underlying_symbol": contract["underlying_symbol"],
                "strike": contract["strike"],
                "expiration": contract["expiration"],
                "dte": contract["dte"],
                "total_score": contract["total_score"],
                "component_scores": contract["component_scores"],
                "label": contract["label"],
                "human_review_required": contract["human_review_required"],
            }
            for contract in selected_contracts
        ],
        "safety": source_payload["safety"],
    }
    prompt_id = f"BR-05-{symbol}-{created_at.strftime('%Y%m%d%H%M%S')}"
    return AnalystPromptPackage(
        prompt_id=prompt_id,
        symbol=symbol,
        contract_ids=tuple(contract["contract_id"] for contract in selected_contracts),
        created_at=created_at,
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(symbol, source_context),
        source_context=source_context,
        safety=safety_manifest(),
    )


def _system_prompt() -> str:
    return (
        "You are a research-only options thesis reviewer for Jarvis Quant. "
        "Use only the supplied JSON context. Do not request secrets, do not place trades, "
        "do not route orders, and keep all trade-relevant output labeled HUMAN_REVIEW_REQUIRED. "
        "Return one JSON object matching the requested schema."
    )


def _user_prompt(symbol: str, source_context: dict[str, Any]) -> str:
    schema = {
        "thesis_id": "string",
        "prompt_id": "string",
        "symbol": symbol,
        "generated_at": "ISO-8601 datetime",
        "thesis_summary": "string",
        "bull_case": ["source-grounded point"],
        "bear_case": ["source-grounded point"],
        "catalysts": ["source-grounded point"],
        "invalidation_triggers": ["source-grounded point"],
        "risk_notes": ["source-grounded point"],
        "source_citations": ["contract_id or source_module"],
        "confidence": "low|medium|high",
        "label": HUMAN_REVIEW_REQUIRED,
        "research_only": True,
        "human_review_required": True,
        "live_trading_enabled": False,
        "broker_order_call_performed": False,
    }
    return (
        "Prepare a source-grounded LEAPS thesis review for "
        + symbol
        + ". Context JSON:\n"
        + json.dumps(source_context, indent=2, sort_keys=True)
        + "\nRequired response schema:\n"
        + json.dumps(schema, indent=2)
    )


def _prompt_payload(package: AnalystPromptPackage) -> dict[str, Any]:
    return {
        "prompt_id": package.prompt_id,
        "symbol": package.symbol,
        "contract_ids": package.contract_ids,
        "created_at": package.created_at.isoformat(),
        "system_prompt": package.system_prompt,
        "user_prompt": package.user_prompt,
        "source_context": package.source_context,
        "label": package.label,
    }


def _record_payload(record: AnalystThesisRecord) -> dict[str, Any]:
    return {
        "thesis_id": record.thesis_id,
        "prompt_id": record.prompt_id,
        "symbol": record.symbol,
        "generated_at": record.generated_at.isoformat(),
        "thesis_summary": record.thesis_summary,
        "bull_case": record.bull_case,
        "bear_case": record.bear_case,
        "catalysts": record.catalysts,
        "invalidation_triggers": record.invalidation_triggers,
        "risk_notes": record.risk_notes,
        "source_citations": record.source_citations,
        "confidence": record.confidence,
        "label": record.label,
        "research_only": record.research_only,
        "human_review_required": record.human_review_required,
        "live_trading_enabled": record.live_trading_enabled,
        "broker_order_call_performed": record.broker_order_call_performed,
    }


def _require_citations_in_context(citations: tuple[str, ...], source_context: dict[str, Any]) -> None:
    allowed = {source_context["source_module"]}
    allowed.update(contract["contract_id"] for contract in source_context["contracts"])
    unknown = tuple(citation for citation in citations if citation not in allowed)
    if unknown:
        raise ValueError("analyst response source_citations must reference supplied context")


def _text_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list | tuple):
        raise ValueError("analyst response field must be a list of strings")
    return tuple(str(value) for value in values)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _require_symbol(symbol: str) -> None:
    _require_text("symbol", symbol)
    if symbol.strip() != symbol.strip().upper():
        raise ValueError("symbol must be uppercase")


def _require_text(field_name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")


def _require_non_empty_text_tuple(field_name: str, values: tuple[str, ...]) -> None:
    if not values:
        raise ValueError(f"{field_name} requires at least one value")
    for value in values:
        _require_text(field_name, value)


def _require_safe_label(label: str) -> None:
    if label not in SAFE_ACTION_LABELS:
        raise ValueError("label must be a safe research, monitor, paper, review, or blocked label")
