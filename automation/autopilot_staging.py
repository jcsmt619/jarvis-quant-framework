from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


TEMPORARY_PATH_PARTS = {
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pyright_cache",
}

TEMPORARY_PATH_PREFIXES = (
    ".codex_pytest_tmp/",
    ".tmp/",
    "pytest_work/",
    "br10d_pytest_temp/",
    "reports/pytest-cache-files-",
    "reports/pytest-temp/",
    "reports/manual_repair/pytest-temp-",
)

TEMPORARY_PATH_SUFFIXES = (".pyc", ".pyo")


@dataclass(frozen=True)
class GitChange:
    path: str
    index_status: str
    worktree_status: str
    original_path: str | None = None

    @property
    def is_untracked(self) -> bool:
        return self.index_status == "?" and self.worktree_status == "?"

    @property
    def is_deleted(self) -> bool:
        return self.index_status == "D" or self.worktree_status == "D"

    @property
    def is_tracked_change(self) -> bool:
        return not self.is_untracked

    @property
    def is_rename(self) -> bool:
        return self.index_status == "R" or self.worktree_status == "R"


def normalize_repo_path(value: str) -> str:
    text = value.strip().strip('"').strip("'").replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def _decode_porcelain(raw: bytes | str) -> list[str]:
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="surrogateescape")
    else:
        text = raw
    return [item for item in text.split("\0") if item]


def parse_porcelain_z(raw: bytes | str) -> list[GitChange]:
    """Parse `git status --porcelain=v1 -z` records.

    Rename/copy entries in `-z` mode provide the new path first and the old path
    as the following NUL-delimited field.
    """

    fields = _decode_porcelain(raw)
    changes: list[GitChange] = []
    index = 0
    while index < len(fields):
        field = fields[index]
        if len(field) < 3:
            index += 1
            continue

        index_status = field[0]
        worktree_status = field[1]
        path = normalize_repo_path(field[3:])
        original_path: str | None = None
        index += 1

        if index_status in {"R", "C"} or worktree_status in {"R", "C"}:
            if index < len(fields):
                original_path = normalize_repo_path(fields[index])
                index += 1

        changes.append(
            GitChange(
                path=path,
                index_status=index_status,
                worktree_status=worktree_status,
                original_path=original_path,
            )
        )

    return changes


def run_git_status(repo: Path) -> bytes:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def discover_changes(repo: Path) -> list[GitChange]:
    return parse_porcelain_z(run_git_status(repo))


def is_temporary_artifact_path(path_text: str) -> bool:
    path = normalize_repo_path(path_text)
    parts = set(Path(path).parts)
    if parts & TEMPORARY_PATH_PARTS:
        return True
    if path.endswith(TEMPORARY_PATH_SUFFIXES):
        return True
    return any(path.startswith(prefix) for prefix in TEMPORARY_PATH_PREFIXES)


def is_disposable_untracked_artifact(change: GitChange) -> bool:
    return change.is_untracked and is_temporary_artifact_path(change.path)


def intended_phase_paths(changes: Iterable[GitChange]) -> list[str]:
    paths: list[str] = []
    for change in changes:
        if is_disposable_untracked_artifact(change):
            continue
        if change.path not in paths:
            paths.append(change.path)
    return sorted(paths)


def _normalized_set(paths: Iterable[str]) -> set[str]:
    return {normalize_repo_path(path) for path in paths if normalize_repo_path(path)}


def unexpected_paths(changes: Iterable[GitChange], intended_paths: Iterable[str]) -> list[str]:
    intended = _normalized_set(intended_paths)
    unexpected: list[str] = []
    for change in changes:
        if is_disposable_untracked_artifact(change):
            continue
        if change.path not in intended:
            unexpected.append(change.path)
    return sorted(set(unexpected))


def missing_changed_paths(changes: Iterable[GitChange], intended_paths: Iterable[str]) -> list[str]:
    changed = {change.path for change in changes}
    missing = _normalized_set(intended_paths) - changed
    return sorted(missing)


def normalize_eof_whitespace(repo: Path, paths: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for path_text in paths:
        path = repo / normalize_repo_path(path_text)
        if not path.exists() or not path.is_file():
            continue

        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

        crlf_count = raw.count(b"\r\n")
        lf_only_count = raw.count(b"\n") - crlf_count
        newline = "\r\n" if crlf_count > lf_only_count else "\n"
        repaired = text.rstrip() + newline
        if repaired != text:
            path.write_text(repaired, encoding="utf-8", newline="")
            normalized.append(normalize_repo_path(path_text))
    return normalized


def _changes_payload(changes: Sequence[GitChange]) -> list[dict[str, object]]:
    return [
        {
            "path": change.path,
            "index_status": change.index_status,
            "worktree_status": change.worktree_status,
            "original_path": change.original_path,
            "is_untracked": change.is_untracked,
            "is_deleted": change.is_deleted,
            "is_temporary_untracked": is_disposable_untracked_artifact(change),
        }
        for change in changes
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jarvis autopilot staging guard.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover")
    discover.add_argument("--repo", default=".")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--repo", default=".")
    validate.add_argument("paths", nargs="*")

    normalize = subparsers.add_parser("normalize-eof")
    normalize.add_argument("--repo", default=".")
    normalize.add_argument("paths", nargs="*")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()

    if args.command == "discover":
        changes = discover_changes(repo)
        payload = {
            "changes": _changes_payload(changes),
            "intended_paths": intended_phase_paths(changes),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "validate":
        changes = discover_changes(repo)
        unexpected = unexpected_paths(changes, args.paths)
        if unexpected:
            print("Unexpected changed paths:")
            for path in unexpected:
                print(path)
            return 1
        return 0

    if args.command == "normalize-eof":
        for path in normalize_eof_whitespace(repo, args.paths):
            print(path)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
