from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from risk.policies import (
    BLOCKED_BY_SAFETY_GATE,
    HUMAN_REVIEW_REQUIRED,
    MONITOR_ONLY,
    MOONSHOT_RISK_POLICY,
    PAPER_ONLY,
    PolicyState,
    RESEARCH_ONLY,
    evaluate_policy,
)


PHASE_ID = "13A"
SIMULATOR_NAME = "Moonshot Simulator"
REQUIRED_LABELS = (RESEARCH_ONLY, MONITOR_ONLY, PAPER_ONLY, HUMAN_REVIEW_REQUIRED)
DEFAULT_REPORT_DIR = Path("reports/moonshot_simulator")


@dataclass(frozen=True)
class MoonshotScenario:
    symbol: str
    thesis: str
    proposed_position_pct: float
    upside_pct: float
    downside_pct: float
    probability_upside: float
    dte: int
    iv_rank: float
    theta_decay_pct: float
    option_chain_age_minutes: int
    has_exit_plan: bool = True

    def validate(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if not self.thesis.strip():
            raise ValueError("thesis is required")
        if self.proposed_position_pct <= 0:
            raise ValueError("proposed_position_pct must be positive")
        if self.upside_pct < 0:
            raise ValueError("upside_pct cannot be negative")
        if self.downside_pct < 0:
            raise ValueError("downside_pct cannot be negative")
        if not 0.0 <= self.probability_upside <= 1.0:
            raise ValueError("probability_upside must be between 0 and 1")
        if self.dte <= 0:
            raise ValueError("dte must be positive")
        if not 0.0 <= self.iv_rank <= 1.0:
            raise ValueError("iv_rank must be between 0 and 1")
        if self.theta_decay_pct < 0:
            raise ValueError("theta_decay_pct cannot be negative")
        if self.option_chain_age_minutes < 0:
            raise ValueError("option_chain_age_minutes cannot be negative")


@dataclass(frozen=True)
class MoonshotSimulatorConfig:
    max_total_exposure_pct: float = 0.12
    max_option_chain_age_minutes: int = 30
    max_iv_rank: float = 0.85
    max_theta_decay_pct: float = 0.25
    min_dte: int = 180
    initial_equity: float = 1.0

    def validate(self) -> None:
        if self.max_total_exposure_pct <= 0:
            raise ValueError("max_total_exposure_pct must be positive")
        if self.max_option_chain_age_minutes < 0:
            raise ValueError("max_option_chain_age_minutes cannot be negative")
        if not 0.0 <= self.max_iv_rank <= 1.0:
            raise ValueError("max_iv_rank must be between 0 and 1")
        if self.max_theta_decay_pct < 0:
            raise ValueError("max_theta_decay_pct cannot be negative")
        if self.min_dte <= 0:
            raise ValueError("min_dte must be positive")
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")


@dataclass(frozen=True)
class MoonshotScenarioResult:
    scenario: MoonshotScenario
    label: str
    included_in_research_simulation: bool
    expected_return_pct: float
    expected_account_return_pct: float
    best_case_account_return_pct: float
    stress_loss_account_pct: float
    failure_modes: tuple[str, ...]
    safety: dict[str, Any]


@dataclass(frozen=True)
class MoonshotSimulationResult:
    config: MoonshotSimulatorConfig
    scenario_results: tuple[MoonshotScenarioResult, ...]
    metrics: dict[str, float | int]
    safety: dict[str, Any]


def safety_manifest() -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "simulator": SIMULATOR_NAME,
        "labels": REQUIRED_LABELS,
        "research_only": True,
        "monitor_only": True,
        "paper_only": True,
        "human_review_required": True,
        "live_trading_enabled": False,
        "broker_order_routing_enabled": False,
        "broker_order_call_performed": False,
        "broker_order_submitted": False,
        "LIVE TRADING": "DISABLED",
    }


