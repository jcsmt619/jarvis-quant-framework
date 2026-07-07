[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PhaseName,

    [Parameter(Mandatory = $true)]
    [string]$CommandText,

    [string]$OutputJson = "reports/supervisor_runs/latest.json",

    [switch]$AutoRepairWithCodex,

    [int]$MaxRepairAttempts = 1,

    [ValidateSet("default", "workspace-write", "read-only")]
    [string]$CodexRepairSandbox = "workspace-write"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Invoke-CommandCapture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,

        [Parameter(Mandatory = $true)]
        [string]$LogPath
    )

    Write-Host "`n=== RUN COMMAND ===" -ForegroundColor Cyan
    Write-Host $Text

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $output = Invoke-Expression $Text 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }

    if ($null -eq $exitCode) {
        $exitCode = 0
    }

    ($output | Out-String) | Set-Content -Path $LogPath -Encoding UTF8

    return @{
        ExitCode = $exitCode
        Output = ($output | Out-String)
    }
}

$runDir = "reports/supervisor_runs"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$attempt = 0

while ($attempt -le $MaxRepairAttempts) {
    $attempt += 1
    $logPath = Join-Path $runDir "command_attempt_$attempt.log"

    $result = Invoke-CommandCapture -Text $CommandText -LogPath $logPath

    if ($result.ExitCode -eq 0) {
        Write-Host "`n=== SUPERVISOR LOOP COMMAND PASSED ===" -ForegroundColor Green
        Get-Content -Path $logPath
        exit 0
    }

    Write-Host "`n=== COMMAND FAILED: ASKING OPENAI SUPERVISOR ===" -ForegroundColor Yellow

    .\scripts\run_jarvis_openai_supervisor.ps1 `
        -PhaseName $PhaseName `
        -FailedCommand $CommandText `
        -ExitCode $result.ExitCode `
        -ErrorLog $logPath `
        -OutputJson $OutputJson

    $plan = Get-Content -Raw -Path $OutputJson | ConvertFrom-Json

    if ($plan.safe_to_patch -ne $true -or $plan.dangerous_action_detected -eq $true) {
        throw "Supervisor refused auto patch. STOP."
    }

    if (-not $AutoRepairWithCodex) {
        Write-Host "`n=== SUPERVISOR PLAN READY; AUTO-REPAIR DISABLED ===" -ForegroundColor Yellow
        Get-Content -Path $OutputJson
        throw "Command failed and supervisor plan was created, but -AutoRepairWithCodex was not enabled."
    }

    if ($attempt -gt $MaxRepairAttempts) {
        throw "Max repair attempts exceeded. STOP."
    }

    $repairPromptPath = Join-Path $runDir "repair_prompt_attempt_$attempt.txt"
    $plan.repair_prompt_for_agent | Set-Content -Path $repairPromptPath -Encoding UTF8

    Write-Host "`n=== RUN CODEX REPAIR ATTEMPT $attempt THROUGH COMPATIBILITY WRAPPER ===" -ForegroundColor Cyan

    $codexLog = Join-Path $runDir "codex_repair_attempt_$attempt.log"

    python tools\jarvis_codex_exec.py `
        --prompt-file $repairPromptPath `
        --output-path $codexLog `
        --sandbox $CodexRepairSandbox `
        --timeout-seconds 300

    $codexExit = $LASTEXITCODE

    if ($codexExit -ne 0) {
        Get-Content -Path $codexLog
        throw "Codex repair attempt failed. STOP."
    }

    Write-Host "`n=== CODEX REPAIR ATTEMPT COMPLETE; RERUNNING ORIGINAL COMMAND ===" -ForegroundColor Cyan
}

throw "Supervisor loop exited unexpectedly."
