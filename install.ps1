#Requires -Version 5.1
# algosec-agent-spec Windows installer — global skills (algosec-lean style)
param(
  [string]$Register = "",
  [switch]$RegisterHere,
  [switch]$SkillsOnly
)

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillsSrc = Join-Path $RepoDir "skills"
$CursorSkills = Join-Path $env:USERPROFILE ".cursor\skills"
if ($env:WIN_CURSOR_HOME) {
  $CursorSkills = Join-Path $env:WIN_CURSOR_HOME ".cursor\skills"
}

Write-Host "Installing Cursor skills → $CursorSkills"
New-Item -ItemType Directory -Force -Path $CursorSkills | Out-Null
Get-ChildItem -Directory $SkillsSrc | ForEach-Object {
  $dest = Join-Path $CursorSkills $_.Name
  if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
  Copy-Item -Recurse $_.FullName $dest
  Write-Host "Synced $($_.Name)"
}
Set-Content -Path (Join-Path $CursorSkills ".algosec-agent-spec-root") -Value $RepoDir
Write-Host "Wrote .algosec-agent-spec-root"

# Windows paths must be translated for the bash that will run install.sh:
#   Git Bash  -> C:/Users/me/app          (forward slashes are enough)
#   WSL bash  -> /mnt/c/Users/me/app      (System32\bash.exe; use wslpath)
function ConvertTo-BashPath([string]$WinPath, $BashCmd) {
  $full = (Resolve-Path $WinPath).Path
  if ($BashCmd.Source -like "*\System32\*") {
    $converted = & wsl wslpath -a ($full -replace '\\', '/')
    if ($LASTEXITCODE -eq 0 -and $converted) { return $converted.Trim() }
  }
  return ($full -replace '\\', '/')
}

$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash) {
  $installer = "$(ConvertTo-BashPath $RepoDir $bash)/install.sh"
  if ($RegisterHere) {
    # Registers the git root of the current directory, else the directory itself.
    & bash $installer --register-here
  } elseif ($Register) {
    & bash $installer --register (ConvertTo-BashPath $Register $bash)
  } elseif (-not $SkillsOnly) {
    # Match Unix bare ./install.sh (skills already synced; refresh harness via full script)
    & bash $installer
  }
} elseif ($Register) {
  Write-Host "WARN: bash not found. Skills installed; run ./install.sh --register from Git Bash/WSL for project harness."
}

Write-Host "Done. Skills are in $CursorSkills"
Write-Host "Restart Cursor or start a new chat."
Write-Host "Verify: ./check-install.sh  (or .\check-install.ps1)"
Write-Host "If PowerShell blocked scripts: Set-ExecutionPolicy -Scope Process Bypass"
