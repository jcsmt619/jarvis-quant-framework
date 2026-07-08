[CmdletBinding()]
param(
    [string]$QueuePath = "config/jarvis_master_plan_queue.json"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

python automation\roadmap_queue_extender.py --queue-path $QueuePath
exit $LASTEXITCODE
