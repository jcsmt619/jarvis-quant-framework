from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence


USAGE_LIMIT_MARKERS = (
    "usage limit",
    "purchase more credits",
    "try again at",
    "you've hit your usage limit",
)

EOF_BLANK_LINE_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?[^:\r\n]+?\.py):\d+: new blank line at EOF\.",
    re.IGNORECASE,
)

SOURCE_PREFIXES = (
    "automation/",
    "core/",
    "scripts/",
    "tests/",
    "tools/",
)

REPORT_ROOT = Path("reports/autonomous_orchestrator_v2")


@dataclass(frozen=True)
class CommandResult:
    command: Sequence[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part)


def utc_stamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def normalize_repo_path(value: str) -> str:
    text = value.strip().strip('"').strip("'").replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", text):
        cwd = Path.cwd().as_posix()
        if text.lower().startswith(cwd.lower() + "/"):
            text = text[len(cwd) + 1 :]
    while text.startswith("./"):
        text = text[2:]
    return text


def parse_eof_blank_line_paths(output: str) -> list[str]:
    paths: list[str] = []
    for match in EOF_BLANK_LINE_RE.finditer(output):
        normalized = normalize_repo_path(match.group("path"))
        if normalized not in paths:
            paths.append(normalized)
    return paths


def output_contains_usage_limit(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in USAGE_LIMIT_MARKERS)


def ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def ps_array(values: Iterable[str]) -> str:
    items = list(values)
    if not items:
        return "@()"
    return "@(" + ", ".join(ps_quote(item) for item in items) + ")"



def _safe_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int | None = None,
) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            env={
                **os.environ,
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            },
        )
        return CommandResult(
            command=tuple(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=tuple(command),
            returncode=124,
            stdout=_safe_text(exc.stdout),
            stderr=_safe_text(exc.stderr) + f"\nTIMEOUT after {timeout_seconds} seconds",
        )


def run_powershell(
    script: str,
    *,
    cwd: Path,
    timeout_seconds: int | None = None,
) -> CommandResult:
    return run_command(
        (
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ),
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_ledger(log_dir: Path, text: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    ledger = log_dir / "orchestrator_ledger.md"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n\n")


def load_queue(queue_path: Path) -> list[dict[str, object]]:
    data = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise RuntimeError(f"Expected queue list at {queue_path}")
    return [
        item
        for item in data
        if isinstance(item, dict) and isinstance(item.get("phase"), str)
    ]


def find_phase_index(queue: list[dict[str, object]], start_phase: str) -> int:
    for index, item in enumerate(queue):
        if item.get("phase") == start_phase:
            return index
    raise RuntimeError(f"Start phase not found in queue: {start_phase}")


def git_current_branch(repo: Path) -> str:
    result = run_command(("git", "branch", "--show-current"), cwd=repo)
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)
    return result.stdout.strip()


def git_status_short(repo: Path) -> str:
    result = run_command(("git", "status", "--short", "--untracked-files=all"), cwd=repo)
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)
    return result.stdout.strip()


def assert_clean_repo(repo: Path) -> None:
    status = git_status_short(repo)
    if status:
        raise RuntimeError("Repo is not clean:\n" + status)


def checkout_clean_main(repo: Path) -> None:
    result = run_command(("git", "checkout", "main"), cwd=repo)
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)
    result = run_command(("git", "pull", "origin", "main"), cwd=repo)
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)
    assert_clean_repo(repo)


def status_paths(repo: Path) -> list[str]:
    result = run_command(("git", "status", "--short", "--untracked-files=all"), cwd=repo)
    if result.returncode != 0:
        raise RuntimeError(result.combined_output)

    paths: list[str] = []
    for raw in result.stdout.splitlines():
        line = raw.rstrip()
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        normalized = normalize_repo_path(path)
        if normalized and normalized not in paths:
            paths.append(normalized)
    return paths


def changed_source_paths(repo: Path) -> list[str]:
    paths: list[str] = []
    for path in status_paths(repo):
        if path.startswith(SOURCE_PREFIXES) and (repo / path).exists():
            paths.append(path)
    return sorted(set(paths))


def trim_extra_blank_line_at_eof(repo: Path, paths: Iterable[str]) -> list[str]:
    fixed: list[str] = []
    for path_text in paths:
        normalized = normalize_repo_path(path_text)
        path = repo / normalized
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        fixed.append(normalized)
    return fixed


def run_autopilot_for_phase(repo: Path, phase: str, timeout_seconds: int) -> CommandResult:
    script = f"""
.\\scripts\\run_jarvis_master_plan_autopilot.ps1 `
    -StartPhase {ps_quote(phase)} `
    -MaxPhases 1 `
    -Execute `
    -AutoRepairWithCodex `
    -Commit `
    -PushBranch `
    -MergeToMain
"""
    return run_powershell(script, cwd=repo, timeout_seconds=timeout_seconds)


