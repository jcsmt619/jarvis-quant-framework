from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    PAPER_ONLY,
    RESEARCH_ONLY,
    SAFE_LABELS,
)


PHASE_ID = "13G"
MODULE_NAME = "Claude OpenAI Dual Agent Review"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/dual_agent_review")
ALLOWED_AGENTS = ("claude", "codex", "openai")
ALLOWED_REVIEW_TYPES = ("research", "code_safety")
ALLOWED_VERDICTS = ("pass", "review", "block")
_UNSAFE_TRADE_LABELS = (
    "BUY" + "_NOW",
    "SELL" + "_NOW",
    "EXECUTE" + "_TRADE",
    "AUTO" + "_TRADE",
)
_UNSAFE_ACTION_PATTERNS = (
    re.compile(r"\benable\s+live\s+trading\b", re.IGNORECASE),
    re.compile(r"\bsubmit\s+broker\s+order\b", re.IGNORECASE),
    re.compile(r"\broute\s+(?:a\s+)?(?:live\s+)?order\b", re.IGNORECASE),
    re.compile(r"\bprint\s+(?:api\s+key|secret|token|password|private\s+key)\b", re.IGNORECASE),
    re.compile(r"\bshow\s+(?:api\s+key|secret|token|password|private\s+key)\b", re.IGNORECASE),
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(API_" + r"KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)(\s*[:=]\s*)['\"][^'\"]+['\"]"
)


@dataclass(frozen=True)
class AgentReviewOutput:
    agent: str
    review_type: str
    summary: str
    findings: tuple[str, ...]
    verdict: str = "review"
    label: str = HUMAN_REVIEW_REQUIRED

    def validate(self) -> None:
        if self.agent.lower() not in ALLOWED_AGENTS:
            raise ValueError("agent must be claude, codex, or openai")
        if self.review_type not in ALLOWED_REVIEW_TYPES:
            raise ValueError("review_type must be research or code_safety")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if self.verdict not in ALLOWED_VERDICTS:
            raise ValueError("verdict must be pass, review, or block")
        if self.label not in SAFE_LABELS:
            raise ValueError("label must be a safe research, monitor, paper, or review label")


@dataclass(frozen=True)
class DualAgentReviewReport:
    source_artifact: str
    reviews: tuple[AgentReviewOutput, ...]
    consensus_status: str
    label: str
    warnings: tuple[str, ...]
    safety: dict[str, Any]
    metrics: dict[str, Any]


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "ingests_agent_outputs_only": True,
        "external_agent_calls_enabled": False,
        "claude_api_call_performed": False,
        "openai_api_call_performed": False,
        "codex_exec_performed": False,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "LIVE TRADING": "DISABLED",
    }


def build_dual_agent_review(
    reviews: list[AgentReviewOutput] | tuple[AgentReviewOutput, ...],
    source_artifact: str,
    min_distinct_agents: int = 2,
) -> DualAgentReviewReport:
    if min_distinct_agents < 2:
        raise ValueError("min_distinct_agents must be at least 2")
    if min_distinct_agents > len(ALLOWED_AGENTS):
        raise ValueError("min_distinct_agents cannot exceed supported agent count")
    if not source_artifact.strip():
        raise ValueError("source_artifact is required")

    ordered_reviews = tuple(sorted(reviews, key=lambda item: (item.agent.lower(), item.review_type)))
    for review in ordered_reviews:
        review.validate()

    warnings: list[str] = []
    distinct_agents = sorted({review.agent.lower() for review in ordered_reviews})
    review_types = sorted({review.review_type for review in ordered_reviews})
    verdicts = {review.verdict for review in ordered_reviews}

    if len(distinct_agents) < min_distinct_agents:
        warnings.append("insufficient_distinct_agent_coverage")
    if "research" not in review_types:
        warnings.append("missing_research_review")
    if "code_safety" not in review_types:
        warnings.append("missing_code_safety_review")
    if "block" in verdicts:
        warnings.append("agent_blocking_verdict")
    if len(verdicts) > 1:
        warnings.append("agent_verdict_conflict")

    unsafe_findings = _unsafe_review_findings(ordered_reviews)
    warnings.extend(unsafe_findings)

    clean_warnings = tuple(dict.fromkeys(warnings))
    if unsafe_findings:
        consensus_status = "blocked_by_safety_gate"
    elif "agent_blocking_verdict" in clean_warnings:
        consensus_status = "blocked_by_agent_review"
    elif "agent_verdict_conflict" in clean_warnings:
        consensus_status = "requires_human_reconciliation"
    elif clean_warnings:
        consensus_status = "incomplete_review"
    else:
        consensus_status = "dual_agent_review_complete"

    return DualAgentReviewReport(
        source_artifact=source_artifact,
        reviews=ordered_reviews,
        consensus_status=consensus_status,
        label=BLOCKED_BY_SAFETY_GATE if clean_warnings else HUMAN_REVIEW_REQUIRED,
        warnings=clean_warnings,
        safety=safety_manifest(),
        metrics={
            "review_count": len(ordered_reviews),
            "distinct_agent_count": len(distinct_agents),
            "review_types": tuple(review_types),
            "agents": tuple(distinct_agents),
            "warning_count": len(clean_warnings),
        },
    )


