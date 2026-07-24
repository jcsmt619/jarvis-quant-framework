# UI-05 Windows Desktop App

UI-05 wraps the completed UI-01 through UI-04 local application in a repository-owned Windows desktop launcher. It is an application-hosting and resilience phase only.

Safety state:
- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE
- provider_validation_status: pending
- is_live: false
- LIVE TRADING: DISABLED

UI-05 does not retry DXLink, promote BR-30 provider validation, configure providers, read secrets, enable live trading, submit broker orders, or change quant-engine behavior.

## Architecture

The launcher is implemented with Python standard-library components in `ui05_desktop_app`. It starts the existing UI-02 gateway, which starts UI-01 in dependency order on `127.0.0.1`. The gateway remains same-origin and read-only, keeps the restrictive CSP, and uses a memory-only local UI session token that is never placed in URLs, command lines, environment variables, logs, files, or browser profiles.

On Windows, the launcher prefers Microsoft Edge app mode, then Chrome app mode. If no Chromium-family app is found, the local gateway still runs and the existing browser fallback remains available from the UI-02 script.

The CLI, quant engine, research engines, tests, automation, Cline, Codex, and existing scripts remain independent. Closing the desktop app stops only UI processes created by UI-05.

## Operator Commands

Launch with an app window:

```powershell
python scripts/run_ui05_desktop_app.py launch --fixture
```

Launch without opening a browser window:

```powershell
python scripts/run_ui05_desktop_app.py launch --fixture --no-open
```

Use an explicit loopback port:

```powershell
python scripts/run_ui05_desktop_app.py launch --fixture --port 8765
```

Use sanitized recorded-response mode:

```powershell
python scripts/run_ui05_desktop_app.py launch --recorded-response
```

Run startup diagnostics:

```powershell
python scripts/run_ui05_desktop_app.py startup-health
```

Inspect a stale lock:

```powershell
python scripts/run_ui05_desktop_app.py inspect-lock
```

Remove only a stale UI-05 lock:

```powershell
python scripts/run_ui05_desktop_app.py clean-shutdown
```

Inspect sanitized local logs:

```powershell
python scripts/run_ui05_desktop_app.py logs --limit 40
```

Run the offline self-test:

```powershell
python scripts/run_ui05_desktop_app_self_test.py
```

These commands do not provide arbitrary shell execution, provider configuration, credential editing, order approval, order routing, position mutation, or trading controls.

## Install Shortcuts

The installer runs only when explicitly invoked by an operator. Tests and normal startup never create shortcuts.

Dry run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_ui05_windows_desktop_app.ps1 -DryRun
```

Create a Desktop shortcut:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_ui05_windows_desktop_app.ps1
```

Create Desktop and Start Menu shortcuts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_ui05_windows_desktop_app.ps1 -StartMenu
```

The installer does not require administrator privileges, edit the repository, install dependencies, download files, store credentials, enable provider access, or enable trading.

## Uninstall Shortcuts And Local UI-05 Data

Dry run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/uninstall_ui05_windows_desktop_app.ps1 -DryRun
```

Remove only UI-05-created shortcuts, stale locks, temporary profile remnants, and bounded sanitized logs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/uninstall_ui05_windows_desktop_app.ps1 -ConfirmRemove
```

The uninstaller must not remove the repository, Python installation, research evidence, provider credentials, trading records, Git data, or user documents.

## Logs

UI-05 stores only sanitized operational logs under local application data outside Git, normally:

```text
%LOCALAPPDATA%\JarvisQuant\UI05\logs\jarvis-ui05.log
```

Logs are bounded and rotated. They must not include credentials, tokens, authorization headers, account identifiers, raw provider payloads, personal data, or arbitrary environment variables.

## Stale Lock Recovery

UI-05 creates one atomic single-instance lock in the local application-data directory. If a prior process exits unexpectedly, run:

```powershell
python scripts/run_ui05_desktop_app.py inspect-lock
python scripts/run_ui05_desktop_app.py clean-shutdown
```

`clean-shutdown` removes only a stale UI-05 lock. It does not stop the independent quant engine, research engines, CLI, orchestrator, tests, or unrelated Python processes.

## Responsive Shell

UI-05 completes the deferred UI-04 table correction. Shared tables use contained horizontal scroll at laptop widths, readable column minimums, sticky headers, tabular numeric alignment, compact chips for long state labels, and compact card mode on narrow windows. The affected shared regions include Backtests, Models, Paper Activity, Screener, Options, Alerts, and the remaining UI-03/UI-04 data tables.