def failure_mode_definitions() -> dict[str, str]:
    return {
        "missing_stop": "The scenario has no explicit exit or invalidation plan.",
        "position_loss_breach": "Scenario stress loss exceeds Moonshot per-position loss cap.",
        "position_size_breach": "Scenario exposure exceeds Moonshot position sizing cap.",
        "max_positions_breach": "Scenario count exceeds Moonshot maximum concurrent research slots.",
        "option_chain_stale": "Option-chain inputs are older than the simulator freshness cap.",
        "theta_decay_breach": "Theta decay is above the simulator cap.",
        "iv_spike_review": "IV rank is above the simulator cap and needs human review.",
        "dte_below_minimum": "DTE is below the LEAPS research minimum.",
        "portfolio_exposure_breach": "Total proposed Moonshot exposure exceeds the simulator cap.",
    }


def simulate_moonshot_scenarios(
    scenarios: list[MoonshotScenario] | tuple[MoonshotScenario, ...],
    config: MoonshotSimulatorConfig | None = None,
) -> MoonshotSimulationResult:
    cfg = config or MoonshotSimulatorConfig()
    cfg.validate()

    total_exposure = 0.0
    results: list[MoonshotScenarioResult] = []
    for scenario in scenarios:
        scenario.validate()
        total_exposure += scenario.proposed_position_pct
        failure_modes = list(_scenario_failure_modes(scenario, cfg))
        if total_exposure > cfg.max_total_exposure_pct:
            failure_modes.append("portfolio_exposure_breach")

        stress_loss_account_pct = scenario.proposed_position_pct * scenario.downside_pct
        expected_return_pct = (
            scenario.probability_upside * scenario.upside_pct
            - (1.0 - scenario.probability_upside) * scenario.downside_pct
        )
        expected_account_return_pct = scenario.proposed_position_pct * expected_return_pct
        best_case_account_return_pct = scenario.proposed_position_pct * scenario.upside_pct

        policy_decision = evaluate_policy(
            MOONSHOT_RISK_POLICY,
            PolicyState(
                proposed_position_pct=scenario.proposed_position_pct,
                current_positions=len(results),
                max_position_loss_pct=stress_loss_account_pct,
                missing_stop=not scenario.has_exit_plan,
                extra_stop_flags=tuple(
                    mode
                    for mode in failure_modes
                    if mode in MOONSHOT_RISK_POLICY.stop_conditions
                ),
            ),
        )

        combined_failures = tuple(dict.fromkeys((*policy_decision.reasons, *failure_modes)))
        included = not combined_failures
        results.append(
            MoonshotScenarioResult(
                scenario=scenario,
                label=RESEARCH_ONLY if included else BLOCKED_BY_SAFETY_GATE,
                included_in_research_simulation=included,
                expected_return_pct=expected_return_pct,
                expected_account_return_pct=expected_account_return_pct,
                best_case_account_return_pct=best_case_account_return_pct,
                stress_loss_account_pct=stress_loss_account_pct,
                failure_modes=combined_failures,
                safety=safety_manifest(),
            )
        )

    return MoonshotSimulationResult(
        config=cfg,
        scenario_results=tuple(results),
        metrics=_compute_metrics(results),
        safety=safety_manifest(),
    )


def build_report_payload(result: MoonshotSimulationResult) -> dict[str, Any]:
    return {
        "phase": PHASE_ID,
        "simulator": SIMULATOR_NAME,
        "safety": result.safety,
        "risk_caps": {
            "max_position_pct": MOONSHOT_RISK_POLICY.max_position_pct,
            "max_positions": MOONSHOT_RISK_POLICY.max_positions,
            "max_loss_per_position_pct": MOONSHOT_RISK_POLICY.max_loss_per_position_pct,
            "max_total_drawdown_pct": MOONSHOT_RISK_POLICY.max_total_drawdown_pct,
            "max_total_exposure_pct": result.config.max_total_exposure_pct,
            "max_option_chain_age_minutes": result.config.max_option_chain_age_minutes,
            "max_iv_rank": result.config.max_iv_rank,
            "max_theta_decay_pct": result.config.max_theta_decay_pct,
            "min_dte": result.config.min_dte,
        },
        "failure_mode_definitions": failure_mode_definitions(),
        "metrics": result.metrics,
        "scenarios": [_scenario_payload(item) for item in result.scenario_results],
    }


