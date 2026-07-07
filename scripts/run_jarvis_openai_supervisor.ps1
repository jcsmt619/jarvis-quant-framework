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

$argsList = @(
    "tools/jarvis_openai_supervisor.py",
    "--phase-name", $PhaseName,
    "--failed-command", $FailedCommand,
    "--exit-code", "$ExitCode",
    "--output-json", $OutputJson
)

if (-not [string]::IsNullOrWhiteSpace($ErrorSummary)) {
    $argsList += @("--error-summary", $ErrorSummary)
}

if (-not [string]::IsNullOrWhiteSpace($ErrorLog)) {
    $argsList += @("--error-log", $ErrorLog)
}

if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $argsList += @("--model", $Model)
}

if (-not [string]::IsNullOrWhiteSpace($ReasoningEffort)) {
    $argsList += @("--reasoning-effort", $ReasoningEffort)
}

if ($DryRun) {
    $argsList += "--dry-run"
}

Write-Host "`n=== RUN JARVIS OPENAI SUPERVISOR ===" -ForegroundColor Cyan

python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Jarvis OpenAI Supervisor failed."
}
