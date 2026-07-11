[CmdletBinding()]
param(
    [string]$StartPhase = "10D",

    [int]$MaxPhases = 1,

    [switch]$AutoRepairWithCodex,

    [switch]$Commit,

    [switch]$PushBranch,

    [switch]$MergeToMain,

    [switch]$Execute,

    [switch]$DryRun,

    [switch]$AllowMain,

    [string]$QueuePath = "config/jarvis_master_plan_queue.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Stop-IfUnsafeAutopilotRequest {
    $branch = (& git branch --show-current).Trim()

    if ($branch -eq "main" -and -not $AllowMain) {
        Write-Host "Current branch is main. Autopilot will create/check out phase branches before edits." -ForegroundColor Yellow
    }

    if (-not $Execute) {
        Write-Host "`n=== DRY CONTROL MODE ===" -ForegroundColor Yellow
        Write-Host "Autopilot did not execute because -Execute was not supplied."
        Write-Host "Use -Execute only when you want Jarvis to start applying roadmap phases."
    }

    if ($MergeToMain -and -not $Commit) {
        throw "MergeToMain requires Commit. STOP."
    }

    if ($PushBranch -and -not $Commit) {
        throw "PushBranch requires Commit. STOP."
    }
}

function Get-QueueSlice {
    param(
        [Parameter(Mandatory = $true)]
        [array]$Queue,

        [Parameter(Mandatory = $true)]
        [string]$Start,

        [Parameter(Mandatory = $true)]
        [int]$Limit
    )

    $startIndex = -1

    for ($i = 0; $i -lt $Queue.Count; $i++) {
        if ($Queue[$i].phase -eq $Start) {
            $startIndex = $i
            break
        }
    }

    if ($startIndex -lt 0) {
        throw "StartPhase not found in master queue: $Start"
    }

    return @($Queue[$startIndex..([Math]::Min($Queue.Count - 1, $startIndex + $Limit - 1))])
}

function New-PhasePrompt {
    param(
        [Parameter(Mandatory = $true)]
        $Phase
    )

    return @"
You are Codex working inside the local Jarvis Quant Framework repo.

Build roadmap phase:
$($Phase.phase) - $($Phase.title)

Phase specification:
$($Phase.spec)

Mandatory safety boundaries:
- Do not touch .env.
- Do not request, print, modify, or expose API keys, broker credentials, OAuth tokens, passwords, private keys, or secrets.
- Do not enable live trading.
- Do not submit broker orders.
- Do not add broker order routing.
- Use only approved research-state labels and safety-gate classifications.
- Keep all strategy work research-only, paper-only, monitor-only, or human-review-required.
- Add or update tests.
- Keep the patch narrow and aligned with the phase.
- Do not commit.
- Do not push.
- Do not merge.

After patching, summarize changed files and tests to run.
"@
}

function Get-ChangedPathsForCheckpoint {
    $statusJson = & python -m automation.autopilot_staging discover --repo $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Could not discover changed paths with autopilot staging guard."
    }

    $status = $statusJson | ConvertFrom-Json
    $paths = @($status.intended_paths)
    if ($paths.Count -eq 0) {
        return @()
    }

    return @($paths)
}

function Assert-CleanGitWorktree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Context
    )

    $statusJson = & python -m automation.autopilot_staging discover --repo $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect git worktree before $Context. STOP."
    }

    $status = $statusJson | ConvertFrom-Json
    $paths = @($status.intended_paths)
    if ($paths.Count -gt 0) {
        throw "Git worktree is not clean before $Context. STOP."
    }
}

function Invoke-PhaseCheckpoint {
    param(
        [Parameter(Mandatory = $true)]
        $Phase,

        [Parameter(Mandatory = $true)]
        [string[]]$ChangedPaths
    )

    if ($ChangedPaths.Count -eq 0) {
        throw "No changed paths found after Codex phase patch. STOP."
    }

    $testPaths = @()
    foreach ($path in $ChangedPaths) {
        if ($path -like "tests/test_*.py") {
            $testPaths += $path
        }
    }

    if ($testPaths.Count -eq 0) {
        $testPaths = @("tests/")
    }

    $checkpointArgs = @{
        PhaseName = "$($Phase.phase) $($Phase.title)"
        ChangedPath = $ChangedPaths
        FocusedTest = $testPaths
        CommitMessage = $Phase.commit_message
    }

    if ($Commit) {
        $checkpointArgs["Commit"] = $true
    }

    if ($PushBranch) {
        $checkpointArgs["PushBranch"] = $true
    }

    .\scripts\run_jarvis_phase_checkpoint.ps1 @checkpointArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Checkpoint failed for $($Phase.phase). STOP."
    }
}