def render_markdown_report(result: MoonshotSimulationResult) -> str:
    payload = build_report_payload(result)
    lines = [
        f"# {PHASE_ID} {SIMULATOR_NAME}",
        "",
        "Research labels: " + ", ".join(REQUIRED_LABELS),
        "LIVE TRADING: DISABLED",
        "",
        "## Risk Caps",
    ]
    for name, value in payload["risk_caps"].items():
        lines.append(f"- {name}: {_format_metric(value)}")

    lines.extend(["", "## Scenario Results"])
    for scenario in payload["scenarios"]:
        lines.append(
            "- "
            + scenario["symbol"]
            + f": label={scenario['label']}, expected_account_return_pct="
            + _format_metric(scenario["expected_account_return_pct"])
            + f", stress_loss_account_pct={_format_metric(scenario['stress_loss_account_pct'])}"
        )
        if scenario["failure_modes"]:
            lines.append("  failure_modes: " + ", ".join(scenario["failure_modes"]))

    lines.extend(["", "## Aggregate Metrics"])
    for name, value in payload["metrics"].items():
        lines.append(f"- {name}: {_format_metric(value)}")

    lines.extend(
        [
            "",
            "## Safety",
            "- No broker imports, order routing, or order submission are used.",
            "- Outputs are high-risk research scenarios and require human review.",
            "- Blocked scenarios remain in the report for audit visibility.",
        ]
    )
    return "\n".join(lines)


def write_research_report(
    result: MoonshotSimulationResult,
    out_dir: Path = DEFAULT_REPORT_DIR,
) -> tuple[Path, Path]:
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(result)
    json_path = out_dir / "summary.json"
    md_path = out_dir / "report.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown_report(result), encoding="utf-8")
    return json_path, md_path


def _scenario_failure_modes(
    scenario: MoonshotScenario,
    config: MoonshotSimulatorConfig,
) -> tuple[str, ...]:
    modes: list[str] = []
    if scenario.option_chain_age_minutes > config.max_option_chain_age_minutes:
        modes.append("option_chain_stale")
    if scenario.theta_decay_pct > config.max_theta_decay_pct:
        modes.append("theta_decay_breach")
    if scenario.iv_rank > config.max_iv_rank:
        modes.append("iv_spike_review")
    if scenario.dte < config.min_dte:
        modes.append("dte_below_minimum")
    return tuple(modes)


def _compute_metrics(results: list[MoonshotScenarioResult]) -> dict[str, float | int]:
    included = [item for item in results if item.included_in_research_simulation]
    blocked = [item for item in results if not item.included_in_research_simulation]
    return {
        "scenario_count": int(len(results)),
        "included_count": int(len(included)),
        "blocked_count": int(len(blocked)),
        "total_expected_account_return_pct": float(
            sum(item.expected_account_return_pct for item in included)
        ),
        "total_best_case_account_return_pct": float(
            sum(item.best_case_account_return_pct for item in included)
        ),
        "total_stress_loss_account_pct": float(
            sum(item.stress_loss_account_pct for item in included)
        ),
        "blocked_stress_loss_account_pct": float(
            sum(item.stress_loss_account_pct for item in blocked)
        ),
    }


def _scenario_payload(item: MoonshotScenarioResult) -> dict[str, Any]:
    scenario = item.scenario
    return {
        "symbol": scenario.symbol,
        "thesis": scenario.thesis,
        "label": item.label,
        "included_in_research_simulation": item.included_in_research_simulation,
        "proposed_position_pct": scenario.proposed_position_pct,
        "upside_pct": scenario.upside_pct,
        "downside_pct": scenario.downside_pct,
        "probability_upside": scenario.probability_upside,
        "dte": scenario.dte,
        "iv_rank": scenario.iv_rank,
        "theta_decay_pct": scenario.theta_decay_pct,
        "option_chain_age_minutes": scenario.option_chain_age_minutes,
        "has_exit_plan": scenario.has_exit_plan,
        "expected_return_pct": item.expected_return_pct,
        "expected_account_return_pct": item.expected_account_return_pct,
        "best_case_account_return_pct": item.best_case_account_return_pct,
        "stress_loss_account_pct": item.stress_loss_account_pct,
        "failure_modes": item.failure_modes,
        "safety": item.safety,
    }


def _format_metric(value: float | int) -> str:
    return f"{value:.6f}" if isinstance(value, float) else str(value)
