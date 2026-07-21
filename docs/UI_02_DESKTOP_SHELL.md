# UI-02 Futuristic Desktop Shell and Navigation

UI-02 adds a local browser shell on top of UI-01. It is optional and independent: closing the shell or gateway does not stop the quant engine, existing CLI, PowerShell scripts, Python tests, Cline, or automation.

Safety status:
- RESEARCH_ONLY
- MONITOR_ONLY
- PAPER_ONLY
- HUMAN_REVIEW_REQUIRED
- BLOCKED_BY_SAFETY_GATE
- LIVE TRADING: DISABLED

Run locally:

```powershell
python scripts/run_ui02_desktop_shell.py --source-mode fixture --port 0 --no-open
```

Use `--source-mode recorded_response` to use committed sanitized recorded artifacts. UI-02 intentionally does not support live provider mode. Use `--open` to ask the installed browser to open the loopback URL after startup.

Security boundary:
- Binds only to `127.0.0.1`.
- Serves only repository-owned local HTML, CSS, and JavaScript.
- Adds a same-origin gateway at `/gateway/api/v1/...`.
- Proxies only approved UI-01 `GET`, `HEAD`, `OPTIONS`, and SSE endpoints.
- Rejects mutation methods, traversal, absolute upstream URLs, unknown destinations, malformed event resume metadata, and oversized headers.
- Keeps the UI-01 local session token in Python memory only. It is not exposed to browser JavaScript, HTML, URLs, logs, reports, command lines, environment variables, or files.
- Does not add npm, Python package, CDN, hosted font, analytics, telemetry, Electron, Tauri, WebView, PyInstaller, browser extension, or external network dependencies.

Accessibility notes:
- Semantic landmarks are used for banner, navigation, main workspace, and event rail.
- The shell supports keyboard navigation, focus-visible outlines, screen-reader status messages, and a command palette for local navigation only.
- Visual preferences for standard dark, reduced effects, and high contrast are held in memory only.
- `prefers-reduced-motion` disables animation sweeps.

Offline self-test:

```powershell
python scripts/run_ui02_desktop_shell_self_test.py
```

The self-test starts UI-01 fixture mode and UI-02 on ephemeral loopback ports, checks local assets, CSP, routes, read-only proxy endpoints, SSE replay/reconnect metadata, mutation rejection, token isolation, disabled live-trading guarantees, shutdown, and port release. It prints a bounded sanitized JSON envelope.