def build_dual_agent_review_payload(report: DualAgentReviewReport) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "module": MODULE_NAME,
        "source_artifact": report.source_artifact,
        "label": report.label,
        "consensus_status": report.consensus_status,
        "metrics": report.metrics,
        "warnings": report.warnings,
        "reviews": [_review_payload(review) for review in report.reviews],
        "safety": report.safety,
    }


def render_markdown_review(report: DualAgentReviewReport) -> str:
    payload = build_dual_agent_review_payload(report)
    lines = [
        f"# {PHASE_ID} {MODULE_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Summary",
        f"- source_artifact: {payload['source_artifact']}",
        f"- label: {payload['label']}",
        f"- consensus_status: {payload['consensus_status']}",
        f"- review_count: {payload['metrics']['review_count']}",
        f"- distinct_agent_count: {payload['metrics']['distinct_agent_count']}",
        "",
        "## Reviews",
    ]
    for review in payload["reviews"]:
        lines.append(
            f"- {review['agent']} {review['review_type']}: verdict={review['verdict']}, "
            f"label={review['label']}, summary={review['summary']}"
        )

    lines.extend(["", "## Warnings"])
    if payload["warnings"]:
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- no_dual_agent_review_warnings")

    lines.extend(
        [
            "",
            "## Safety",
            "- Review workflow ingests prewritten agent outputs only.",
            "- No external agent calls, broker routing, broker calls, or live order submission.",
            "- Trade-relevant research remains human-review-required.",
        ]
    )
    return "\n".join(lines)


def write_dual_agent_review_report(
    report: DualAgentReviewReport,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_dual_agent_review_payload(report)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_review(report), encoding="utf-8")
    return json_path, md_path


def _unsafe_review_findings(reviews: tuple[AgentReviewOutput, ...]) -> list[str]:
    warnings: list[str] = []
    for review in reviews:
        text = "\n".join((review.summary, *review.findings))
        upper_text = text.upper()
        for label in _UNSAFE_TRADE_LABELS:
            if label in upper_text:
                warnings.append(f"{review.agent.lower()}:{review.review_type}:unsafe_trade_label")
        for pattern in _UNSAFE_ACTION_PATTERNS:
            if pattern.search(text):
                warnings.append(f"{review.agent.lower()}:{review.review_type}:unsafe_action_phrase")
        if _SECRET_ASSIGNMENT.search(text):
            warnings.append(f"{review.agent.lower()}:{review.review_type}:secret_like_assignment_redacted")
    return warnings


def _review_payload(review: AgentReviewOutput) -> dict[str, Any]:
    return {
        "agent": review.agent.lower(),
        "review_type": review.review_type,
        "summary": _redact_secrets(review.summary),
        "findings": tuple(_redact_secrets(finding) for finding in review.findings),
        "verdict": review.verdict,
        "label": review.label,
        "human_review_required": True,
    }


def _redact_secrets(text: str) -> str:
    return _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", text)
