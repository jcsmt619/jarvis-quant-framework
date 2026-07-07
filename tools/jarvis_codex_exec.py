from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


FORBIDDEN_FLAGS = (
    "--ask-for-approval",
    "--approval-policy",
)


def normalize_prompt_text(prompt_text: str) -> str:
    return prompt_text.lstrip("\ufeff")


def build_codex_args(*, sandbox: str) -> list[str]:
    args = ["codex", "exec"]

    if sandbox and sandbox != "default":
        args.extend(["--sandbox", sandbox])

    return args


def read_prompt(*, prompt: str, prompt_file: str) -> str:
    if prompt and prompt_file:
        raise ValueError("Use either --prompt or --prompt-file, not both.")

    if prompt_file:
        return normalize_prompt_text(
            Path(prompt_file).read_text(encoding="utf-8-sig", errors="replace")
        )

    if prompt:
        return normalize_prompt_text(prompt)

    stdin_text = sys.stdin.read()
    if stdin_text.strip():
        return normalize_prompt_text(stdin_text)

    raise ValueError("No prompt supplied. Use --prompt, --prompt-file, or stdin.")


def assert_safe_args(args: list[str]) -> None:
    joined = " ".join(args).lower()

    for flag in FORBIDDEN_FLAGS:
        if flag in joined:
            raise ValueError(f"Forbidden Codex CLI flag detected: {flag}")


def run_codex_exec(
    *,
    prompt_text: str,
    output_path: Path,
    sandbox: str,
    timeout_seconds: int,
) -> int:
    args = build_codex_args(sandbox=sandbox)
    assert_safe_args(args)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_prompt = normalize_prompt_text(prompt_text)

    try:
        completed = subprocess.run(
            args,
            input=safe_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        output_path.write_text(
            "Codex CLI not found on PATH. Run `codex --version` in PowerShell on PC.\n",
            encoding="utf-8",
        )
        return 127
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        output_path.write_text(
            "Codex exec timed out.\n\n"
            f"TIMEOUT_SECONDS: {timeout_seconds}\n\n"
            "STDOUT:\n"
            f"{stdout}\n\n"
            "STDERR:\n"
            f"{stderr}\n",
            encoding="utf-8",
        )
        return 124
    except Exception as exc:
        output_path.write_text(
            "Codex exec wrapper crashed before Codex completed.\n\n"
            f"ERROR_TYPE: {type(exc).__name__}\n"
            f"ERROR: {exc}\n",
            encoding="utf-8",
        )
        return 1

    combined = (
        "COMMAND:\n"
        + " ".join(args)
        + "\n\nEXIT_CODE:\n"
        + str(completed.returncode)
        + "\n\nSTDOUT:\n"
        + (completed.stdout or "")
        + "\n\nSTDERR:\n"
        + (completed.stderr or "")
    )

    output_path.write_text(combined, encoding="utf-8")
    print(combined)

    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis Codex exec compatibility wrapper")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--output-path", default="reports/codex_exec/latest.txt")
    parser.add_argument(
        "--sandbox",
        default="read-only",
        choices=["read-only", "workspace-write", "default"],
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    prompt_text = read_prompt(prompt=args.prompt, prompt_file=args.prompt_file)

    return run_codex_exec(
        prompt_text=prompt_text,
        output_path=Path(args.output_path),
        sandbox=args.sandbox,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
