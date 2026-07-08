[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StartPhase,

    [int]$MaxPhases = 1,

    [int]$PhaseTimeoutSeconds = 3600,

    [int]$CodexLimitSleepMinutes = 20,

    [int]$MaxCodexLimitSleeps = 12
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

python automation\autonomous_master_plan_orchestrator_v2.py `
    --repo "." `
    --start-phase $StartPhase `
    --max-phases $MaxPhases `
    --phase-timeout-seconds $PhaseTimeoutSeconds `
    --codex-limit-sleep-minutes $CodexLimitSleepMinutes `
    --max-codex-limit-sleeps $MaxCodexLimitSleeps

exit $LASTEXITCODE
