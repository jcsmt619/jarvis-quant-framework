param(
  [switch]$ConfirmRemove,
  [switch]$DryRun,
  [string]$ShortcutName = "Jarvis Quant UI-05",
  [string]$AppDataDir
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmRemove -and -not $DryRun) {
  throw "Explicit -ConfirmRemove is required. The uninstaller removes only UI-05 shortcuts, locks, temporary profiles, and sanitized logs."
}

$LocalAppData = if ($AppDataDir) { $AppDataDir } else { Join-Path $env:LOCALAPPDATA "JarvisQuant\UI05" }
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "$ShortcutName.lnk"
$StartMenuShortcut = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs\$ShortcutName.lnk"
$Allowed = @($DesktopShortcut, $StartMenuShortcut)
$RemovableData = @(
  (Join-Path $LocalAppData "jarvis-ui05-desktop.lock"),
  (Join-Path $LocalAppData "logs"),
  (Join-Path $LocalAppData "profiles")
)

$Summary = [ordered]@{
  schema_version = "ui05.windows_desktop_uninstaller.v1"
  dry_run = [bool]$DryRun
  app_data_dir = $LocalAppData
  live_trading_status = "LIVE TRADING: DISABLED"
  shortcut_candidates = $Allowed
  data_candidates = $RemovableData
}

if ($DryRun) {
  $Summary | ConvertTo-Json -Compress
  exit 0
}

foreach ($Path in $Allowed) {
  if (Test-Path -LiteralPath $Path) {
    Remove-Item -LiteralPath $Path -Force
  }
}

foreach ($Path in $RemovableData) {
  if (Test-Path -LiteralPath $Path) {
    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    $Root = (Resolve-Path -LiteralPath $LocalAppData -ErrorAction SilentlyContinue).Path
    if ($Root -and $Resolved.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
  }
}

$Summary | ConvertTo-Json -Compress
