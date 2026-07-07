from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def run_git(args: list[str], max_chars: int = 12000) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "git not found"

    output = (completed.stdout or "") + (completed.stderr or "")
    if len(output) > max_chars:
        return output[:max_chars] + "\n...[truncated]..."
    return output


def read_file(path: Path, max_chars: int = 12000) -> str:
    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated]..."
    return text


def read_supervisor_context(
    repo_root: Path,
    max_chars_per_file: int = 12000,
    max_total_chars: int = 60000,
) -> str:
    context_parts: list[str] = []

    priority_files = [
        repo_root / "AGENTS.md",
        repo_root / "CLAUDE.md",
    ]

    for path in priority_files:
        if path.exists():
            context_parts.append(
                f"\n\n## {path.relative_to(repo_root)}\n\n"
                + read_file(path, max_chars=max_chars_per_file)
            )

    context_dir = repo_root / "docs" / "supervisor_context"
    if context_dir.exists():
        for path in sorted(context_dir.glob("*.md")):
            context_parts.append(
                f"\n\n## {path.relative_to(repo_root)}\n\n"
                + read_file(path, max_chars=max_chars_per_file)
            )

    context = "\n".join(context_parts)
    if len(context) > max_total_chars:
        return context[:max_total_chars] + "\n...[supervisor context truncated]..."
    return context


def extract_output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    pieces: list[str] = []

    for item in response.get("output", []) or []:
        if not isinstance(item, dict):
            continue

        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue

            if isinstance(content.get("text"), str):
                pieces.append(content["text"])
            elif isinstance(content.get("value"), str):
                pieces.append(content["value"])

    return "\n".join(pieces).strip()


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    first = cleaned.find("{")
    last = cleaned.rfind("}")

    if first >= 0 and last >= first:
        cleaned = cleaned[first : last + 1]

    return json.loads(cleaned)


def call_openai_responses(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    reasoning_effort: str,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    if reasoning_effort.lower() != "none":
        payload["reasoning"] = {"effort": reasoning_effort}

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API HTTP {exc.code}: {error_body}") from exc

    parsed = json.loads(body)
    output_text = extract_output_text(parsed)

    if not output_text:
        raise RuntimeError("OpenAI response did not contain output text.")

    return output_text


def build_user_prompt(args: argparse.Namespace, repo_root: Path) -> str:
    if args.error_log:
        error_log = read_file(Path(args.error_log), max_chars=args.max_error_chars)
    else:
        error_log = args.error_summary

    supervisor_context = read_supervisor_context(repo_root)

    return f"""
Phase:
{args.phase_name}

Failed command:
{args.failed_command}

Exit code:
{args.exit_code}

Error output:
{error_log}

Current branch:
{run_git(["branch", "--show-current"])}

Git status:
{run_git(["status", "--short", "--untracked-files=all"])}

Git diff stat:
{run_git(["diff", "--stat"])}

Git diff names:
{run_git(["diff", "--name-only"])}

Recent commits:
{run_git(["log", "--oneline", "-8"])}

Supervisor project context:
{supervisor_context}

Return JSON only.
"""


def validate_plan(plan: dict[str, Any]) -> None:
    required = [
        "status",
        "root_cause",
        "safe_repair_plan",
        "recommended_agent",
        "repair_prompt_for_agent",
        "commands_to_run_after_patch",
        "files_to_change",
        "stop_conditions",
        "dangerous_action_detected",
        "safe_to_patch",
    ]

    missing = [key for key in required if key not in plan]
    if missing:
        raise ValueError(f"Supervisor JSON missing required keys: {missing}")

    if plan["dangerous_action_detected"] is True:
        raise ValueError("Supervisor detected dangerous action. Refusing to continue.")

    if plan["safe_to_patch"] is not True:
        raise ValueError("Supervisor did not mark plan safe_to_patch=true.")

    agent = str(plan["recommended_agent"]).lower()
    if agent not in {"codex", "claude", "human"}:
        raise ValueError(f"Unsupported recommended_agent: {agent}")

    repair_prompt = str(plan["repair_prompt_for_agent"]).lower()
    hard_forbidden = [
        "enable live trading",
        "submit broker order",
        "print api key",
        "show api key",
        "paste api key",
        "disable safety",
        "remove safety",
    ]

    for phrase in hard_forbidden:
        if phrase in repair_prompt:
            raise ValueError(f"Repair prompt contains forbidden phrase: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis OpenAI Supervisor")
    parser.add_argument("--phase-name", required=True)
    parser.add_argument("--failed-command", required=True)
    parser.add_argument("--exit-code", type=int, default=1)
    parser.add_argument("--error-summary", default="")
    parser.add_argument("--error-log", default="")
    parser.add_argument("--output-json", default="reports/supervisor_runs/latest.json")
    parser.add_argument("--model", default=os.environ.get("JARVIS_SUPERVISOR_MODEL", "gpt-5.5"))
    parser.add_argument("--reasoning-effort", default=os.environ.get("JARVIS_SUPERVISOR_REASONING", "medium"))
    parser.add_argument("--max-error-chars", type=int, default=12000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path.cwd()
    system_prompt_path = repo_root / "prompts" / "jarvis_openai_supervisor_system.md"
    system_prompt = read_file(system_prompt_path, max_chars=16000)

    if not system_prompt:
        raise RuntimeError(f"Supervisor system prompt not found: {system_prompt_path}")

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        plan = {
            "status": "repair_needed",
            "root_cause": "dry-run supervisor self-test",
            "safe_repair_plan": ["Confirm supervisor can write valid JSON."],
            "recommended_agent": "codex",
            "repair_prompt_for_agent": "Dry-run only. Do not edit files.",
            "commands_to_run_after_patch": ["python -m pytest tests/ -q"],
            "files_to_change": [],
            "stop_conditions": ["Any secret, live trading, or broker order request."],
            "dangerous_action_detected": False,
            "safe_to_patch": True,
        }
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it locally in PowerShell on PC. Do not paste it into chat."
            )

        user_prompt = build_user_prompt(args, repo_root)

        output_text = call_openai_responses(
            api_key=api_key,
            model=args.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            reasoning_effort=args.reasoning_effort,
        )

        plan = parse_json_text(output_text)
        validate_plan(plan)

    output_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
