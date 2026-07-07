from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

_UNSAFE_LABELS = (
    "BUY" + "_NOW",
    "SELL" + "_NOW",
    "EXECUTE" + "_TRADE",
    "AUTO" + "_TRADE",
)

_SKIPPED_PATH_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}

_SKIPPED_SUFFIXES = {
    ".zip",
    ".parquet",
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
}

_SECRET_FILE_NAMES = {".env"}

_ALLOWLIST_FRAGMENTS = (
    "Do not touch .env",
    "Do not modify .env",
    "any .env/API key/secret access",
    "No .env",
    "not touch .env",
    "not access secrets",
    "Safety review",
    "safety scan",
    "Safety scanner",
    "Dangerous pattern found",
    "AllowDangerousPatterns",
    "dangerousPatterns",
    "Autopilot does not mean",
    "broker order submission",
    "Do not submit broker orders",
    "Do not enable live trading",
    "LIVE TRADING: DISABLED",
    "SAFETY_SCANNER_RULE",
)


@dataclass(frozen=True)
class SafetyRule:
    rule_id: str
    description: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class SafetyFinding:
    path: str
    line_number: int
    rule_id: str
    description: str
    excerpt: str


@dataclass(frozen=True)
class SafetyScanResult:
    findings: list[SafetyFinding]
    scanned_files: int
    skipped_files: list[str]

    @property
    def passed(self) -> bool:
        return not self.findings


SAFETY_RULES = (
    SafetyRule(
        rule_id="LIVE_TRADING_ENABLEMENT",
        description="Blocks live-trading enablement flags.",
        pattern=re.compile(
            r"(live_trading_" + r"enabled\s*[:=]\s*True|LIVE TRADING:\s*ENABLED|paper\s*=\s*False)",
            re.IGNORECASE,
        ),
    ),
    SafetyRule(
        rule_id="BROKER_ORDER_SUBMISSION",
        description="Blocks broker order submission calls.",
        pattern=re.compile(
            r"\b(submit_" + r"order|place_" + r"order|create_" + r"order)\s*\(",
            re.IGNORECASE,
        ),
    ),
    SafetyRule(
        rule_id="SECRET_FILE_ACCESS",
        description="Blocks direct secret-file reads or writes.",
        pattern=re.compile(
            r"\b(Get-Content|Set-Content|cat|type|open|read_text|write_text)\b.*\." + r"env\b",
            re.IGNORECASE,
        ),
    ),
    SafetyRule(
        rule_id="SECRET_ASSIGNMENT_OR_EXPOSURE",
        description="Blocks newly assigned secret-looking values.",
        pattern=re.compile(
            r"\b(API_" + r"KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)\b\s*[:=]\s*['\"][^'\"]+['\"]",
            re.IGNORECASE,
        ),
    ),
    SafetyRule(
        rule_id="UNSAFE_TRADE_LABEL",
        description="Blocks prohibited trade-action labels.",
        pattern=re.compile(r"\b(" + "|".join(re.escape(label) for label in _UNSAFE_LABELS) + r")\b"),
    ),
    SafetyRule(
        rule_id="TEST_BYPASS",
        description="Blocks checkpoint or test-bypass switches.",
        pattern=re.compile(
            r"\b(skip_" + r"tests|bypass_" + r"tests|AllowDangerousPatterns)\b\s*[:=]\s*(true|True|1)",
            re.IGNORECASE,
        ),
    ),
)


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _should_skip_path(path: Path) -> bool:
    if path.name in _SECRET_FILE_NAMES:
        return True

    parts = set(path.parts)
    if parts & _SKIPPED_PATH_PARTS:
        return True

    return path.suffix.lower() in _SKIPPED_SUFFIXES


def _is_allowlisted(line: str) -> bool:
    return any(fragment in line for fragment in _ALLOWLIST_FRAGMENTS)


def _redact_excerpt(line: str) -> str:
    redacted = re.sub(
        r"(?i)(API_" + r"KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)(\s*[:=]\s*)['\"][^'\"]+['\"]",
        r"\1\2[REDACTED]",
        line.strip(),
    )
    return redacted[:220]


def _scan_line(*, path: str, line_number: int, line: str) -> list[SafetyFinding]:
    if _is_allowlisted(line):
        return []

    findings: list[SafetyFinding] = []
    for rule in SAFETY_RULES:
        if rule.pattern.search(line):
            findings.append(
                SafetyFinding(
                    path=path,
                    line_number=line_number,
                    rule_id=rule.rule_id,
                    description=rule.description,
                    excerpt=_redact_excerpt(line),
                )
            )
    return findings


def scan_paths(paths: list[Path], *, repo_root: Path = REPO_ROOT) -> SafetyScanResult:
    findings: list[SafetyFinding] = []
    skipped_files: list[str] = []
    scanned_files = 0

    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else repo_root / raw_path
        rel_path = _repo_relative(path)

        if _should_skip_path(path):
            skipped_files.append(rel_path)
            continue

        if not path.exists() or not path.is_file():
            skipped_files.append(rel_path)
            continue

        scanned_files += 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            skipped_files.append(rel_path)
            continue

        for line_number, line in enumerate(lines, start=1):
            findings.extend(_scan_line(path=rel_path, line_number=line_number, line=line))

    return SafetyScanResult(
        findings=findings,
        scanned_files=scanned_files,
        skipped_files=skipped_files,
    )


def scan_git_diff(paths: list[Path], *, repo_root: Path = REPO_ROOT) -> SafetyScanResult:
    command = ["git", "diff", "-U0", "--", *[str(path) for path in paths]]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    findings: list[SafetyFinding] = []
    skipped_files: list[str] = []
    current_path = ""
    new_line_number = 0
    scanned_files: set[str] = set()

    for raw_line in completed.stdout.splitlines():
        if raw_line.startswith("+++ b/"):
            current_path = raw_line.removeprefix("+++ b/")
            path = repo_root / current_path
            if _should_skip_path(path):
                skipped_files.append(current_path)
            else:
                scanned_files.add(current_path)
            continue

        if raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,\d+)?", raw_line)
            new_line_number = int(match.group(1)) if match else 0
            continue

        if not raw_line.startswith("+") or raw_line.startswith("+++"):
            continue

        if not current_path or current_path in skipped_files:
            new_line_number += 1
            continue

        line = raw_line[1:]
        findings.extend(_scan_line(path=current_path, line_number=new_line_number, line=line))
        new_line_number += 1

    return SafetyScanResult(
        findings=findings,
        scanned_files=len(scanned_files),
        skipped_files=sorted(set(skipped_files)),
    )