def precheck_after_eof_fix(
    repo: Path,
    *,
    changed_paths: list[str],
    timeout_seconds: int,
) -> CommandResult:
    compile_paths = [path for path in changed_paths if path.endswith(".py")]
    focused_tests = [
        path
        for path in changed_paths
        if path.startswith("tests/") and path.endswith(".py")
    ]

    script_parts = [
        "git add -- " + " ".join(ps_quote(path) for path in changed_paths),
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        "git diff --cached --check -- " + " ".join(ps_quote(path) for path in changed_paths),
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
    ]

    if compile_paths:
        script_parts.extend(
            [
                "python -m py_compile " + " ".join(ps_quote(path) for path in compile_paths),
                "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
            ]
        )

    if focused_tests:
        script_parts.extend(
            [
                "python -m pytest " + " ".join(ps_quote(path) for path in focused_tests) + " -q",
                "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
            ]
        )

    script_parts.extend(
        [
            "python scripts\\check_jarvis_safety_scanner.py "
            + " ".join(ps_quote(path) for path in changed_paths),
            "exit $LASTEXITCODE",
        ]
    )

    return run_powershell(
        "\n".join(script_parts),
        cwd=repo,
        timeout_seconds=timeout_seconds,
    )


def run_phase_checkpoint_repair(
    repo: Path,
    *,
    phase: str,
    title: str,
    commit_message: str,
    changed_paths: list[str],
    timeout_seconds: int,
) -> CommandResult:
    compile_paths = [path for path in changed_paths if path.endswith(".py")]
    focused_tests = [
        path
        for path in changed_paths
        if path.startswith("tests/") and path.endswith(".py")
    ]
    phase_name = f"{phase} {title}".strip()

    script = f"""
.\\scripts\\run_jarvis_phase_checkpoint.ps1 `
    -PhaseName {ps_quote(phase_name)} `
    -CompilePath {ps_array(compile_paths)} `
    -FocusedTest {ps_array(focused_tests)} `
    -ChangedPath {ps_array(changed_paths)} `
    -CommitMessage {ps_quote(commit_message)} `
    -Commit `
    -PushBranch
"""
    return run_powershell(script, cwd=repo, timeout_seconds=timeout_seconds)


def run_merge_after_repair(
    repo: Path,
    *,
    phase: str,
    title: str,
    branch: str,
    timeout_seconds: int,
) -> CommandResult:
    merge_message = f"merge {phase} {title}".strip()
    script = f"""
git checkout main
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}

git pull origin main
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}

git merge --no-ff {ps_quote(branch)} -m {ps_quote(merge_message)}
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}

python -m pytest tests/ -q
if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }}

git push origin main
exit $LASTEXITCODE
"""
    return run_powershell(script, cwd=repo, timeout_seconds=timeout_seconds)


def attempt_eof_repair(
    repo: Path,
    *,
    phase_item: dict[str, object],
    failed_output: str,
    log_dir: Path,
    timeout_seconds: int,
) -> bool:
    phase = str(phase_item["phase"])
    title = str(phase_item.get("title", ""))
    commit_message = str(phase_item.get("commit_message", f"feat: complete {phase}"))

    eof_paths = parse_eof_blank_line_paths(failed_output)
    if not eof_paths:
        return False

    append_ledger(
        log_dir,
        f"### {utc_stamp()} EOF repair detected for {phase}\n\n"
        + "\n".join(f"- `{path}`" for path in eof_paths),
    )

    fixed = trim_extra_blank_line_at_eof(repo, eof_paths)
    if not fixed:
        append_ledger(log_dir, f"### {utc_stamp()} EOF repair failed: no files fixed.")
        return False

    changed = changed_source_paths(repo)
    if not changed:
        changed = sorted(set(fixed))

    precheck = precheck_after_eof_fix(
        repo,
        changed_paths=changed,
        timeout_seconds=timeout_seconds,
    )
    write_text(log_dir / f"{phase}_eof_precheck.log", precheck.combined_output)
    if precheck.returncode != 0:
        append_ledger(log_dir, f"### {utc_stamp()} EOF precheck failed for {phase}.")
        return False

    branch = git_current_branch(repo)

    checkpoint = run_phase_checkpoint_repair(
        repo,
        phase=phase,
        title=title,
        commit_message=commit_message,
        changed_paths=changed,
        timeout_seconds=timeout_seconds,
    )
    write_text(log_dir / f"{phase}_eof_checkpoint.log", checkpoint.combined_output)
    if checkpoint.returncode != 0:
        append_ledger(log_dir, f"### {utc_stamp()} EOF checkpoint repair failed for {phase}.")
        return False

    merge = run_merge_after_repair(
        repo,
        phase=phase,
        title=title,
        branch=branch,
        timeout_seconds=timeout_seconds,
    )
    write_text(log_dir / f"{phase}_eof_merge.log", merge.combined_output)
    if merge.returncode != 0:
        append_ledger(log_dir, f"### {utc_stamp()} EOF repair merge failed for {phase}.")
        return False

    append_ledger(log_dir, f"### {utc_stamp()} EOF repair completed for {phase}.")
    return True


