[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PhaseName,

    [Parameter(Mandatory = $true)]
    [string]$FailedCommand,

    [int]$ExitCode = 1,

    [string]$ErrorSummary = "",

    [string]$ErrorLog = "",

    [string]$OutputJson = "reports/supervisor_runs/latest.json",

    [string]$Model = "",

    [string]$ReasoningEffort = "",

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $savedKey = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
    if (-not [string]::IsNullOrWhiteSpace($savedKey)) {
        $env:OPENAI_API_KEY = $savedKey
    }
}


$argLines = @(
    "--phase-name", $PhaseName,
    "--failed-command", $FailedCommand,
    "--exit-code", "$ExitCode",
    "--output-json", $OutputJson
)

if (-not [string]::IsNullOrWhiteSpace($ErrorSummary)) {
    $argLines += @("--error-summary", $ErrorSummary)
}

if (-not [string]::IsNullOrWhiteSpace($ErrorLog)) {
    $argLines += @("--error-log", $ErrorLog)
}

if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $argLines += @("--model", $Model)
}

if (-not [string]::IsNullOrWhiteSpace($ReasoningEffort)) {
    $argLines += @("--reasoning-effort", $ReasoningEffort)
}

if ($DryRun) {
    $argLines += "--dry-run"
}

$argFile = Join-Path $env:TEMP ("jarvis_openai_supervisor_args_" + [guid]::NewGuid().ToString("N") + ".txt")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($argFile, $argLines, $utf8NoBom)

Write-Host "`n=== RUN JARVIS OPENAI SUPERVISOR ===" -ForegroundColor Cyan

try {
    python "tools/jarvis_openai_supervisor.py" "@$argFile"
    if ($LASTEXITCODE -ne 0) {
        throw "Jarvis OpenAI Supervisor failed."
    }
} finally {
    if (Test-Path $argFile) {
        Remove-Item -Force $argFile
    }
}