function Merge-PhaseToMain {
    param(
        [Parameter(Mandatory = $true)]
        $Phase
    )

    if (-not $MergeToMain) {
        return
    }

    $phaseBranch = $Phase.branch

    Write-Host "`n=== MERGE $($Phase.phase) INTO MAIN ===" -ForegroundColor Cyan

    Assert-CleanGitWorktree -Context "merge checkout"

    git checkout main
    if ($LASTEXITCODE -ne 0) { throw "Could not checkout main. STOP." }

    git pull origin main
    if ($LASTEXITCODE -ne 0) { throw "Could not pull main. STOP." }

    git merge --no-ff $phaseBranch -m "merge $($Phase.phase) $($Phase.title)"
    if ($LASTEXITCODE -ne 0) {
        git merge --abort
        throw "Merge failed for $($Phase.phase); attempted merge abort. STOP."
    }

    python -m pytest tests/ -q
    if ($LASTEXITCODE -ne 0) { throw "Full regression failed after merge for $($Phase.phase). STOP. Do not push main." }

    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "Push main failed for $($Phase.phase). STOP." }
}

Stop-IfUnsafeAutopilotRequest

if (-not (Test-Path $QueuePath)) {
    throw "Master plan queue not found: $QueuePath"
}

$queueResolvedPath = (Resolve-Path $QueuePath).Path
$queueText = [System.IO.File]::ReadAllText($queueResolvedPath, [System.Text.Encoding]::UTF8)

if ($queueText.Length -gt 0 -and $queueText[0] -eq [char]0xFEFF) {
    $queueText = $queueText.Substring(1)
}

$queue = $queueText | ConvertFrom-Json
$phases = Get-QueueSlice -Queue $queue -Start $StartPhase -Limit $MaxPhases

$runDir = "reports/master_plan_autopilot"
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

Write-Host "`n=== JARVIS MASTER PLAN AUTOPILOT ===" -ForegroundColor Cyan
Write-Host "StartPhase: $StartPhase"
Write-Host "MaxPhases: $MaxPhases"
Write-Host "Execute: $Execute"
Write-Host "AutoRepairWithCodex: $AutoRepairWithCodex"
Write-Host "Commit: $Commit"
Write-Host "PushBranch: $PushBranch"
Write-Host "MergeToMain: $MergeToMain"

foreach ($phase in $phases) {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host "PHASE: $($phase.phase) - $($phase.title)" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan

    if (-not $Execute -or $DryRun) {
        Write-Host "Branch: $($phase.branch)"
        Write-Host "Commit: $($phase.commit_message)"
        Write-Host "Spec:"
        Write-Host $phase.spec
        continue
    }

    git checkout main
    if ($LASTEXITCODE -ne 0) { throw "Could not checkout main. STOP." }

    git pull origin main
    if ($LASTEXITCODE -ne 0) { throw "Could not pull main. STOP." }

    Assert-CleanGitWorktree -Context "$($phase.phase) branch checkout"

    $existingBranch = git branch --list $phase.branch

    if ($existingBranch) {
        git checkout $phase.branch
    } else {
        git checkout -b $phase.branch
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not checkout/create branch $($phase.branch). STOP." }

    $promptPath = Join-Path $runDir "$($phase.phase)_prompt.txt"
    $codexLog = Join-Path $runDir "$($phase.phase)_codex.log"

    New-PhasePrompt -Phase $phase | Set-Content -Path $promptPath -Encoding UTF8

    Write-Host "`n=== RUN CODEX ROADMAP PATCH ===" -ForegroundColor Cyan

    python tools\jarvis_codex_exec.py `
        --prompt-file $promptPath `
        --output-path $codexLog `
        --sandbox workspace-write `
        --timeout-seconds 600

    if ($LASTEXITCODE -ne 0) {
        if (Test-Path $codexLog) {
            Get-Content -Path $codexLog
        } else {
            Write-Host "Codex log was not created: $codexLog" -ForegroundColor Yellow
        }
        throw "Codex roadmap patch failed for $($phase.phase). STOP."
    }

    $changedPaths = Get-ChangedPathsForCheckpoint

    try {
        Invoke-PhaseCheckpoint -Phase $phase -ChangedPaths $changedPaths
    } catch {
        if (-not $AutoRepairWithCodex) {
            throw
        }

        Write-Host "`n=== CHECKPOINT FAILED; RUNNING SUPERVISED REPAIR ===" -ForegroundColor Yellow

        $repairCommand = "python -m pytest tests/ -q"

        .\scripts\run_jarvis_supervised_repair_checkpoint.ps1 `
            -PhaseName "$($phase.phase) $($phase.title)" `
            -CommandText $repairCommand `
            -ChangedPath $changedPaths `
            -FocusedTest @("tests/") `
            -CommitMessage $phase.commit_message `
            -AutoRepairWithCodex `
            -Commit:$Commit `
            -PushBranch:$PushBranch

        if ($LASTEXITCODE -ne 0) {
            throw "Supervised repair failed for $($phase.phase). STOP."
        }
    }

    Merge-PhaseToMain -Phase $phase
}

Write-Host "`n=== MASTER PLAN AUTOPILOT COMPLETE ===" -ForegroundColor Green
git status --short --untracked-files=all
git log --oneline -16
