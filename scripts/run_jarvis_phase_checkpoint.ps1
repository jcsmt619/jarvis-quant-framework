[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PhaseName,

    [string[]]$FocusedTest = @(),

    [string[]]$CompilePath = @(),

    [string[]]$CheckCommand = @(),

    [string[]]$ChangedPath = @(),

    [string]$CommitMessage = "",

    [switch]$SkipFullSuite,

    [switch]$Commit,

    [switch]$PushBranch,

    [switch]$AllowMain,

    [switch]$AllowDangerousPatterns
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Block
    )

    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Test-AllowListedSafetyLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Line
    )

    $allowedInstructionFragments = @(
        "Do not touch .env",
        "Do not modify .env",
        "any .env/API key/secret access",
        "No .env",
        "not touch .env",
        "not access secrets",
        "Safety review",
        "safety scan",
        "Dangerous pattern found",
        "AllowDangerousPatterns",
        "dangerousPatterns",
        "Autopilot does not mean",
        "broker order submission",
        "Do not submit broker orders",
        "Do not enable live trading",
        "LIVE TRADING: DISABLED"
    )

    foreach ($fragment in $allowedInstructionFragments) {
        if ($Line -like "*$fragment*") {
            return $true
        }
    }

    return $false
}

Write-Host "`n=== JARVIS PHASE CHECKPOINT: $PhaseName ===" -ForegroundColor Green
Write-Host "Repo: $RepoRoot"

$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Could not read git branch."
}

Write-Host "Branch: $branch"

if ($branch -eq "main" -and -not $AllowMain) {
    throw "Refusing to run commit checkpoint directly on main. Create a phase branch first, or pass -AllowMain intentionally."
}

Invoke-Step "Git status before checkpoint" {
    git status --short --untracked-files=all
}

if ($CompilePath.Count -gt 0) {
    Invoke-Step "Compile selected files" {
        python -m compileall @CompilePath
    }
}

foreach ($test in $FocusedTest) {
    Invoke-Step "Focused test: $test" {
        python -m pytest $test -q
    }
}

foreach ($commandText in $CheckCommand) {
    Invoke-Step "Check command: $commandText" {
        Invoke-Expression $commandText
    }
}

if (-not $SkipFullSuite) {
    Invoke-Step "Full test suite" {
        python -m pytest tests/ -q
    }
}

if ($ChangedPath.Count -gt 0) {
    Invoke-Step "Register changed paths for diff review" {
        foreach ($path in $ChangedPath) {
            if (-not (Test-Path $path)) {
                throw "Changed path does not exist: $path"
            }
            git add -N $path
        }
    }

    Invoke-Step "Git diff check" {
        git diff --check -- @ChangedPath
    }

    if (-not $AllowDangerousPatterns) {
        Write-Host "`n=== Safety pattern scan ===" -ForegroundColor Cyan

        $diffText = & git diff -U0 -- @ChangedPath
        $addedLines = $diffText -split "`n" | Where-Object {
            $_.StartsWith("+") -and -not $_.StartsWith("+++")
        }

        $dangerousPatterns = @(
            "\+\s*.*(Get-Content|Set-Content|cat|type|open|read_text|write_text).*(\." + "env)",
            "\+\s*.*(API_" + "KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)\s*=",
            "\+\s*.*live_trading_" + "enabled\s*=\s*True",
            "\+\s*.*LIVE TRADING:\s*ENABLED",
            "\+\s*.*paper\s*=\s*False",
            "\+\s*.*submit_" + "order\s*\(",
            "\+\s*.*place_" + "order\s*\(",
            "\+\s*.*create_" + "order\s*\("
        )

        foreach ($line in $addedLines) {
            if (Test-AllowListedSafetyLine -Line $line) {
                continue
            }

            foreach ($pattern in $dangerousPatterns) {
                if ($line -match $pattern) {
                    throw "Safety scan blocked this checkpoint. Dangerous pattern found: $pattern in line: $line"
                }
            }
        }

        Write-Host "Safety pattern scan passed." -ForegroundColor Green
    }
}

if ($Commit) {
    if ([string]::IsNullOrWhiteSpace($CommitMessage)) {
        throw "Commit requested but CommitMessage is empty."
    }

    if ($ChangedPath.Count -eq 0) {
        throw "Commit requested but ChangedPath is empty. Refusing to git add everything."
    }

    Invoke-Step "Stage changed paths" {
        git add @ChangedPath
    }

    Invoke-Step "Commit checkpoint" {
        git commit -m $CommitMessage
    }
}

if ($PushBranch) {
    Invoke-Step "Push branch" {
        git push -u origin $branch
    }
}

Write-Host "`n=== PHASE CHECKPOINT COMPLETE: $PhaseName ===" -ForegroundColor Green
git status --short --untracked-files=all
git log --oneline -5