def phase_summary(item: dict[str, object]) -> str:
    return f"{item.get('phase')} - {item.get('title')}"


def run_orchestrator(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    queue_path = repo / "config" / "jarvis_master_plan_queue.json"
    queue = load_queue(queue_path)
    start_index = find_phase_index(queue, args.start_phase)

    run_id = utc_stamp()
    log_dir = repo / REPORT_ROOT / run_id
    log_dir.mkdir(parents=True, exist_ok=True)

    append_ledger(
        log_dir,
        "# Jarvis Autonomous Orchestrator V2\n\n"
        f"- run_id: `{run_id}`\n"
        f"- start_phase: `{args.start_phase}`\n"
        f"- max_phases: `{args.max_phases}`\n",
    )

    completed = 0
    index = start_index
    usage_limit_sleeps = 0

    while index < len(queue) and completed < args.max_phases:
        phase_item = queue[index]
        phase = str(phase_item["phase"])

        append_ledger(log_dir, f"## {utc_stamp()} Starting {phase_summary(phase_item)}")

        try:
            checkout_clean_main(repo)
        except Exception as exc:
            write_text(log_dir / f"{phase}_clean_main_failed.txt", str(exc))
            append_ledger(log_dir, f"### STOP: main is not clean before {phase}.")
            print(f"STOP: main is not clean before {phase}. See {log_dir}")
            return 1

        result = run_autopilot_for_phase(
            repo,
            phase=phase,
            timeout_seconds=args.phase_timeout_seconds,
        )
        write_text(log_dir / f"{phase}_autopilot.log", result.combined_output)

        if result.returncode == 0:
            append_ledger(log_dir, f"### {utc_stamp()} Completed {phase_summary(phase_item)}")
            completed += 1
            index += 1
            usage_limit_sleeps = 0
            continue

        output = result.combined_output

        if output_contains_usage_limit(output):
            append_ledger(log_dir, f"### {utc_stamp()} Codex usage limit detected for {phase}.")
            if usage_limit_sleeps >= args.max_codex_limit_sleeps:
                append_ledger(log_dir, "### STOP: maximum Codex usage-limit sleeps reached.")
                print(f"STOP: Codex usage limit persisted. See {log_dir}")
                return 2

            usage_limit_sleeps += 1
            sleep_seconds = max(1, args.codex_limit_sleep_minutes) * 60
            append_ledger(
                log_dir,
                f"Sleeping {args.codex_limit_sleep_minutes} minutes before retry "
                f"{usage_limit_sleeps}/{args.max_codex_limit_sleeps}.",
            )
            print(
                f"Codex usage limit detected for {phase}. "
                f"Sleeping {args.codex_limit_sleep_minutes} minutes. "
                f"Log dir: {log_dir}"
            )
            time.sleep(sleep_seconds)
            continue

        repaired = attempt_eof_repair(
            repo,
            phase_item=phase_item,
            failed_output=output,
            log_dir=log_dir,
            timeout_seconds=args.phase_timeout_seconds,
        )
        if repaired:
            completed += 1
            index += 1
            usage_limit_sleeps = 0
            continue

        append_ledger(
            log_dir,
            f"### STOP: unknown failure for {phase}. See `{phase}_autopilot.log`.",
        )
        print(f"STOP: unknown failure for {phase}. See {log_dir}")
        return 1

    append_ledger(log_dir, f"## {utc_stamp()} Orchestrator complete. Completed phases: {completed}.")
    print(f"JARVIS AUTONOMOUS ORCHESTRATOR V2 COMPLETE: completed_phases={completed}")
    print(f"LOG_DIR: {log_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent Jarvis master-plan autonomous orchestrator v2.")
    parser.add_argument("--repo", default=".", help="Repo root. Defaults to current directory.")
    parser.add_argument("--start-phase", required=True, help="First queue phase to run.")
    parser.add_argument("--max-phases", type=int, default=1, help="Maximum phases to complete in this run.")
    parser.add_argument("--phase-timeout-seconds", type=int, default=3600)
    parser.add_argument("--codex-limit-sleep-minutes", type=int, default=20)
    parser.add_argument("--max-codex-limit-sleeps", type=int, default=12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_orchestrator(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
