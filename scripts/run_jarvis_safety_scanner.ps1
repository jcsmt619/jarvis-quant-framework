[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Path,

    [switch]$DiffOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$argsList = @("scripts/check_jarvis_safety_scanner.py")

if ($DiffOnly) {
    $argsList += "--diff-only"
}

$argsList += $Path

python @argsList
exit $LASTEXITCODE
