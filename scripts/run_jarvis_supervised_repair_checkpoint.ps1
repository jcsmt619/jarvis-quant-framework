[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PhaseName,

    [Parameter(Mandatory = $true)]
    [string]$CommandText,

    [string[]]$ChangedPath = @(),

    [string[]]$FocusedTest = @(),

    [string[]]$CompilePath = @(),

    [string]$CommitMessage = "",

    [int]$MaxRepairAttempts = 1,

    [switch]$AutoRepairWithCodex,

    [switch]$DryRunSupervisor,

    [switch]$PlanOnly,

    [switch]$Commit,

    [switch]$PushBranch,

    [switch]$AllowMain
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
    } catch {
        $output = $_ | Out-String
        $exitCode = 1
    } finally {
        $ErrorActionPreference = $oldPreference
    }

    if ($null -eq $exitCode) {
        $exitCode = 0
    }

    ($output | Out-String) | Set-Content -Path $LogPath -Encoding UTF8

    return @{
        ExitCode = [int]$exitCode
        Output = ($output | Out-String)
    }
}

function Invoke-JarvisCheckpoint {
    if (-not $Commit) {
        Write-Host "`n=== COMMIT DISABLED; SKIPPING CHECKPOINT COMMIT ===" -ForegroundColor Yellow
        return
    }

    if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
        throw "Commit was requested, but CommitMessage is empty. STOP."
    }

    if ($ChangedPath.Count -eq 0) {
        throw "Commit was requested, but ChangedPath is empty. STOP."
    }

    $branch = (& git branch --show-current).Trim()
    if ($branch -eq "main" -and -not $AllowMain) {
        throw "Refusing supervised repair checkpoint commit on main. Use a branch. STOP."
    }

    $checkpointArgs = @{
        PhaseName = $PhaseName
        ChangedPath = $ChangedPath
        CommitMessage = $CommitMessage
        Commit = $true
    }

    if ($CompilePath.Count -gt 0) {
        $checkpointArgs["CompilePath"] = $CompilePath
    }

    if ($FocusedTest.Count -gt 0) {
        $checkpointArgs["FocusedTest"] = $FocusedTest
    }

    if ($PushBranch) {
        $checkpointArgs["PushBranch"] = $true
    }

    .\scripts\run_jarvis_phase_checkpoint.ps1 @checkpointArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Jarvis phase checkpoint failed. STOP."
    }
}

$runDir = "reports/supervised_repair"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Write-Host "`n=== JARVIS SUPERVISED REPAIR CHECKPOINT ===" -ForegroundColor Cyan
Write-Host "Phase: $PhaseName"
Write-Host "AutoRepairWithCodex: $AutoRepairWithCodex"
Write-Host "DryRunSupervisor: $DryRunSupervisor"
Write-Host "PlanOnly: $PlanOnly"

$attempt = 0

while ($attempt -le $MaxRepairAttempts) {
    $attempt += 1

    $commandLog = Join-Path $runDir "command_attempt_$attempt.log"
    $result = Invoke-CommandCapture -Text $CommandText -LogPath $commandLog

    if ($result.ExitCode -eq 0) {
        Write-Host "`n=== COMMAND PASSED ===" -ForegroundColor Green
        Invoke-JarvisCheckpoint
        exit 0
    }

    Write-Host "`n=== COMMAND FAILED; ASKING OPENAI SUPERVISOR ===" -ForegroundColor Yellow

    $planPath = Join-Path $runDir "supervisor_plan_attempt_$attempt.json"

    $supervisorArgs = @{
        PhaseName = $PhaseName
        FailedCommand = $CommandText
        ExitCode = [int]$result.ExitCode
        ErrorLog = $commandLog
        OutputJson = $planPath
    }

    if ($DryRunSupervisor) {
        $supervisorArgs["DryRun"] = $true
    }

    .\scripts\run_jarvis_openai_supervisor.ps1 @supervisorArgs
    if ($LASTEXITCODE -ne 0) {
        throw "OpenAI supervisor failed. STOP."
    }

    $plan = Get-Content -Raw -Path $planPath | ConvertFrom-Json

    if ($plan.dangerous_action_detected -eq $true) {
        Get-Content -Path $planPath
        throw "Supervisor detected dangerous action. STOP."
    }

    if ($plan.safe_to_patch -ne $true) {
        Get-Content -Path $planPath
        throw "Supervisor did not mark safe_to_patch=true. STOP."
    }

    if ($PlanOnly) {
        Write-Host "`n=== PLAN ONLY MODE COMPLETE ===" -ForegroundColor Green
        Get-Content -Path $planPath
        exit 0
    }

    if (-not $AutoRepairWithCodex) {
        Write-Host "`n=== SUPERVISOR PLAN READY; AUTO-REPAIR DISABLED ===" -ForegroundColor Yellow
        Get-Content -Path $planPath
        throw "Command failed and supervisor plan was created, but -AutoRepairWithCodex was not enabled."
    }

    if ($attempt -gt $MaxRepairAttempts) {
        throw "Max repair attempts exceeded. STOP."
    }

    $repairPromptPath = Join-Path $runDir "repair_prompt_attempt_$attempt.txt"
    $plan.repair_prompt_for_agent | Set-Content -Path $repairPromptPath -Encoding UTF8

    $codexLog = Join-Path $runDir "codex_repair_attempt_$attempt.log"

    Write-Host "`n=== RUN CODEX REPAIR THROUGH COMPATIBILITY WRAPPER ===" -ForegroundColor Cyan

    python tools\jarvis_codex_exec.py `
        --prompt-file $repairPromptPath `
        --output-path $codexLog `
        --sandbox workspace-write `
        --timeout-seconds 300

    $codexExit = $LASTEXITCODE

    if ($codexExit -ne 0) {
        Get-Content -Path $codexLog
        throw "Codex repair failed. STOP."
    }

    Write-Host "`n=== CODEX REPAIR COMPLETE; RERUNNING ORIGINAL COMMAND ===" -ForegroundColor Cyan
}

throw "Supervised repair loop exited unexpectedly. STOP."
