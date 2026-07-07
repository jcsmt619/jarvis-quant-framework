[CmdletBinding()]
param(
    [string]$Prompt = "",

    [string]$PromptFile = "",

    [string]$OutputPath = "reports/codex_exec/latest.txt",

    [ValidateSet("read-only", "workspace-write", "default")]
    [string]$Sandbox = "read-only",

    [int]$TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$argsList = @(
    "tools/jarvis_codex_exec.py",
    "--output-path", $OutputPath,
    "--sandbox", $Sandbox,
    "--timeout-seconds", "$TimeoutSeconds"
)

if (-not [string]::IsNullOrWhiteSpace($PromptFile)) {
    $argsList += @("--prompt-file", $PromptFile)
} elseif (-not [string]::IsNullOrWhiteSpace($Prompt)) {
    $argsList += @("--prompt", $Prompt)
}

Write-Host "`n=== JARVIS CODEX EXEC WRAPPER ===" -ForegroundColor Cyan
python @argsList

if ($LASTEXITCODE -ne 0) {
    throw "Jarvis Codex exec wrapper failed with exit code $LASTEXITCODE."
}
