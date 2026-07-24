param(
  [switch]$DryRun,
  [switch]$StartMenu,
  [string]$ShortcutName = "Jarvis Quant UI-05",
  [string]$AppDataDir
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Launcher = Join-Path $RepoRoot "scripts\run_ui05_desktop_app.py"
if (-not (Test-Path -LiteralPath $Launcher)) {
  throw "UI-05 launcher not found."
}

$LocalAppData = if ($AppDataDir) { $AppDataDir } else { Join-Path $env:LOCALAPPDATA "JarvisQuant\UI05" }
$DesktopPath = [Environment]::GetFolderPath("DesktopDirectory")
$StartMenuPath = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
$Targets = @([pscustomobject]@{ Path = (Join-Path $DesktopPath "$ShortcutName.lnk"); Enabled = $true })
if ($StartMenu) {
  $Targets += [pscustomobject]@{ Path = (Join-Path $StartMenuPath "$ShortcutName.lnk"); Enabled = $true }
}

$Command = "`"$((Get-Command python).Source)`" `"$Launcher`" launch --fixture"
$Summary = [ordered]@{
  schema_version = "ui05.windows_desktop_installer.v1"
  dry_run = [bool]$DryRun
  repo_root = $RepoRoot
  app_data_dir = $LocalAppData
  live_trading_status = "LIVE TRADING: DISABLED"
  shortcuts = @($Targets | ForEach-Object { $_.Path })
}

if ($DryRun) {
  $Summary | ConvertTo-Json -Compress
  exit 0
}

New-Item -ItemType Directory -Force -Path $LocalAppData | Out-Null
$Shell = New-Object -ComObject WScript.Shell
foreach ($Target in $Targets) {
  $Parent = Split-Path -Parent $Target.Path
  New-Item -ItemType Directory -Force -Path $Parent | Out-Null
  $Shortcut = $Shell.CreateShortcut($Target.Path)
  $Shortcut.TargetPath = (Get-Command python).Source
  $Shortcut.Arguments = "`"$Launcher`" launch --fixture"
  $Shortcut.WorkingDirectory = $RepoRoot
  $Shortcut.Description = "Jarvis Quant UI-05 local read-only desktop app. LIVE TRADING: DISABLED."
  $Shortcut.Save()
}

$Summary | ConvertTo-Json -Compress
