[CmdletBinding()]
param(
    [string]$ReviewPromptPath = "prompts/codex_safety_review.md",

    [string]$OutputPath = "reports/codex_safety_review_latest.txt",

    [string[]]$ChangedPath = @(),

    [switch]$RequireDiff,

    [switch]$RequireSafeToCommit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

Write-Host "`n=== JARVIS CODEX SAFETY REVIEW ===" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not read git branch."
}

Write-Host "Branch: $branch"

if (-not (Test-Path $ReviewPromptPath)) {
    throw "Review prompt not found: $ReviewPromptPath"
}

$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codexCommand) {
    throw "Codex CLI not found on PATH. Run this manually first in PowerShell on PC: codex"
}

if ($ChangedPath.Count -gt 0) {
    Write-Host "`n=== Register changed paths for review diff ===" -ForegroundColor Cyan
    foreach ($path in $ChangedPath) {
        if (-not (Test-Path $path)) {
            throw "Changed path does not exist: $path"
        }
        git add -N $path
    }
}

$diffNames = (& git diff --name-only)
if ($LASTEXITCODE -ne 0) {
    throw "Could not read git diff."
}

if ($RequireDiff -and [string]::IsNullOrWhiteSpace(($diffNames -join "`n"))) {
    throw "RequireDiff was set, but there is no working-tree diff to review."
}

$promptText = Get-Content -Raw -Path $ReviewPromptPath

$gitStatus = (& git status --short --untracked-files=all) -join "`n"
$gitDiffStat = (& git diff --stat) -join "`n"
$gitDiffNames = (& git diff --name-only) -join "`n"

$fullPrompt = @"
$promptText

Additional Jarvis automation instructions:
- This is a non-interactive safety review.
- Do not edit files.
- Do not modify code.
- Do not run destructive commands.
- Do not touch .env or secrets.
- Inspect the current working-tree diff only.
- Return SAFE TO COMMIT: YES only if no blocking safety issue exists.

Current git status:
$gitStatus

Current git diff stat:
$gitDiffStat

Current git diff files:
$gitDiffNames
"@

Write-Host "`n=== Running Codex read-only safety review ===" -ForegroundColor Cyan

$reviewOutput = & codex exec `
    --cd $RepoRoot `
    --sandbox read-only `
    --ask-for-approval never `
    $fullPrompt

$exitCode = $LASTEXITCODE

$reviewDir = Split-Path -Parent $OutputPath
if ($reviewDir -and -not (Test-Path $reviewDir)) {
    New-Item -ItemType Directory -Force -Path $reviewDir | Out-Null
}

$reviewOutput | Set-Content -Path $OutputPath -Encoding UTF8

Write-Host "`n=== CODEX REVIEW OUTPUT SAVED ===" -ForegroundColor Green
Write-Host $OutputPath

if ($exitCode -ne 0) {
    throw "Codex review failed with exit code $exitCode"
}

if ($RequireSafeToCommit) {
    $reviewText = ($reviewOutput -join "`n")
    if ($reviewText -notmatch "SAFE TO COMMIT:\s*YES") {
        throw "Codex review did not return SAFE TO COMMIT: YES"
    }
}

Write-Host "`n=== CODEX SAFETY REVIEW COMPLETE ===" -ForegroundColor Green
Get-Content -Path $OutputPath
